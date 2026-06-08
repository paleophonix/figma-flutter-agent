"""Layout slot primitives for geometry planning."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.affine import (
    has_non_trivial_linear,
    is_axis_aligned,
    linear_affine,
    requires_raster_tier,
)
from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.schemas import (
    Affine2,
    AxisPins,
    CleanDesignTreeNode,
    GeomRect,
    LayerClass,
    LayoutBackend,
    NodeType,
)

_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
    }
)


def layer_class(node: CleanDesignTreeNode) -> LayerClass:
    if node.type in _INTERACTIVE_TYPES:
        return LayerClass.INTERACTIVE
    if stack_interaction_kind(node) == "button":
        return LayerClass.INTERACTIVE
    return LayerClass.STATIC


def stack_pins_from_placement(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
) -> AxisPins | None:
    frame = node.geometry_frame
    placement = node.stack_placement
    local = frame.local_transform if frame is not None else Affine2()
    if frame is not None and (
        has_non_trivial_linear(linear_affine(local)) or not is_axis_aligned(local)
    ):
        intrinsic = frame.intrinsic_size
        return AxisPins(
            free_horizontal="left",
            free_vertical="top",
            left=local.tx,
            top=local.ty,
            width=intrinsic.width if intrinsic.width > 0 else None,
            height=intrinsic.height if intrinsic.height > 0 else None,
        )
    if placement is None and frame is not None and frame.placement_aabb is not None:
        aabb = frame.placement_aabb
        placement_left = aabb.x
        placement_top = aabb.y
        placement_width = aabb.width
        placement_height = aabb.height
    elif placement is not None:
        placement_left = placement.left
        placement_top = placement.top
        placement_width = placement.width
        placement_height = placement.height
    elif frame is not None and frame.placement_origin is not None:
        origin = frame.placement_origin
        intrinsic = frame.intrinsic_size
        return AxisPins(
            free_horizontal="left",
            free_vertical="top",
            left=origin.x,
            top=origin.y,
            width=intrinsic.width if intrinsic.width > 0 else None,
            height=intrinsic.height if intrinsic.height > 0 else None,
        )
    else:
        return None

    free_h: str | None = "left"
    if placement is not None and placement.horizontal == "RIGHT":
        free_h = "right"
    elif placement is not None and (
        placement.horizontal in {"LEFT_RIGHT", "SCALE"}
        or placement.horizontal == "CENTER"
        and placement.width is not None
    ):
        free_h = "width"
    free_v: str | None = "top"
    if placement is not None and placement.vertical == "BOTTOM":
        free_v = "bottom"
    elif placement is not None and (
        placement.vertical in {"TOP_BOTTOM", "SCALE"}
        or placement.vertical == "CENTER"
        and placement.height is not None
    ):
        free_v = "height"
    _ = parent_type
    return AxisPins(
        free_horizontal=free_h,  # type: ignore[arg-type]
        free_vertical=free_v,  # type: ignore[arg-type]
        left=placement_left,
        top=placement_top,
        right=placement.right if placement else None,
        bottom=placement.bottom if placement else None,
        width=placement_width,
        height=placement_height,
    )


def slot_rect(node: CleanDesignTreeNode) -> GeomRect:
    frame = node.geometry_frame
    if frame is not None:
        intrinsic = frame.intrinsic_size
        if intrinsic.width > 0 or intrinsic.height > 0:
            origin = frame.placement_aabb or frame.placement_origin
            return GeomRect(
                x=origin.x if origin is not None else 0.0,
                y=origin.y if origin is not None else 0.0,
                width=intrinsic.width,
                height=intrinsic.height,
            )
    placement = node.stack_placement
    if (
        placement is not None
        and placement.width is not None
        and placement.height is not None
    ):
        return GeomRect(
            x=placement.left,
            y=placement.top,
            width=placement.width,
            height=placement.height,
        )
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    return GeomRect(width=width, height=height)


def resolve_backend(node: CleanDesignTreeNode, *, local: Affine2) -> LayoutBackend:
    if node.render_boundary:
        return LayoutBackend.BOUNDARY
    if node.scroll_axis != "none":
        return LayoutBackend.SCROLL
    if requires_raster_tier(local):
        return LayoutBackend.BOUNDARY
    if node.type in {NodeType.ROW, NodeType.COLUMN, NodeType.WRAP}:
        return LayoutBackend.FLEX
    return LayoutBackend.STACK
