"""Hydrate ``GeometryFrame`` and ``TextMetricsFrame`` from Figma REST nodes."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.render_bounds import compute_render_bounds_expand
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeStyle,
    NodeType,
    StackPlacement,
    TextMetricsFrame,
)


def _bbox_rect(raw: dict[str, Any]) -> GeomRect | None:
    bbox = raw.get("absoluteBoundingBox")
    if not isinstance(bbox, dict):
        return None
    try:
        return GeomRect(
            x=float(bbox["x"]),
            y=float(bbox["y"]),
            width=float(bbox["width"]),
            height=float(bbox["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _paint_rect(raw: dict[str, Any], style: NodeStyle) -> GeomRect | None:
    bbox = raw.get("absoluteBoundingBox") or {}
    render = raw.get("absoluteRenderBounds") or {}
    expand = compute_render_bounds_expand(bbox, render)
    world = _bbox_rect(raw)
    if world is None:
        return None
    if expand is None:
        return world
    return GeomRect(
        x=world.x - (expand.left or 0.0),
        y=world.y - (expand.top or 0.0),
        width=world.width + (expand.left or 0.0) + (expand.right or 0.0),
        height=world.height + (expand.top or 0.0) + (expand.bottom or 0.0),
    )


def affine2_from_figma_node(raw: dict[str, Any]) -> Affine2:
    """Build ``Affine2`` from raw Figma ``relativeTransform`` (no polar loss)."""
    matrix = raw.get("relativeTransform")
    if not isinstance(matrix, list) or len(matrix) < 2:
        return Affine2()
    try:
        row0 = matrix[0]
        row1 = matrix[1]
        a, c, tx = float(row0[0]), float(row0[1]), float(row0[2])
        b, d, ty = float(row1[0]), float(row1[1]), float(row1[2])
    except (IndexError, TypeError, ValueError):
        return Affine2()
    return Affine2(a=a, b=b, c=c, d=d, tx=tx, ty=ty)


def _placement_aabb_from_node(node: CleanDesignTreeNode) -> GeomRect | None:
    placement = node.stack_placement
    if placement is None:
        return None
    width = placement.width if placement.width is not None else node.sizing.width
    height = placement.height if placement.height is not None else node.sizing.height
    if width is None or height is None:
        return None
    return GeomRect(
        x=placement.left,
        y=placement.top,
        width=width,
        height=height,
    )


def hydrate_geometry_frame(
    raw: dict[str, Any],
    style: NodeStyle,
    *,
    stack_placement: StackPlacement | None = None,
    sizing_width: float | None = None,
    sizing_height: float | None = None,
) -> GeometryFrame:
    """Parse immutable geometry frame without early coordinate rounding."""
    local = affine2_from_figma_node(raw)
    parsed_aabb = _bbox_rect(raw) or GeomRect()
    sizing = raw.get("absoluteBoundingBox") or {}
    layout_w = float(sizing.get("width") or parsed_aabb.width or sizing_width or 0.0)
    layout_h = float(sizing.get("height") or parsed_aabb.height or sizing_height or 0.0)
    intrinsic = GeomRect(width=layout_w, height=layout_h)
    layout_rect = GeomRect(
        x=local.tx,
        y=local.ty,
        width=layout_w,
        height=layout_h,
    )
    placement_aabb = None
    if stack_placement is not None:
        width = stack_placement.width if stack_placement.width is not None else layout_w
        height = (
            stack_placement.height if stack_placement.height is not None else layout_h
        )
        placement_aabb = GeomRect(
            x=stack_placement.left,
            y=stack_placement.top,
            width=width,
            height=height,
        )
    return GeometryFrame(
        local_transform=local,
        layout_rect=layout_rect,
        intrinsic_size=intrinsic,
        placement_origin=GeomRect(x=local.tx, y=local.ty),
        placement_aabb=placement_aabb,
        parsed_world_aabb=parsed_aabb,
        world_aabb=parsed_aabb,
        paint_rect=_paint_rect(raw, style),
    )


def hydrate_text_metrics_frame(
    node_type: NodeType,
    style: NodeStyle,
) -> TextMetricsFrame | None:
    """Build text metrics frame for TEXT nodes when line-box data exists."""
    if node_type != NodeType.TEXT:
        return None
    if (
        style.line_height is None
        and style.glyph_top_offset is None
        and style.glyph_height is None
    ):
        return None
    line_height_px = None
    if (
        style.line_height is not None
        and style.font_size is not None
        and style.font_size > 0
    ):
        line_height_px = style.line_height * style.font_size
    return TextMetricsFrame(
        line_height_px=line_height_px,
        glyph_top_offset=style.glyph_top_offset,
        glyph_height=style.glyph_height,
        font_size=style.font_size,
        strut_height_ratio=style.line_height,
        baseline_verifiable=style.font_size is not None and style.font_size > 0,
    )


def attach_geometry_frames(
    node: CleanDesignTreeNode,
    raw: dict[str, Any],
) -> CleanDesignTreeNode:
    """Attach geometry and text metric frames to a parsed clean-tree node."""
    geometry = hydrate_geometry_frame(
        raw,
        node.style,
        stack_placement=node.stack_placement,
        sizing_width=node.sizing.width,
        sizing_height=node.sizing.height,
    )
    text_metrics = hydrate_text_metrics_frame(node.type, node.style)
    return node.model_copy(
        update={
            "geometry_frame": geometry,
            "text_metrics_frame": text_metrics,
        }
    )
