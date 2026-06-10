"""CTA pill + footer link split-stack emitter."""

from __future__ import annotations

from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.parser.interaction import (
    _is_footer_link_text_node,
    _local_nodes,
    _stack_spans_primary_button_and_footer_link,
    primary_surface_node,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .core import _wrap_button_stack


def _try_render_cta_footer_split_stack(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None,
    cluster_vector_variant: ClusterVectorVariant | None,
    skip_cluster_id: str | None,
    responsive_enabled: bool,
    design_artboard_width: float | None = None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render CTA pill + footer link as separate vertical bands with one InkWell on the pill."""
    if node.type != NodeType.STACK:
        return None
    text_nodes = [
        item
        for item in _local_nodes(node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    if not _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
        return None
    surface = primary_surface_node(node)
    clip_height = float(surface.sizing.height or 0) if surface is not None else 0.0
    if clip_height <= 0:
        return None
    stack_width = node.sizing.width
    if node.stack_placement is not None and node.stack_placement.width is not None:
        stack_width = node.stack_placement.width
    if stack_width is None or stack_width <= 0:
        return None
    sorted_children = _sort_absolute_stack_children(node.children, is_layout_root=False)
    cta_children = [
        child
        for child in sorted_children
        if not (child.type == NodeType.TEXT and _is_footer_link_text_node(child))
    ]
    if surface is not None:
        cta_children = [child for child in cta_children if child.id != surface.id]
    footer_children = [
        child
        for child in sorted_children
        if child.type == NodeType.TEXT and _is_footer_link_text_node(child)
    ]
    if not cta_children or not footer_children:
        return None
    from ..emit import render_node_body  # lazy: avoid button→emit→button cycle
    cta_widgets = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=node,
            theme_variant=theme_variant,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
            cluster_vector_variant=cluster_vector_variant,
            skip_cluster_id=skip_cluster_id,
            responsive_enabled=responsive_enabled,
            design_artboard_width=design_artboard_width,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        for child in cta_children
    ]
    cta_body = ", ".join(cta_widgets)
    cta_stack = _wrap_button_stack(
        f"Stack(clipBehavior: Clip.hardEdge, children: [{cta_body}])",
        node,
        theme_variant=theme_variant,
    )
    parts = [
        (
            "Positioned(left: 0.0, top: 0.0, "
            f"width: {format_geometry_literal(stack_width)}, "
            f"height: {format_geometry_literal(clip_height)}, "
            f"child: {cta_stack})"
        ),
    ]
    for footer in footer_children:
        parts.append(
            render_node_body(
                footer,
                uses_svg=uses_svg,
                parent_type=NodeType.STACK,
                parent_node=node,
                theme_variant=theme_variant,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
                cluster_vector_variant=cluster_vector_variant,
                skip_cluster_id=skip_cluster_id,
                responsive_enabled=responsive_enabled,
                design_artboard_width=design_artboard_width,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            ),
        )
    return f"Stack(clipBehavior: Clip.none, children: [{', '.join(parts)}])"


__all__ = ["_try_render_cta_footer_split_stack"]
