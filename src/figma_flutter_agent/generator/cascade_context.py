"""Cascade context helpers for geometry planning (WP-1)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.affine import (
    compose_affine,
    has_non_trivial_linear,
    is_axis_aligned,
    linear_affine,
)
from figma_flutter_agent.schemas import Affine2, CascadeContext, CleanDesignTreeNode, GeomRect


def cascade_context_from_node(
    node: CleanDesignTreeNode,
    *,
    parent_world: Affine2 | None = None,
) -> CascadeContext | None:
    """Build cascade context from parsed geometry frames (single world/local space)."""
    frame = node.geometry_frame
    if frame is None:
        return None
    local = frame.local_transform
    world = compose_affine(parent_world, local) if parent_world is not None else local
    intrinsic = frame.intrinsic_size
    linear = linear_affine(local)
    if has_non_trivial_linear(linear) or not is_axis_aligned(local):
        pivot_x, pivot_y = local.tx, local.ty
    elif frame.placement_origin is not None:
        pivot_x, pivot_y = frame.placement_origin.x, frame.placement_origin.y
    else:
        pivot_x, pivot_y = local.tx, local.ty
    return CascadeContext(
        world=world,
        local=local,
        pivot_x=pivot_x,
        pivot_y=pivot_y,
        intrinsic_size=intrinsic,
    )


def layout_slot_from_stack_placement(
    node: CleanDesignTreeNode,
) -> GeomRect | None:
    """Legacy adapter: placement corner from stack pins or local origin."""
    frame = node.geometry_frame
    if frame is not None:
        local = frame.local_transform
        linear = linear_affine(local)
        if has_non_trivial_linear(linear) or not is_axis_aligned(local):
            intrinsic = frame.intrinsic_size
            return GeomRect(
                x=local.tx,
                y=local.ty,
                width=intrinsic.width,
                height=intrinsic.height,
            )
    placement = node.stack_placement
    if placement is not None:
        width = placement.width if placement.width is not None else node.sizing.width
        height = placement.height if placement.height is not None else node.sizing.height
        if width is not None and height is not None:
            return GeomRect(x=placement.left, y=placement.top, width=width, height=height)
    if frame is None:
        return None
    intrinsic = frame.intrinsic_size
    origin = frame.placement_origin
    if origin is not None:
        return GeomRect(
            x=origin.x,
            y=origin.y,
            width=intrinsic.width,
            height=intrinsic.height,
        )
    return GeomRect(width=intrinsic.width, height=intrinsic.height)
