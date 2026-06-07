"""Apply scoped LLM repair patches onto a generation payload."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart.syntax_repairs import apply_llm_dart_syntax_repairs
from figma_flutter_agent.generator.ir.repair import apply_ir_patch_to_screen
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.generator.dart.llm_codegen import (
    ensure_valid_llm_widget_code,
    sanitize_llm_screen_code,
    validate_dart_delimiters,
)
from figma_flutter_agent.llm.line_numbered_source import (
    strip_line_number_markers,
    strip_line_number_markers_from_diff,
)
from figma_flutter_agent.llm.unified_diff import apply_unified_diff, is_unified_diff_text
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlutterGenerationResponse,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
)

_FORBIDDEN_PATCH_MARKERS = (
    "<<<<<<<",
    ">>>>>>>",
    "// ... existing",
    "\nSEARCH\n",
    "\nREPLACE\n",
)
_SEARCH_REPLACE_RE = re.compile(r"\bSEARCH\b.*\bREPLACE\b", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class RepairApplyOutcome:
    """Result of merging LLM repair patches into a generation payload."""

    generation: FlutterGenerationResponse
    patches_applied: int = 0
    patches_rejected: int = 0
    ir_patches_applied: int = 0


def repair_patch_uses_forbidden_hunks(code: str) -> bool:
    """Return True when patch text uses SEARCH/REPLACE or conflict markers."""
    stripped = code.strip()
    if not stripped:
        return True
    if any(marker in code for marker in _FORBIDDEN_PATCH_MARKERS):
        return True
    if _SEARCH_REPLACE_RE.search(code):
        return True
    if stripped.startswith("...") or "\n...\n" in code:
        return True
    return False


def _resolve_base_source(
    patch: FlutterRepairPatch,
    *,
    current: FlutterGenerationResponse,
    base_sources: dict[str, str] | None,
    planned_path_for_target: str | None,
) -> str:
    if base_sources and planned_path_for_target:
        normalized = planned_path_for_target.replace("\\", "/")
        if normalized in base_sources:
            return base_sources[normalized]
        for key, value in base_sources.items():
            if key.replace("\\", "/") == normalized:
                return value
    if patch.target == "screenCode":
        return current.screen_code
    for widget in current.extracted_widgets:
        if widget.widget_name == patch.widget_name:
            return widget.resolved_code()
    return ""


def _apply_patch_code(
    patch: FlutterRepairPatch,
    *,
    current: FlutterGenerationResponse,
    base_sources: dict[str, str] | None,
    planned_path_for_target: str | None,
) -> str | None:
    if repair_patch_uses_forbidden_hunks(patch.code):
        logger.warning(
            "Rejecting {} repair patch: forbidden SEARCH/REPLACE or conflict markers",
            patch.target,
        )
        return None
    if not is_unified_diff_text(patch.code):
        logger.warning(
            "Rejecting {} repair patch: expected unified diff (---/+++ and @@ hunks)",
            patch.target,
        )
        return None
    base = _resolve_base_source(
        patch,
        current=current,
        base_sources=base_sources,
        planned_path_for_target=planned_path_for_target,
    )
    base = strip_line_number_markers(base)
    if not base.strip():
        logger.warning(
            "Rejecting {} repair patch: empty base source for {}",
            patch.target,
            planned_path_for_target or patch.target,
        )
        return None
    diff_text = strip_line_number_markers_from_diff(patch.code)
    patched = apply_unified_diff(base, diff_text)
    if patched is None:
        logger.warning(
            "Rejecting {} repair patch: unified diff did not apply cleanly",
            patch.target,
        )
        return None
    return apply_llm_dart_syntax_repairs(strip_line_number_markers(patched))


def apply_repair_patches(
    current: FlutterGenerationResponse,
    patch_response: FlutterRepairPatchResponse,
    *,
    escalation_level: int = 1,
    base_sources: dict[str, str] | None = None,
    target_planned_paths: dict[tuple[str, str | None], str] | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
    use_screen_ir: bool = False,
    require_screen_ir: bool = False,
) -> RepairApplyOutcome:
    """Merge repair patches into an existing generation payload.

    Args:
        current: Generation state before repair.
        patch_response: Scoped patches emitted by the repair LLM call.
        base_sources: Planned Dart file bodies used as diff bases (path → source).
        target_planned_paths: Map ``(target, widgetName)`` → planned relative path.
        escalation_level: Repair prompt escalation level (reserved for telemetry).

    Returns:
        Updated generation payload with patched targets only.

    Raises:
        ValueError: When a widget patch omits ``widgetName`` or names an unknown target.
    """
    del escalation_level
    if not patch_response.patches and not patch_response.ir_patches:
        return RepairApplyOutcome(generation=current)

    applied = 0
    rejected = 0
    ir_applied = 0
    screen_code = current.screen_code
    screen_ir = current.screen_ir
    dart_screen_patched = False
    widgets = list(current.extracted_widgets)
    widget_index = {widget.widget_name: index for index, widget in enumerate(widgets)}

    for ir_patch in patch_response.ir_patches:
        if screen_ir is None:
            logger.warning("Rejecting ir patch: generation has no screenIr")
            rejected += 1
            continue
        try:
            screen_ir = apply_ir_patch_to_screen(
                screen_ir,
                figma_id=ir_patch.figma_id,
                replace_subtree=ir_patch.replace_subtree,
                overrides=ir_patch.overrides,
                reorder_children=ir_patch.reorder_children,
            )
            ir_applied += 1
        except GenerationError as exc:
            logger.warning("Rejecting ir patch for {}: {}", ir_patch.figma_id, exc)
            rejected += 1

    if ir_applied and clean_tree is not None:
        from figma_flutter_agent.generator.ir.presence import (
            expand_extracted_widget_names_for_validate,
            normalize_screen_ir_presence,
        )

        extracted = frozenset(widget.widget_name for widget in widgets)
        screen_ir = normalize_screen_ir_presence(
            screen_ir,
            clean_tree,
            extracted_widget_names=extracted,
        )
        extracted_for_validate = expand_extracted_widget_names_for_validate(
            extracted,
            clean_tree=clean_tree,
            screen_ir=screen_ir,
        )
        validate_screen_ir(
            screen_ir,
            clean_tree,
            extracted_widget_names=extracted_for_validate,
            project_dir=project_dir,
            tokens=tokens,
            skip_presence_normalize=True,
        )

    for patch in patch_response.patches:
        if patch.target == "screenCode" and (use_screen_ir or require_screen_ir):
            logger.warning(
                "Rejecting screenCode repair patch: screen body must be patched via screenIr "
                "(use_screen_ir or require_screen_ir)"
            )
            rejected += 1
            continue
        path_key = (patch.target, patch.widget_name)
        planned_path = (
            target_planned_paths.get(path_key) if target_planned_paths else None
        )
        candidate = _apply_patch_code(
            patch,
            current=current,
            base_sources=base_sources,
            planned_path_for_target=planned_path,
        )
        if candidate is None:
            rejected += 1
            continue
        if patch.target == "screenCode":
            candidate = sanitize_llm_screen_code(candidate)
            if validate_dart_delimiters(candidate) is not None:
                logger.warning(
                    "Rejecting screenCode repair patch: {}",
                    validate_dart_delimiters(candidate),
                )
                rejected += 1
                continue
            screen_code = candidate
            dart_screen_patched = True
            applied += 1
            continue
        if patch.target != "extractedWidget":
            msg = f"Unsupported repair patch target: {patch.target!r}"
            raise ValueError(msg)
        if not patch.widget_name:
            msg = "extractedWidget repair patches must include widgetName."
            raise ValueError(msg)
        widget_code = ensure_valid_llm_widget_code(
            candidate,
            widget_name=patch.widget_name,
        )
        from figma_flutter_agent.generator.planned.reconcile import sync_widget_class_constructors

        widget_code = sync_widget_class_constructors(widget_code)
        if validate_dart_delimiters(widget_code) is not None:
            logger.warning(
                "Rejecting extractedWidget {} repair patch: {}",
                patch.widget_name,
                validate_dart_delimiters(widget_code),
            )
            rejected += 1
            continue
        updated = ExtractedWidget(
            widget_name=patch.widget_name,
            code=widget_code,
            widget_ir=None,
        )
        if patch.widget_name in widget_index:
            widgets[widget_index[patch.widget_name]] = updated
        else:
            widget_index[patch.widget_name] = len(widgets)
            widgets.append(updated)
        applied += 1

    if dart_screen_patched:
        screen_ir = None
    elif ir_applied:
        screen_code = None

    return RepairApplyOutcome(
        generation=FlutterGenerationResponse(
            screen_code=screen_code,
            screen_ir=screen_ir,
            extracted_widgets=widgets,
        ),
        patches_applied=applied,
        patches_rejected=rejected,
        ir_patches_applied=ir_applied,
    )
