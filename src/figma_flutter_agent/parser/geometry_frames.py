"""Hydrate ``GeometryFrame`` and ``TextMetricsFrame`` from Figma REST nodes."""

from __future__ import annotations

from typing import Any

from loguru import logger

from figma_flutter_agent.generator.geometry.affine import (
    aabb_residual,
    expand_aabb,
    geom_epsilon,
    has_non_trivial_linear,
    is_axis_aligned,
    linear_affine,
)
from figma_flutter_agent.parser.render_bounds import compute_render_bounds_expand
from figma_flutter_agent.parser.text_metrics import hydrate_text_metrics_frame
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeStyle,
    StackPlacement,
)


def _bbox_rect(raw: dict[str, Any]) -> GeomRect | None:
    bbox = raw.get("absoluteBoundingBox")
    if not isinstance(bbox, dict):
        return None
    try:
        width = float(bbox["width"])
        height = float(bbox["height"])
    except (KeyError, TypeError, ValueError):
        return None
    try:
        x = float(bbox.get("x", 0.0))
        y = float(bbox.get("y", 0.0))
    except (TypeError, ValueError):
        return None
    return GeomRect(x=x, y=y, width=width, height=height)


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


def affine2_from_figma_node(
    raw: dict[str, Any],
    *,
    node_id: str | None = None,
) -> Affine2:
    """Build ``Affine2`` from raw Figma ``relativeTransform`` (no polar loss)."""
    from figma_flutter_agent.errors import ParseError

    matrix = raw.get("relativeTransform")
    label = node_id or str(raw.get("id", "?"))
    if matrix is None:
        return Affine2()
    if not isinstance(matrix, list) or len(matrix) < 2:
        raise ParseError(f"malformed relativeTransform at node {label}")
    try:
        row0 = matrix[0]
        row1 = matrix[1]
        a, c, tx = float(row0[0]), float(row0[1]), float(row0[2])
        b, d, ty = float(row1[0]), float(row1[1]), float(row1[2])
    except (IndexError, TypeError, ValueError) as exc:
        raise ParseError(f"malformed relativeTransform at node {label}") from exc
    return Affine2(a=a, b=b, c=c, d=d, tx=tx, ty=ty)


