"""Figma node tree to CleanDesignTree conversion."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.errors import ParseError
from figma_flutter_agent.parser.accessibility import derive_accessibility_label
from figma_flutter_agent.parser.components import (
    extract_component_variant,
    resolve_semantic_node_type,
)
from figma_flutter_agent.parser.dedup.clusters import (
    assign_component_clusters,
    assign_structural_clusters,
    merge_cluster_summaries,
)
from figma_flutter_agent.parser.dedup.instances import (
    DedupResult,
    collect_component_instances,
)
from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree
from figma_flutter_agent.parser.dev_mode_css import DevModeCssDump
from figma_flutter_agent.parser.geometry import enrich_clean_tree_from_geometry
from figma_flutter_agent.parser.geometry_frames import attach_geometry_frames
from figma_flutter_agent.parser.layout import (
    adjust_sizing_for_visible_children,
    enforce_fixed_sizing_for_stack_and_button,
    extract_alignment,
    extract_grid_column_count,
    extract_grid_gaps,
    extract_layout_position,
    extract_padding,
    extract_scroll_axis,
    extract_sizing,
    extract_stack_placement,
    infer_container_type,
    promote_flex_hosts_with_absolute_children,
    refine_text_stack_placement,
)
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.parser.richtext import extract_text_span_parts
from figma_flutter_agent.parser.text_normalize import normalize_figma_characters
from figma_flutter_agent.parser.tree_node import (
    extract_rotation_degrees,
    extract_rotation_rad,
    extract_style,
    figma_layout_node,
    infer_leaf_type,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, TextSpanPart


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
    dev_mode_dump: DevModeCssDump | None = None,
    dev_mode_css_override: bool = False,
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
                dev_mode_dump=dev_mode_dump,
                dev_mode_css_override=dev_mode_css_override,
            )
        )
    ]

    has_layout = node.get("layoutMode") not in (None, "NONE") or bool(children)
    if has_layout and children:
        node_type = infer_container_type(figma_layout_node(node))
        semantic_type = resolve_semantic_node_type(node, components, component_sets)
        if semantic_type is not None and semantic_type != NodeType.CONTAINER:
            node_type = semantic_type
    else:
        node_type = infer_leaf_type(node, components=components, component_sets=component_sets)
    if node_type == NodeType.STACK and not children:
        node_type = NodeType.CONTAINER

    node_name = node.get("name") or node["id"]
    raw_text = node.get("characters") if node.get("type") == "TEXT" else None
    text = normalize_figma_characters(raw_text) if raw_text else None
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
    node_style = extract_style(
        node,
        published_styles=published_styles,
        style_paint_index=style_paint_index,
        dev_mode_dump=dev_mode_dump,
        dev_mode_css_override=dev_mode_css_override,
    )
    parent_type = infer_container_type(figma_layout_node(parent)) if parent is not None else None
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

    sizing = extract_sizing(node, parent=parent)
    visible_raw_children = [
        child
        for child in children_raw
        if isinstance(child, dict) and child.get("visible") is not False
    ]
    sizing = adjust_sizing_for_visible_children(
        node,
        sizing,
        visible_children=visible_raw_children,
    )
    sizing = enforce_fixed_sizing_for_stack_and_button(
        node_type,
        sizing,
        stack_placement=stack_placement,
        figma_node=node,
    )

    return attach_geometry_frames(
        CleanDesignTreeNode(
        id=node["id"],
        name=node_name,
        type=node_type,
        padding=extract_padding(node),
        spacing=round_geometry(float(node.get("itemSpacing") or 0)) or 0.0,
        sizing=sizing,
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
        rotation=extract_rotation_degrees(node),
        rotation_rad=extract_rotation_rad(node),
        ),
        node,
        parent_raw=parent,
    )


def build_clean_tree(
    root: dict[str, Any],
    *,
    published_styles: dict[str, dict[str, Any]] | None = None,
    components: dict[str, dict[str, Any]] | None = None,
    component_sets: dict[str, dict[str, Any]] | None = None,
    style_paint_index: dict[str, dict[str, Any]] | None = None,
    dev_mode_dump: DevModeCssDump | None = None,
    dev_mode_css_override: bool = False,
) -> tuple[CleanDesignTreeNode, float, DedupResult, dict[str, int]]:
    """Convert a Figma subtree into a clean design tree.

    Args:
        root: Figma node dictionary for the selected frame.
        published_styles: Optional published styles map from the Styles API.
        components: Optional published components map from the Components API.
        component_sets: Optional published component sets map from the Components API.
        style_paint_index: Optional published style id to style node document map.
        dev_mode_dump: Optional pre-loaded Dev Mode CSS dump.  When provided,
            each node's ``NodeStyle.css_properties`` is enriched with the CSS
            values from the dump for its Figma id.
        dev_mode_css_override: When ``True``, dump values overwrite existing
            ``css_properties`` (``dev_mode_inspect`` source mode).  When
            ``False`` (``hybrid``), existing values win on key conflicts.

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
        dev_mode_dump=dev_mode_dump,
        dev_mode_css_override=dev_mode_css_override,
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
    prune_generation_layout_tree(tree)
    enrich_clean_tree_from_geometry(tree)
    from figma_flutter_agent.parser.boundaries.collapse import collapse_render_boundaries

    collapse_render_boundaries(tree)
    tree = promote_flex_hosts_with_absolute_children(tree)
    from figma_flutter_agent.parser.stack_paint import apply_stack_paint_order_to_clean_tree

    tree = apply_stack_paint_order_to_clean_tree(tree)
    ratio = absolute_count[0] / total_count[0] if total_count[0] else 0.0
    return tree, ratio, dedup, cluster_summary
