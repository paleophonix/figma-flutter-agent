"""Figma node tree to CleanDesignTree conversion."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.errors import ParseError
from figma_flutter_agent.parser.accessibility import derive_accessibility_label
from figma_flutter_agent.parser.components import (
    extract_component_variant,
    infer_semantic_type_from_figma_overlay,
    resolve_semantic_node_type,
)
from figma_flutter_agent.parser.dedup import (
    DedupResult,
    assign_component_clusters,
    assign_structural_clusters,
    collect_component_instances,
    merge_cluster_summaries,
)
from figma_flutter_agent.parser.layout import (
    extract_alignment,
    extract_grid_column_count,
    extract_grid_gaps,
    extract_layout_position,
    extract_padding,
    extract_scroll_axis,
    extract_sizing,
    extract_stack_placement,
    infer_container_type,
    refine_text_stack_placement,
)
from figma_flutter_agent.parser.richtext import extract_text_span_parts
from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.parser.tokens import rgba_to_argb_hex
from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_style,
    resolve_font_weight,
    resolve_letter_spacing,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, TextSpanPart


def _figma_layout_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a node view for layout inference (spec §7.1).

    SECTION is treated as FRAME (Auto Layout). GROUP keeps type GROUP but maps to STACK
    in ``infer_container_type`` (classic positioning, layoutMode NONE).
    """
    if node.get("type") == "SECTION":
        return {**node, "type": "FRAME"}
    return node


def _infer_leaf_type(
    node: dict[str, Any],
    *,
    components: dict[str, dict[str, Any]] | None = None,
    component_sets: dict[str, dict[str, Any]] | None = None,
) -> NodeType:
    semantic_type = resolve_semantic_node_type(node, components, component_sets)
    if semantic_type is not None:
        return semantic_type

    overlay_type = infer_semantic_type_from_figma_overlay(node)
    if overlay_type is not None:
        return overlay_type

    node_type = node.get("type")
    name = (node.get("name") or "").lower()
    if node_type == "TEXT":
        return NodeType.TEXT
    if node_type in {"VECTOR", "BOOLEAN_OPERATION"}:
        return NodeType.VECTOR
    if node_type == "RECTANGLE" and any(
        fill.get("type") == "IMAGE" for fill in (node.get("fills") or [])
    ):
        return NodeType.IMAGE

    # Unpublished instances: avoid layer-name heuristics when Components API data exists.
    if node_type == "INSTANCE" and node.get("componentId") and components:
        return NodeType.CONTAINER

    if "input" in name:
        return NodeType.INPUT
    if "button" in name or (node_type == "INSTANCE" and "btn" in name):
        return NodeType.BUTTON
    if "card" in name:
        return NodeType.CARD
    return NodeType.CONTAINER


def _extract_style(
    node: dict[str, Any],
    *,
    published_styles: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
) -> NodeStyle:
    style = NodeStyle()
    fills = node.get("fills") or []
    if node.get("type") != "TEXT":
        for fill in fills:
            if fill.get("visible") is False:
                continue
            if fill.get("type") == "SOLID" and fill.get("color"):
                style.background_color = rgba_to_argb_hex(fill["color"])
                break

    if node.get("cornerRadius") is not None:
        style.border_radius = float(node["cornerRadius"])

    if node.get("type") == "TEXT":
        text_style = node.get("style") or {}
        if text_style.get("fontSize") is not None:
            style.font_size = float(text_style["fontSize"])
        resolved_weight = resolve_font_weight(text_style)
        if resolved_weight is not None:
            style.font_weight = resolved_weight
        resolved_family = resolve_font_family(text_style)
        if resolved_family is not None:
            style.font_family = resolved_family
        resolved_style = resolve_font_style(text_style)
        if resolved_style is not None:
            style.font_style = resolved_style
        align = text_style.get("textAlignHorizontal")
        if isinstance(align, str) and align.strip():
            style.text_align = align.strip().upper()
        line_height_px = text_style.get("lineHeightPx")
        font_size = text_style.get("fontSize")
        if line_height_px is not None and font_size:
            style.line_height = float(line_height_px) / float(font_size)
        elif text_style.get("lineHeightPercentFontSize") is not None:
            style.line_height = float(text_style["lineHeightPercentFontSize"]) / 100.0
        resolved_spacing = resolve_letter_spacing(text_style, font_size=style.font_size)
        if resolved_spacing is not None:
            style.letter_spacing = resolved_spacing
        bbox = node.get("absoluteBoundingBox") or {}
        render = node.get("absoluteRenderBounds") or {}
        if bbox.get("y") is not None and render.get("y") is not None:
            style.glyph_top_offset = round(float(render["y"]) - float(bbox["y"]), 3)
        if render.get("height") is not None:
            style.glyph_height = round(float(render["height"]), 3)
        for fill in fills:
            if fill.get("visible") is False:
                continue
            if fill.get("type") == "SOLID" and fill.get("color"):
                style.text_color = rgba_to_argb_hex(fill["color"])
                break

    return enrich_node_style(
        node,
        style,
        published_styles=published_styles,
        style_paint_index=style_paint_index,
    )