def _figma_local_size(raw: dict[str, Any]) -> tuple[float, float] | None:
    """Return Figma node-local width/height from ``size`` when present."""
    size = raw.get("size")
    if not isinstance(size, dict):
        return None
    try:
        return float(size["x"]), float(size["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _local_intrinsic_size_from_aabb(
    linear: Affine2,
    aabb_w: float,
    aabb_h: float,
) -> tuple[float, float]:
    """Recover local (w, h) from axis-aligned bounds and linear part."""
    linear_only = Affine2(a=linear.a, b=linear.b, c=linear.c, d=linear.d, tx=0.0, ty=0.0)
    if aabb_w <= geom_epsilon() or aabb_h <= geom_epsilon():
        return aabb_w, aabb_h

    target = GeomRect(width=aabb_w, height=aabb_h)
    a_abs = abs(linear.a)
    b_abs = abs(linear.b)
    c_abs = abs(linear.c)
    d_abs = abs(linear.d)
    det = a_abs * d_abs - c_abs * b_abs
    if abs(det) > geom_epsilon():
        candidate_w = (aabb_w * d_abs - aabb_h * c_abs) / det
        candidate_h = (aabb_h * a_abs - aabb_w * b_abs) / det
        if candidate_w > geom_epsilon() and candidate_h > geom_epsilon():
            expanded = expand_aabb(linear_only, candidate_w, candidate_h)
            residual = aabb_residual(target, GeomRect(width=expanded.width, height=expanded.height))
            if residual <= geom_epsilon():
                return candidate_w, candidate_h

    best_w = aabb_w
    best_h = aabb_h
    best_residual = float("inf")
    for index in range(1, 5000):
        aspect = index / 50.0
        unit = expand_aabb(linear_only, aspect, 1.0)
        if unit.width <= geom_epsilon() or unit.height <= geom_epsilon():
            continue
        scale_w = aabb_w / unit.width
        scale_h = aabb_h / unit.height
        for scale in (scale_w, scale_h, (scale_w + scale_h) / 2.0):
            w_final = aspect * scale
            h_final = scale
            expanded = expand_aabb(linear_only, w_final, h_final)
            residual = aabb_residual(target, GeomRect(width=expanded.width, height=expanded.height))
            if residual < best_residual:
                best_residual = residual
                best_w = w_final
                best_h = h_final

    if best_residual > geom_epsilon():
        logger.warning(
            "Local size recovery from AABB residual {:.3f}px; using AABB dimensions",
            best_residual,
        )
        return aabb_w, aabb_h
    return best_w, best_h


def _local_intrinsic_size(
    raw: dict[str, Any],
    linear: Affine2,
    aabb_w: float,
    aabb_h: float,
) -> tuple[float, float]:
    """Local intrinsic width/height for transformed nodes (size field or 2x2 fallback)."""
    explicit = _figma_local_size(raw)
    if explicit is not None:
        return explicit
    return _local_intrinsic_size_from_aabb(linear, aabb_w, aabb_h)


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
    parent_raw: dict[str, Any] | None = None,
) -> GeometryFrame:
    """Parse immutable geometry frame without early coordinate rounding."""
    local = affine2_from_figma_node(raw, node_id=str(raw.get("id", "")))
    parent_delta = _translation_from_parent_bbox(raw, parent_raw)
    if parent_delta is not None and is_axis_aligned(local):
        local = local.model_copy(update={"tx": parent_delta[0], "ty": parent_delta[1]})
    parsed_aabb = _bbox_rect(raw) or GeomRect()
    sizing = raw.get("absoluteBoundingBox") or {}
    layout_w = float(sizing.get("width") or parsed_aabb.width or sizing_width or 0.0)
    layout_h = float(sizing.get("height") or parsed_aabb.height or sizing_height or 0.0)
    linear = linear_affine(local)
    transformed = has_non_trivial_linear(linear) or not is_axis_aligned(local)
    if transformed:
        local_w, local_h = _local_intrinsic_size(raw, linear, layout_w, layout_h)
        intrinsic = GeomRect(width=local_w, height=local_h)
        layout_rect = GeomRect(x=local.tx, y=local.ty, width=local_w, height=local_h)
        origin_x, origin_y = local.tx, local.ty
        derived_aabb = expand_aabb(local, local_w, local_h)
        world_aabb = parsed_aabb if parsed_aabb.width > 0 else derived_aabb
    else:
        intrinsic = GeomRect(width=layout_w, height=layout_h)
        expanded_local = expand_aabb(local, layout_w, layout_h)
        layout_rect = GeomRect(
            x=expanded_local.x,
            y=expanded_local.y,
            width=layout_w,
            height=layout_h,
        )
        origin_x = stack_placement.left if stack_placement is not None else expanded_local.x
        origin_y = stack_placement.top if stack_placement is not None else expanded_local.y
        world_aabb = parsed_aabb
    placement_aabb = None
    if stack_placement is not None and not transformed:
        width = stack_placement.width if stack_placement.width is not None else layout_w
        height = stack_placement.height if stack_placement.height is not None else layout_h
        placement_aabb = GeomRect(
            x=stack_placement.left,
            y=stack_placement.top,
            width=width,
            height=height,
        )
        origin_x = placement_aabb.x
        origin_y = placement_aabb.y
    return GeometryFrame(
        local_transform=local,
        layout_rect=layout_rect,
        intrinsic_size=intrinsic,
        placement_origin=GeomRect(x=origin_x, y=origin_y),
        placement_aabb=placement_aabb,
        parsed_world_aabb=parsed_aabb,
        world_aabb=world_aabb,
        paint_rect=_paint_rect(raw, style),
    )


def _translation_from_parent_bbox(
    raw: dict[str, Any],
    parent_raw: dict[str, Any] | None,
) -> tuple[float, float] | None:
    """Parent-relative translation when Figma omits ``relativeTransform``."""
    if parent_raw is None or raw.get("relativeTransform") is not None:
        return None
    node_bounds = raw.get("absoluteBoundingBox") or {}
    parent_bounds = parent_raw.get("absoluteBoundingBox") or {}
    try:
        return (
            float(node_bounds["x"]) - float(parent_bounds["x"]),
            float(node_bounds["y"]) - float(parent_bounds["y"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def attach_geometry_frames(
    node: CleanDesignTreeNode,
    raw: dict[str, Any],
    *,
    parent_raw: dict[str, Any] | None = None,
) -> CleanDesignTreeNode:
    """Attach geometry and text metric frames to a parsed clean-tree node."""
    geometry = hydrate_geometry_frame(
        raw,
        node.style,
        stack_placement=node.stack_placement,
        sizing_width=node.sizing.width,
        sizing_height=node.sizing.height,
        parent_raw=parent_raw,
    )
    text_metrics = hydrate_text_metrics_frame(node.type, node.style)
    return node.model_copy(
        update={
            "geometry_frame": geometry,
            "text_metrics_frame": text_metrics,
        }
    )
