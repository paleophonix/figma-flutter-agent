"""Extracted widget materialization from widget IR."""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart.llm_codegen import _canonical_widget_class_name
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_screen_body_from_ir
from figma_flutter_agent.generator.ir.extracted_paint import (
    extracted_icon_badge_glyph_emit_needs_rematerialization,
    prefers_clean_tree_extracted_widget_emit,
    subtree_has_visible_paint,
)
from figma_flutter_agent.generator.ir.tree import index_clean_tree, merge_screen_ir
from figma_flutter_agent.generator.ir.validate import (
    apply_ir_guards,
    validate_screen_ir,
)
from figma_flutter_agent.generator.layout import render_widget_file
from figma_flutter_agent.generator.layout.common import (
    to_snake_case,
    wrap_centered_decoration_container,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def _iter_ir_nodes(root: WidgetIrNode) -> list[WidgetIrNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_iter_ir_nodes(child))
    return nodes


def _default_widget_ir_kind(clean: CleanDesignTreeNode) -> WidgetIrKind:
    mapping = {
        NodeType.COLUMN: WidgetIrKind.COLUMN,
        NodeType.ROW: WidgetIrKind.ROW,
        NodeType.STACK: WidgetIrKind.STACK,
        NodeType.TEXT: WidgetIrKind.TEXT,
        NodeType.BUTTON: WidgetIrKind.BUTTON,
        NodeType.CARD: WidgetIrKind.CONTAINER_CARD,
    }
    return mapping.get(clean.type, WidgetIrKind.AUTO)


def align_extracted_widgets_with_screen_ir(
    screen_ir: ScreenIr | None,
    widgets: list[ExtractedWidget],
    clean_tree: CleanDesignTreeNode,
) -> list[ExtractedWidget]:
    """Ensure each screen-IR extracted root has a distinct extracted widget entry."""
    if screen_ir is None or screen_ir.root is None:
        return widgets
    tree_by_id = index_clean_tree(clean_tree)
    extracted_nodes = [
        node
        for node in _iter_ir_nodes(screen_ir.root)
        if node.kind == WidgetIrKind.EXTRACTED and node.ref is not None and node.figma_id
    ]
    if not extracted_nodes:
        return widgets
    by_name: dict[str, list[ExtractedWidget]] = {}
    for widget in widgets:
        by_name.setdefault(widget.widget_name, []).append(widget)
    resolved = list(widgets)
    seen_figma_ids = {
        widget.widget_ir.figma_id
        for widget in widgets
        if widget.widget_ir is not None and widget.widget_ir.figma_id
    }
    for ir_node in extracted_nodes:
        ref_name = (ir_node.ref.widget_name if ir_node.ref else "").strip()
        figma_id = ir_node.figma_id
        if not ref_name or figma_id in seen_figma_ids:
            continue
        template_items = by_name.get(ref_name) or []
        template = next(
            (item for item in template_items if item.widget_ir is not None),
            template_items[0] if template_items else None,
        )
        clean = tree_by_id.get(figma_id)
        if clean is None:
            continue
        widget_ir = (
            template.widget_ir.model_copy(update={"figma_id": figma_id})
            if template is not None and template.widget_ir is not None
            else WidgetIrNode(figma_id=figma_id, kind=_default_widget_ir_kind(clean))
        )
        match = re.match(r"^(.*?)(\d*)Widget$", ref_name)
        stem = (match.group(1) if match and match.group(1) else None) or "Extracted"
        suffix = len([item for item in resolved if item.widget_name.startswith(stem)]) + 1
        new_name = f"{stem}{suffix}Widget"
        resolved.append(
            ExtractedWidget(
                widget_name=new_name,
                widget_ir=widget_ir,
            )
        )
        seen_figma_ids.add(figma_id)
    return resolved


def build_figma_id_to_widget_name(widgets: list[ExtractedWidget]) -> dict[str, str]:
    """Map each widgetIr figma root to its public widget name."""
    mapping: dict[str, str] = {}
    for widget in widgets:
        if widget.widget_ir is None or not widget.widget_ir.figma_id:
            continue
        mapping[widget.widget_ir.figma_id] = widget.widget_name
    return mapping


def remap_screen_ir_extracted_refs(
    screen_ir: ScreenIr,
    *,
    figma_id_to_widget_name: dict[str, str],
) -> ScreenIr:
    """Point extracted IR refs at the widget name for their figma root."""

    def _remap(node: WidgetIrNode) -> WidgetIrNode:
        updated = node
        if node.kind == WidgetIrKind.EXTRACTED and node.ref is not None:
            mapped = figma_id_to_widget_name.get(node.figma_id)
            if mapped and mapped != node.ref.widget_name:
                updated = node.model_copy(
                    update={"ref": node.ref.model_copy(update={"widget_name": mapped})}
                )
        if not updated.children:
            return updated
        return updated.model_copy(
            update={"children": [_remap(child) for child in updated.children]}
        )

    if screen_ir.root is None:
        return screen_ir
    return screen_ir.model_copy(update={"root": _remap(screen_ir.root)})


def disambiguate_extracted_widget_name_collisions(
    widgets: list[ExtractedWidget],
) -> list[ExtractedWidget]:
    """Assign unique widget names when one name maps to multiple figma roots."""
    grouped: dict[str, list[ExtractedWidget]] = {}
    for widget in widgets:
        grouped.setdefault(widget.widget_name, []).append(widget)
    resolved: list[ExtractedWidget] = []
    for name, items in grouped.items():
        figma_ids = {
            item.widget_ir.figma_id
            for item in items
            if item.widget_ir is not None and item.widget_ir.figma_id
        }
        if len(items) == 1 or len(figma_ids) <= 1:
            resolved.extend(items)
            continue
        match = re.match(r"^(.*?)(\d*)Widget$", name)
        stem = (match.group(1) if match and match.group(1) else None) or "Extracted"
        for index, item in enumerate(items, start=1):
            new_name = f"{stem}{index}Widget"
            resolved.append(item.model_copy(update={"widget_name": new_name}))
    return resolved


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


def _extracted_widget_skip_cluster_id(
    subtree: CleanDesignTreeNode,
    widget_name: str,
    ctx: IrEmitContext,
) -> str | None:
    """Block cluster delegate shortcut when materializing the widget's own cluster root."""
    cluster_id = subtree.cluster_id
    if not cluster_id or not ctx.cluster_classes:
        return None
    class_name = _canonical_widget_class_name(widget_name)
    if ctx.cluster_classes.get(cluster_id) == class_name:
        return cluster_id
    return None


def _render_extracted_widget_body(
    node: CleanDesignTreeNode,
    *,
    widget_name: str,
    ctx: IrEmitContext,
) -> str:
    """Render an extracted widget subtree without self-referential cluster delegation."""
    from figma_flutter_agent.generator.layout.widgets import render_node_body

    return render_node_body(
        node,
        uses_svg=ctx.uses_svg,
        is_layout_root=False,
        responsive_enabled=ctx.responsive_enabled,
        cluster_classes=ctx.cluster_classes,
        cluster_vector_variants=ctx.cluster_vector_variants,
        skip_cluster_id=_extracted_widget_skip_cluster_id(node, widget_name, ctx),
    )


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
            semantics=ctx.semantics,
            strict_contrast=ctx.strict_contrast,
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
    skip_cluster_id = _extracted_widget_skip_cluster_id(subtree, widget_name, ctx)
    widget_ctx = IrEmitContext(
        semantic_report_only=ctx.semantic_report_only,
        uses_svg=ctx.uses_svg,
        cluster_classes=ctx.cluster_classes,
        cluster_vector_variants=ctx.cluster_vector_variants,
        theme_variant=ctx.theme_variant,
        responsive_enabled=ctx.responsive_enabled,
        is_layout_root=False,
        bundled_font_families=ctx.bundled_font_families,
        dart_weight_overrides_by_family=ctx.dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=ctx.text_theme_slot_by_style_name,
        text_theme_size_slots=ctx.text_theme_size_slots,
        skip_cluster_id=skip_cluster_id,
        policy=ctx.policy,
    )
    if prefers_clean_tree_extracted_widget_emit(widget_ir, subtree):
        body = _render_extracted_widget_body(merged, widget_name=widget_name, ctx=widget_ctx)
    else:
        body = emit_screen_body_from_ir(
            widget_ir_screen,
            merged,
            ctx=widget_ctx,
            extracted_class_by_widget_name={
                widget_name: _canonical_widget_class_name(widget_name),
            },
        )
        if subtree_has_visible_paint(subtree) and _is_shrink_only_emit_body(body):
            body = _render_extracted_widget_body(merged, widget_name=widget_name, ctx=widget_ctx)
    from figma_flutter_agent.generator.layout.widget_roots import (
        strip_stack_parent_data_wrappers,
        validate_widget_build_has_no_parent_data_root,
    )

    body = strip_stack_parent_data_wrappers(body)
    body = _preserve_extracted_widget_decoration_shell(subtree, body)
    class_name = _canonical_widget_class_name(widget_name)
    file_stem = to_snake_case(widget_name)
    code = render_widget_file(
        class_name=class_name,
        body=body,
        uses_svg=ctx.uses_svg,
        source_file=f"lib/widgets/{file_stem}.dart",
    )
    violations = validate_widget_build_has_no_parent_data_root(code)
    if violations:
        raise GenerationError(
            f"extracted widget {widget_name!r} violates emit invariant: {violations[0]}"
        )
    return code


def _extracted_widget_needs_decoration_rematerialization(
    subtree: CleanDesignTreeNode,
    existing_code: str,
) -> bool:
    """Return True when cached extracted widget code dropped a painted host shell."""
    if "BoxDecoration(" in existing_code:
        return False
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )
    from figma_flutter_agent.generator.layout.style import has_box_decoration
    from figma_flutter_agent.parser.interaction.input_fields import primary_surface_node

    if has_box_decoration(subtree.style):
        return True
    if layout_fact_icon_badge_stack(subtree):
        return True
    return primary_surface_node(subtree) is not None


