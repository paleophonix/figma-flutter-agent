"""Hydrate ``GeometryFrame`` and ``TextMetricsFrame`` from Figma REST nodes."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.geometry import transform_context_from_figma_node
from figma_flutter_agent.parser.render_bounds import compute_render_bounds_expand
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeomRect,
    GeometryFrame,
    NodeStyle,
    NodeType,
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
    """Build ``Affine2`` from Figma ``relativeTransform`` or identity."""
    ctx = transform_context_from_figma_node(raw)
    if ctx is None:
        return Affine2()
    rotation = ctx.rotation_rad or 0.0
    import math

    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    sx = ctx.scale_x
    sy = ctx.scale_y
    return Affine2(
        a=cos_r * sx,
        b=sin_r * sx,
        c=-sin_r * sy,
        d=cos_r * sy,
        tx=ctx.translate_x,
        ty=ctx.translate_y,
    )


def hydrate_geometry_frame(raw: dict[str, Any], style: NodeStyle) -> GeometryFrame:
    """Parse immutable geometry frame without early coordinate rounding."""
    local = affine2_from_figma_node(raw)
    world_aabb = _bbox_rect(raw) or GeomRect()
    sizing = raw.get("absoluteBoundingBox") or {}
    layout_w = float(sizing.get("width") or world_aabb.width or 0.0)
    layout_h = float(sizing.get("height") or world_aabb.height or 0.0)
    layout_rect = GeomRect(
        x=local.tx,
        y=local.ty,
        width=layout_w,
        height=layout_h,
    )
    return GeometryFrame(
        local_transform=local,
        layout_rect=layout_rect,
        world_aabb=world_aabb,
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
    if style.line_height is not None and style.font_size is not None and style.font_size > 0:
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
    geometry = hydrate_geometry_frame(raw, node.style)
    text_metrics = hydrate_text_metrics_frame(node.type, node.style)
    return node.model_copy(
        update={
            "geometry_frame": geometry,
            "text_metrics_frame": text_metrics,
        }
    )
