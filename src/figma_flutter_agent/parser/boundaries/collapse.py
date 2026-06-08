"""Collapse decorative vector-heavy subtrees into SVG render boundaries."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.parser.boundaries.assets import render_boundary_asset_path
from figma_flutter_agent.parser.boundaries.heuristics import should_collapse_boundary
from figma_flutter_agent.parser.boundaries.ids import collect_descendant_figma_ids
from figma_flutter_agent.parser.boundaries.models import RenderBoundaryCollapseResult
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import CleanDesignTreeNode


def _pin_render_boundary_placement(
    node: CleanDesignTreeNode,
    *,
    parent_height: float | None,
) -> None:
    placement = node.stack_placement
    if placement is None:
        return
    height = placement.height or node.sizing.height
    if height is None or height <= 0:
        return
    top = placement.top
    if top is None and parent_height is not None and placement.bottom > 0:
        top = float(parent_height) - float(placement.bottom) - float(height)
    if top is None:
        top = node.offset_y
    rounded_top = round_geometry(top)
    node.stack_placement = placement.model_copy(
        update={
            "vertical": "TOP",
            "top": rounded_top if rounded_top is not None else top,
            "bottom": 0.0,
        },
    )


def _collapse_node(
    node: CleanDesignTreeNode,
    result: RenderBoundaryCollapseResult,
    *,
    parent_height: float | None,
) -> None:
    flattened = collect_descendant_figma_ids(node)
    node.children = []
    node.render_boundary = True
    node.flatten_figma_node_ids = flattened
    node.vector_asset_key = render_boundary_asset_path(node.id)
    node.vector_svg_has_filter = False
    _pin_render_boundary_placement(node, parent_height=parent_height)
    result.collapsed_count += 1
    result.boundary_node_ids = frozenset(set(result.boundary_node_ids) | {node.id})
    result.flattened_node_ids = frozenset(
        set(result.flattened_node_ids) | set(flattened)
    )


def _walk_and_collapse(
    node: CleanDesignTreeNode,
    result: RenderBoundaryCollapseResult,
    *,
    parent: CleanDesignTreeNode | None,
    screen_root: CleanDesignTreeNode,
    parent_height: float | None,
) -> None:
    if should_collapse_boundary(node, parent=parent, screen_root=screen_root):
        _collapse_node(node, result, parent_height=parent_height)
        return
    child_parent_height = node.sizing.height or parent_height
    for child in list(node.children):
        _walk_and_collapse(
            child,
            result,
            parent=node,
            screen_root=screen_root,
            parent_height=child_parent_height,
        )


def collapse_render_boundaries(
    root: CleanDesignTreeNode,
) -> RenderBoundaryCollapseResult:
    """Collapse decorative vector-heavy subtrees into single SVG boundaries."""
    result = RenderBoundaryCollapseResult()
    screen_height = root.sizing.height
    for child in list(root.children):
        _walk_and_collapse(
            child,
            result,
            parent=root,
            screen_root=root,
            parent_height=screen_height,
        )
    if result.collapsed_count:
        logger.info(
            "Render boundaries collapsed={} flattened_nodes={} boundaries={}",
            result.collapsed_count,
            len(result.flattened_node_ids),
            len(result.boundary_node_ids),
        )
    return result
