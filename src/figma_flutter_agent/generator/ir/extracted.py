"""Extracted widget materialization from widget IR."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart.llm_codegen import _canonical_widget_class_name
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_screen_body_from_ir
from figma_flutter_agent.generator.ir.tree import index_clean_tree, merge_screen_ir
from figma_flutter_agent.generator.ir.validate import (
    apply_ir_guards,
    validate_screen_ir,
)
from figma_flutter_agent.generator.layout import render_widget_file
from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    ScreenIr,
    WidgetIrNode,
)


def drop_extracted_widgets_for_inline_hosts(
    widgets: list[ExtractedWidget],
    clean_tree: CleanDesignTreeNode,
) -> list[ExtractedWidget]:
    """Remove LLM extracted widgets that target inline form-field hosts.

    Args:
        widgets: Extracted widget payloads from structured LLM output.
        clean_tree: Canonical clean design tree for the screen.

    Returns:
        Filtered widget list safe for ``lib/widgets`` materialization.
    """
    from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

    tree_by_id = index_clean_tree(clean_tree)
    kept: list[ExtractedWidget] = []
    for widget in widgets:
        figma_id = widget.widget_ir.figma_id if widget.widget_ir is not None else None
        clean = tree_by_id.get(figma_id) if figma_id else None
        if clean is not None and must_inline_extracted_widget_host(clean):
            logger.warning(
                "Dropping extracted widget {}: figmaId {} must inline in layout",
                widget.widget_name,
                figma_id,
            )
            continue
        kept.append(widget)
    return kept


def emit_extracted_widget_code_from_ir(
    widget_ir: WidgetIrNode,
    *,
    clean_tree: CleanDesignTreeNode,
    widget_name: str,
    ctx: IrEmitContext,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> str:
    """Compile one extracted widget IR subtree into a widget Dart file."""
    tree_by_id = index_clean_tree(clean_tree)
    subtree = tree_by_id.get(widget_ir.figma_id)
    if subtree is None:
        raise GenerationError(f"widgetIr figmaId {widget_ir.figma_id!r} not found in clean tree")
    widget_ir_screen = ScreenIr(root=widget_ir)
    if ctx.policy.validate:
        clean_tree = validate_screen_ir(
            widget_ir_screen,
            clean_tree,
            project_dir=project_dir,
            tokens=tokens,
            apply_guards=ctx.policy.apply_guards,
        )
        subtree = index_clean_tree(clean_tree).get(widget_ir.figma_id) or subtree
    elif ctx.policy.apply_guards:
        clean_tree = apply_ir_guards(widget_ir_screen, clean_tree, tokens=tokens)
        subtree = index_clean_tree(clean_tree).get(widget_ir.figma_id) or subtree
    merged = merge_screen_ir(
        subtree,
        widget_ir_screen,
        extracted_class_by_widget_name={
            widget_name: _canonical_widget_class_name(widget_name),
        },
    )
    widget_ctx = IrEmitContext(
        semantic_report_only=ctx.semantic_report_only,
        uses_svg=ctx.uses_svg,
        cluster_classes=ctx.cluster_classes,
        cluster_vector_variants=ctx.cluster_vector_variants,
        theme_variant=ctx.theme_variant,
        responsive_enabled=ctx.responsive_enabled,
        is_layout_root=True,
        bundled_font_families=ctx.bundled_font_families,
        dart_weight_overrides_by_family=ctx.dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=ctx.text_theme_slot_by_style_name,
        text_theme_size_slots=ctx.text_theme_size_slots,
        policy=ctx.policy,
    )
    body = emit_screen_body_from_ir(
        widget_ir_screen,
        merged,
        ctx=widget_ctx,
        extracted_class_by_widget_name={
            widget_name: _canonical_widget_class_name(widget_name),
        },
    )
    class_name = _canonical_widget_class_name(widget_name)
    file_stem = to_snake_case(widget_name)
    return render_widget_file(
        class_name=class_name,
        body=body,
        uses_svg=ctx.uses_svg,
        source_file=f"lib/widgets/{file_stem}.dart",
    )


def materialize_extracted_widgets(
    widgets: list[ExtractedWidget],
    *,
    clean_tree: CleanDesignTreeNode,
    ctx: IrEmitContext,
    prefer_existing_code: bool = True,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> list[ExtractedWidget]:
    tree_by_id = index_clean_tree(clean_tree)
    materialized: list[ExtractedWidget] = []
    for widget in widgets:
        if widget.widget_ir is None:
            materialized.append(widget)
            continue
        if prefer_existing_code and widget.resolved_code():
            materialized.append(widget)
            continue
        if widget.widget_ir.figma_id not in tree_by_id:
            logger.warning(
                "Skipping widgetIr materialization for {}: figmaId {} absent from clean tree "
                "(likely true_subtree_pruning); rely on deterministic lib/widgets code",
                widget.widget_name,
                widget.widget_ir.figma_id,
            )
            materialized.append(widget)
            continue
        code = emit_extracted_widget_code_from_ir(
            widget.widget_ir,
            clean_tree=clean_tree,
            widget_name=widget.widget_name,
            ctx=ctx,
            project_dir=project_dir,
            tokens=tokens,
        )
        materialized.append(widget.model_copy(update={"code": code}))
    return materialized
