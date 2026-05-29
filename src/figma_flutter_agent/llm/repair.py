"""LLM analyze repair payload helpers."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.llm.payload_format import format_labeled_user_payload
from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm, dump_tokens_for_llm
from figma_flutter_agent.llm.refine_context import RefineAttemptSummary
from figma_flutter_agent.llm.repair_scope import RepairScope
from figma_flutter_agent.schemas import ExtractedWidget, FlutterGenerationResponse


def _serialize_extracted_widget_for_payload(
    widget: ExtractedWidget,
    *,
    use_screen_ir: bool,
) -> dict[str, Any]:
    payload = widget.model_dump(mode="json", by_alias=True)
    if use_screen_ir and widget.widget_ir is not None:
        payload.pop("code", None)
    elif not use_screen_ir:
        payload.pop("widgetIr", None)
    return payload


def build_repair_user_payload(
    *,
    feature_name: str,
    scope: RepairScope,
    analyze_errors: list[str],
    escalation_level: int = 1,
    current_generation: FlutterGenerationResponse | None = None,
    use_screen_ir: bool = False,
) -> str:
    """Build the scoped repair-mode user JSON payload for structured LLM output.

    Args:
        feature_name: Generated feature slug.
        scope: Scoped repair targets derived from analyzer output.
        analyze_errors: Analyzer error lines from ``dart analyze``.

    Returns:
        Labeled user message for the LLM (### sections with JSON bodies).
    """
    sections: dict[str, Any] = {
        "mode": "repair_patch",
        "featureName": feature_name,
        "analyzeErrors": analyze_errors,
        "unchangedWidgetNames": list(scope.unchanged_widget_names),
        "repairWriteMode": "unified_diff",
        "repairDiffFormat": (
            "Each patch `code` MUST be a git unified diff against the clean (unnumbered) "
            "on-disk file. Hunk line numbers MUST match analyzeErrors and the `N: ` "
            "numbered plannedExcerpt. FORBIDDEN: line-number prefixes in diff lines, "
            "full file bodies, SEARCH/REPLACE, ellipses, or conflict markers."
        ),
        "numberedSourceFormat": (
            "plannedExcerpt and L6 code use `lineNumber: dartLine` prefixes aligned with "
            "dart format / flutter analyze diagnostics."
        ),
        "repairTargets": [
            {
                "target": target.target,
                "widgetName": target.widget_name,
                "plannedPath": target.planned_path,
                "code": target.code,
                "errors": list(target.errors),
                "plannedExcerpt": target.planned_excerpt,
            }
            for target in scope.targets
        ],
    }
    if use_screen_ir and current_generation is not None and current_generation.screen_ir is not None:
        sections["currentScreenIr"] = current_generation.screen_ir.model_dump(
            mode="json",
            by_alias=True,
        )
        sections["repairIrPatchFormat"] = (
            "Optional `irPatches` array for structural screen fixes without Dart syntax. "
            "Each entry needs `figmaId` from currentScreenIr / cleanTree. Use "
            "`replaceSubtree` for subtree replacement, `overrides` for text/accessibilityLabel, "
            "or `reorderChildren` for child order. Prefer unified-diff `patches` for analyzer "
            "syntax/type errors on planned Dart files."
        )
    output_schema = (
        "FlutterRepairPatchResponse JSON (patches, optional irPatches)"
        if use_screen_ir
        else "FlutterRepairPatchResponse JSON (patches array)"
    )
    return format_labeled_user_payload(
        mode="repair_patch",
        output_schema=output_schema,
        sections=sections,
    )


def _serialize_diff_regions(diff_bands: tuple) -> list[dict[str, Any]]:
    from figma_flutter_agent.validation.pixeldiff import DiffBandRegion

    bands: tuple[DiffBandRegion, ...] = diff_bands
    return [
        {
            "name": band.name,
            "changedRatio": band.changed_ratio,
            "yStart": band.y_start,
            "yEnd": band.y_end,
        }
        for band in bands
    ]


def build_visual_refine_user_payload(
    *,
    feature_name: str,
    clean_tree,
    tokens,
    asset_manifest: list[dict[str, str]],
    current_generation,
    changed_ratio: float,
    threshold: float,
    widget_hints: list[str] | None = None,
    navigation_hints: list[str] | None = None,
    refine_attempt: int = 1,
    max_refine_attempts: int = 1,
    previous_changed_ratio: float | None = None,
    refine_focus: str = "interaction",
    diff_bands: tuple = (),
    refine_history: tuple[RefineAttemptSummary, ...] = (),
    interactive_inventory: list[dict[str, Any]] | None = None,
    handler_audit: dict[str, Any] | None = None,
    canvas_size: dict[str, float | int] | None = None,
    asset_warnings: list[str] | None = None,
    surgical_widget_snippets: dict[str, str] | None = None,
    use_screen_ir: bool = False,
) -> str:
    """Build the visual-refine user JSON payload for structured LLM output."""
    from figma_flutter_agent.llm.prompts import visual_refine_attached_images
    from figma_flutter_agent.llm.refine_context import build_foreground_layout_anchors
    from figma_flutter_agent.schemas import NodeType

    payload: dict[str, Any] = {
        "mode": "visual_refine",
        "featureName": feature_name,
        "cleanTree": dump_clean_tree_for_llm(clean_tree),
        "tokens": dump_tokens_for_llm(tokens),
        "assetManifest": asset_manifest,
        "currentGeneration": {
            "screenCode": current_generation.screen_code,
            "extractedWidgets": [
                _serialize_extracted_widget_for_payload(widget, use_screen_ir=use_screen_ir)
                for widget in current_generation.extracted_widgets
            ],
        },
        "visualDiff": {
            "changedRatio": changed_ratio,
            "passed": changed_ratio <= threshold,
            "threshold": threshold,
            "diffRegions": _serialize_diff_regions(diff_bands),
        },
        "refineAttempt": refine_attempt,
        "maxRefineAttempts": max_refine_attempts,
        "refineFocus": refine_focus,
        "attachedImages": visual_refine_attached_images(),
    }
    if previous_changed_ratio is not None:
        payload["previousChangedRatio"] = previous_changed_ratio
    if refine_history:
        payload["refineHistory"] = [entry.to_payload() for entry in refine_history]
    if interactive_inventory is not None:
        payload["interactiveInventory"] = interactive_inventory
    if handler_audit is not None:
        payload["handlerAudit"] = handler_audit
    if canvas_size is not None:
        payload["canvasSize"] = canvas_size
    if asset_warnings:
        payload["assetWarnings"] = asset_warnings
    if widget_hints:
        payload["widgetExtractionHints"] = widget_hints
    if navigation_hints:
        payload["navigationHints"] = navigation_hints
    if clean_tree.type == NodeType.STACK:
        anchors = build_foreground_layout_anchors(clean_tree)
        if anchors:
            payload["layoutAnchors"] = anchors
    if surgical_widget_snippets:
        payload["refineMode"] = "surgical_widgets"
        payload["surgicalWidgetSnippets"] = surgical_widget_snippets
    if use_screen_ir:
        if current_generation.screen_ir is not None:
            payload["currentGeneration"]["screenIr"] = current_generation.screen_ir.model_dump(
                mode="json",
                by_alias=True,
            )
        from figma_flutter_agent.llm.ir_payload import dump_screen_ir_blueprint

        payload["screenIrBlueprint"] = dump_screen_ir_blueprint(clean_tree)
    output_schema = (
        "FlutterGenerationResponse JSON (screenIr, extractedWidgets)"
        if use_screen_ir
        else "FlutterGenerationResponse JSON (screenCode, extractedWidgets)"
    )
    return format_labeled_user_payload(
        mode="visual_refine",
        output_schema=output_schema,
        sections=payload,
    )