def _preserve_extracted_widget_decoration_shell(
    subtree: CleanDesignTreeNode,
    body: str,
) -> str:
    """Wrap shrink-only extracted bodies with the host stack's painted shell."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )
    from figma_flutter_agent.generator.layout.style import (
        box_decoration_expr,
        has_box_decoration,
    )
    from figma_flutter_agent.parser.interaction.input_fields import primary_surface_node
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    if "BoxDecoration(" in body:
        return body
    style_source = subtree
    if not has_box_decoration(subtree.style):
        surface = primary_surface_node(subtree)
        if (
            surface is not None
            and layout_fact_icon_badge_stack(subtree)
            or surface is not None
            and has_box_decoration(surface.style)
        ):
            style_source = surface
        else:
            return body
    decoration = box_decoration_expr(
        style_source.style,
        width=subtree.sizing.width,
        height=subtree.sizing.height,
    )
    if decoration is None:
        return body
    width = subtree.sizing.width
    height = subtree.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        return wrap_centered_decoration_container(
            body,
            decoration=decoration,
            width=format_geometry_literal(float(width)),
            height=format_geometry_literal(float(height)),
        )
    return wrap_centered_decoration_container(body, decoration=decoration)


def _is_shrink_only_emit_body(body: str) -> bool:
    from figma_flutter_agent.generator.planned.reconcile import _is_shrink_only_widget_source

    probe = render_widget_file(
        class_name="ProbeWidget",
        body=body,
        uses_svg=False,
        source_file="lib/widgets/probe_widget.dart",
    )
    return _is_shrink_only_widget_source(probe)


def materialize_extracted_widgets(
    widgets: list[ExtractedWidget],
    *,
    clean_tree: CleanDesignTreeNode,
    screen_ir: ScreenIr | None = None,
    ctx: IrEmitContext,
    prefer_existing_code: bool = True,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> list[ExtractedWidget]:
    from figma_flutter_agent.generator.planned.reconcile import _is_shrink_only_widget_source

    widgets = align_extracted_widgets_with_screen_ir(screen_ir, widgets, clean_tree)
    widgets = disambiguate_extracted_widget_name_collisions(widgets)
    tree_by_id = index_clean_tree(clean_tree)
    materialized: list[ExtractedWidget] = []
    for widget in widgets:
        if widget.widget_ir is None:
            materialized.append(widget)
            continue
        existing = widget.resolved_code()
        subtree = tree_by_id.get(widget.widget_ir.figma_id)
        if (
            prefer_existing_code
            and existing
            and not _is_shrink_only_widget_source(existing)
            and not (
                subtree is not None
                and (
                    _extracted_widget_needs_decoration_rematerialization(subtree, existing)
                    or extracted_icon_badge_glyph_emit_needs_rematerialization(subtree, existing)
                )
            )
        ):
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
