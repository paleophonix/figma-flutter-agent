"""LLM analyze repair payload helpers."""

from __future__ import annotations

import json
from typing import Any

from figma_flutter_agent.llm.refine_context import RefineAttemptSummary
from figma_flutter_agent.llm.repair_scope import RepairScope


def build_repair_user_payload(
    *,
    feature_name: str,
    scope: RepairScope,
    analyze_errors: list[str],
) -> str:
    """Build the scoped repair-mode user JSON payload for structured LLM output.

    Args:
        feature_name: Generated feature slug.
        scope: Scoped repair targets derived from analyzer output.
        analyze_errors: Analyzer error lines from ``dart analyze``.

    Returns:
        JSON string for the LLM user message.
    """
    payload: dict[str, Any] = {
        "mode": "repair_patch",
        "featureName": feature_name,
        "analyzeErrors": analyze_errors,
        "unchangedWidgetNames": list(scope.unchanged_widget_names),
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
    return json.dumps(payload, ensure_ascii=False)


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
) -> str:
    """Build the visual-refine user JSON payload for structured LLM output."""
    from figma_flutter_agent.llm.prompts import visual_refine_attached_images
    from figma_flutter_agent.llm.refine_context import build_foreground_layout_anchors
    from figma_flutter_agent.schemas import NodeType

    payload: dict[str, Any] = {
        "mode": "visual_refine",
        "featureName": feature_name,
        "cleanTree": clean_tree.model_dump(mode="json", by_alias=True),
        "tokens": tokens.model_dump(mode="json", by_alias=True),
        "assetManifest": asset_manifest,
        "currentGeneration": {
            "screenCode": current_generation.screen_code,
            "extractedWidgets": [
                widget.model_dump(mode="json", by_alias=True)
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
    return json.dumps(payload, ensure_ascii=False)