def _convert_node(
    node: dict[str, Any],
    dedup_refs: dict[str, str],
    *,
    parent: dict[str, Any] | None = None,
    absolute_count: list[int],
    total_count: list[int],
    published_styles: dict[str, dict[str, Any]] | None = None,
    components: dict[str, dict[str, Any]] | None = None,
    component_sets: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
) -> CleanDesignTreeNode | None:
    if node.get("visible") is False:
        return None

    total_count[0] += 1
    if node.get("layoutPositioning") == "ABSOLUTE":
        absolute_count[0] += 1

    children_raw = node.get("children") or []
    children = [
        converted
        for child in children_raw
        if (
            converted := _convert_node(
                child,
                dedup_refs,
                parent=node,
                absolute_count=absolute_count,
                total_count=total_count,
                published_styles=published_styles,
                components=components,
                component_sets=component_sets,
                style_paint_index=style_paint_index,
            )
        )
    ]

    has_layout = node.get("layoutMode") not in (None, "NONE") or bool(children)
    if has_layout and children:
        node_type = infer_container_type(_figma_layout_node(node))
        semantic_type = resolve_semantic_node_type(node, components, component_sets)
        if semantic_type is not None and semantic_type != NodeType.CONTAINER:
            node_type = semantic_type
    else:
        node_type = _infer_leaf_type(node, components=components, component_sets=component_sets)
    if node_type == NodeType.STACK and not children:
        node_type = NodeType.CONTAINER

    node_name = node.get("name") or node["id"]
    text = node.get("characters") if node.get("type") == "TEXT" else None
    text_spans: list[TextSpanPart] = []
    if node.get("type") == "TEXT":
        spans = extract_text_span_parts(node)
        if spans:
            text_spans = spans
    accessibility_label = derive_accessibility_label(
        node_name=node_name,
        node_type=node_type,
        text=text,
        children=children,
    )
    layout_positioning, offset_x, offset_y = extract_layout_position(node, parent)
    node_style = _extract_style(
        node,
        published_styles=published_styles,
        style_paint_index=style_paint_index,
    )
    parent_type = infer_container_type(_figma_layout_node(parent)) if parent is not None else None
    stack_placement = extract_stack_placement(node, parent) if parent is not None else None
    stack_placement = refine_text_stack_placement(
        node_type,
        node_style,
        parent_type,
        stack_placement,
    )
    grid_column_count: int | None = None
    grid_row_gap: float | None = None
    grid_column_gap: float | None = None
    if node_type == NodeType.GRID:
        grid_column_count = extract_grid_column_count(node, child_count=len(children))
        grid_row_gap, grid_column_gap = extract_grid_gaps(node)

    return CleanDesignTreeNode(
        id=node["id"],
        name=node_name,
        type=node_type,
        padding=extract_padding(node),
        spacing=float(node.get("itemSpacing") or 0),
        sizing=extract_sizing(node, parent=parent),
        alignment=extract_alignment(node),
        style=node_style,
        text=text,
        text_spans=text_spans,
        component_ref=dedup_refs.get(node["id"]),
        variant=extract_component_variant(node, components),
        accessibility_label=accessibility_label,
        accessibility_hint=node_name
        if node_type
        in {
            NodeType.INPUT,
            NodeType.BUTTON,
            NodeType.CHECKBOX,
            NodeType.SWITCH,
            NodeType.RADIO,
            NodeType.RADIO_GROUP,
            NodeType.DROPDOWN,
            NodeType.DIALOG,
            NodeType.SLIDER,
            NodeType.CAROUSEL,
        }
        else None,
        layout_positioning=layout_positioning,
        offset_x=offset_x,
        offset_y=offset_y,
        stack_placement=stack_placement,
        scroll_axis=extract_scroll_axis(node),
        grid_column_count=grid_column_count,
        grid_row_gap=grid_row_gap,
        grid_column_gap=grid_column_gap,
        children=children,
        rotation=float(node["rotation"]) if node.get("rotation") is not None else None,
    )


def build_clean_tree(
    root: dict[str, Any],
    *,
    published_styles: dict[str, dict[str, Any]] | None = None,
    components: dict[str, dict[str, Any]] | None = None,
    component_sets: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[CleanDesignTreeNode, float, DedupResult, dict[str, int]]:
    """Convert a Figma subtree into a clean design tree.

    Args:
        root: Figma node dictionary for the selected frame.
        published_styles: Optional published styles map from the Styles API.
        components: Optional published components map from the Components API.
        component_sets: Optional published component sets map from the Components API.
        style_paint_index: Optional published style id to style node document map.

    Returns:
        Tuple of clean design tree, absolute-position ratio (0-1), dedup result,
        and structural cluster summary.
    """
    dedup = collect_component_instances(root)
    absolute_count = [0]
    total_count = [0]
    tree = _convert_node(
        root,
        dedup.component_refs,
        parent=None,
        absolute_count=absolute_count,
        total_count=total_count,
        published_styles=published_styles,
        components=components,
        component_sets=component_sets,
        style_paint_index=style_paint_index,
    )
    if tree is None:
        raise ParseError("Selected node is not visible or cannot be converted")
    structural_summary = assign_structural_clusters(tree)
    component_summary = assign_component_clusters(
        tree,
        dedup,
        min_count=2,
    )
    cluster_summary = merge_cluster_summaries(structural_summary, component_summary)
    ratio = absolute_count[0] / total_count[0] if total_count[0] else 0.0
    return tree, ratio, dedup, cluster_summary
