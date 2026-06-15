"""Deterministic widgets for vector-rich screen subtrees in LLM generation mode."""

from __future__ import annotations

from figma_flutter_agent.generator.subtree.auth_buttons import (
    reconcile_auth_button_orphan_icons,
)
from figma_flutter_agent.generator.subtree.merge import (
    merge_thin_llm_widgets_with_subtrees,
    replace_extracted_subtree_nodes_with_refs,
)
from figma_flutter_agent.generator.subtree.placement import (
    _should_insert_missing_subtree,
    force_subtree_widgets_at_placement,
    insert_missing_subtree_widgets_at_placement,
    replace_inlined_planned_widgets,
)
from figma_flutter_agent.generator.subtree.plan import (
    ensure_subtree_widget_planned_files,
    plan_subtree_widget_files,
    preserve_deterministic_widget_planned_files,
    seed_subtree_widgets_from_project,
    sync_subtree_extracted_widgets,
)
from figma_flutter_agent.generator.subtree.render import (
    _subtree_render_root,
    build_cluster_render_context,
    refresh_subtree_widget_planned_files,
    render_subtree_widgets,
)
from figma_flutter_agent.generator.subtree.spec import (
    SubtreeWidgetResult,
    SubtreeWidgetSpec,
    build_subtree_widget_hints,
    collect_subtree_widget_specs,
)


def reconcile_llm_screen_with_subtrees(
    screen_code: str,
    *,
    subtree_result: SubtreeWidgetResult | None,
    planned_files: dict[str, str],
    clean_tree,
    uses_svg: bool = True,
) -> str:
    """Patch LLM screen bodies to use prebuilt subtree widgets and Figma-accurate copy."""
    from figma_flutter_agent.generator.dart.llm_codegen import apply_clean_tree_text_to_screen
    from figma_flutter_agent.generator.subtree.placement import (
        _replace_empty_subtree_placeholder,
        _resolve_widget_class_name,
    )

    updated = screen_code
    if subtree_result is not None:
        updated = force_subtree_widgets_at_placement(
            updated,
            subtree_result=subtree_result,
            planned_files=planned_files,
        )
        updated = insert_missing_subtree_widgets_at_placement(
            updated,
            subtree_result=subtree_result,
            planned_files=planned_files,
        )
        for spec in subtree_result.specs:
            placement = spec.representative.stack_placement
            if placement is None or placement.width is None or placement.height is None:
                continue
            class_name = _resolve_widget_class_name(planned_files, subtree_result, spec)
            updated = _replace_empty_subtree_placeholder(
                updated,
                class_name=class_name,
                left=placement.left,
                top=placement.top,
                width=placement.width,
                height=placement.height,
            )
    updated = replace_inlined_planned_widgets(
        updated,
        planned_files=planned_files,
        clean_tree=clean_tree,
    )
    updated = apply_clean_tree_text_to_screen(updated, clean_tree)
    updated = reconcile_auth_button_orphan_icons(
        updated,
        clean_tree=clean_tree,
        planned_files=planned_files,
    )
    from figma_flutter_agent.generator.dart.postprocess import (
        strip_design_canvas_gesture_matryoshka,
    )

    updated = strip_design_canvas_gesture_matryoshka(updated)
    from figma_flutter_agent.generator.ambient_background import (
        ensure_centered_design_canvas,
        fix_ambient_background_responsiveness,
    )

    updated = fix_ambient_background_responsiveness(
        updated,
        clean_tree,
        uses_svg=uses_svg,
    )
    updated = ensure_centered_design_canvas(updated)
    from figma_flutter_agent.generator.planned.reconcile import (
        strip_inline_widget_duplicates_from_screen,
        strip_llm_relative_widget_imports,
    )

    updated = strip_llm_relative_widget_imports(updated)
    updated = strip_inline_widget_duplicates_from_screen(updated, planned_files)
    return _finalize_reconciled_screen(screen_code, updated)


def _finalize_reconciled_screen(original: str, reconciled: str) -> str:
    from loguru import logger

    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        validate_dart_delimiters,
    )

    if validate_dart_delimiters(reconciled) is None:
        return reconciled
    repaired = repair_dart_delimiters(reconciled)
    if validate_dart_delimiters(repaired) is None:
        logger.warning(
            "Subtree reconcile produced invalid Dart syntax; keeping delimiter-repaired screenCode"
        )
        return repaired
    delimiter_error = validate_dart_delimiters(reconciled)
    logger.warning(
        "Subtree reconcile produced invalid Dart syntax ({}); keeping original screenCode",
        delimiter_error,
    )
    return original


__all__ = [
    "SubtreeWidgetResult",
    "SubtreeWidgetSpec",
    "build_subtree_widget_hints",
    "collect_subtree_widget_specs",
    "ensure_subtree_widget_planned_files",
    "plan_subtree_widget_files",
    "preserve_deterministic_widget_planned_files",
    "seed_subtree_widgets_from_project",
    "sync_subtree_extracted_widgets",
    "build_cluster_render_context",
    "refresh_subtree_widget_planned_files",
    "render_subtree_widgets",
    "merge_thin_llm_widgets_with_subtrees",
    "replace_extracted_subtree_nodes_with_refs",
    "force_subtree_widgets_at_placement",
    "insert_missing_subtree_widgets_at_placement",
    "replace_inlined_planned_widgets",
    "reconcile_auth_button_orphan_icons",
    "reconcile_llm_screen_with_subtrees",
    "_finalize_reconciled_screen",
    "_subtree_render_root",
]
