"""Stack placement, Positioned field emitters, and layout-slot wrappers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import (
    normalize_box_constraints,
    wrap_repaint_boundary,
)
from figma_flutter_agent.generator.render_units import snap_to_device_pixel
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import (
    AxisPins,
    CleanDesignTreeNode,
    NodeType,
    SizingMode,
    StackPlacement,
    WrapKind,
)

from .flex_sizing import _unwrap_flex_parent_data_wrapper
from .shared import _snap_device_pixels_ctx


def _stack_has_bottom_anchored_child(node: CleanDesignTreeNode) -> bool:
    """Return True when the stack pins chrome to the bottom edge (FID-21)."""
    for child in node.children:
        placement = child.stack_placement
        if placement is not None:
            if placement.vertical == "BOTTOM":
                return True
            if child.type == NodeType.BOTTOM_NAV and placement.bottom is not None:
                return True
    return False


def _should_pin_bottom(
    placement: StackPlacement,
    *,
    parent_height: float | None,
) -> bool:
    """Return True when a positioned child should use ``bottom:`` not ``top:``."""
    if placement.vertical == "BOTTOM":
        return True
    if (
        parent_height is not None
        and parent_height > 0
        and placement.top is not None
        and placement.height is not None
        and placement.height > 0
    ):
        return placement.top + placement.height >= parent_height - 2.0
    return False


def _resolved_bottom_offset(
    placement: StackPlacement,
    *,
    parent_height: float | None,
) -> float:
    """Resolve a bottom inset for bottom-anchored stack children."""
    if placement.bottom is not None and placement.bottom > 0:
        return float(placement.bottom)
    if (
        parent_height is not None
        and parent_height > 0
        and placement.top is not None
        and placement.height is not None
        and placement.height > 0
    ):
        return max(
            0.0, float(parent_height) - float(placement.top) - float(placement.height)
        )
    return 0.0


def _positioned_fields(
    placement: StackPlacement,
    *,
    render_boundary: bool = False,
    parent_height: float | None = None,
) -> list[str]:
    """Map Figma constraints to Positioned constructor fields.

    Flutter ``Positioned`` allows at most two of ``left``/``right``/``width`` (and
    ``top``/``bottom``/``height``). SCALE pins use explicit ``width``/``height`` when known.
    """

    def _g(value: float) -> str:
        if _snap_device_pixels_ctx.get():
            value = snap_to_device_pixel(value)
        return format_geometry_literal(value)

    fields: list[str] = []
    horizontal = placement.horizontal
    vertical = "TOP" if render_boundary else placement.vertical

    if horizontal == "LEFT":
        fields.append(f"left: {_g(placement.left)}")
        if placement.width is not None and placement.width > 0:
            fields.append(f"width: {_g(placement.width)}")
    elif horizontal == "RIGHT":
        fields.append(f"right: {_g(placement.right)}")
        if placement.width is not None and placement.width > 0:
            fields.append(f"width: {_g(placement.width)}")
    elif horizontal == "CENTER":
        fields.append(f"left: {_g(placement.left)}")
        if placement.width is not None and placement.width > 0:
            fields.append(f"width: {_g(placement.width)}")
    elif horizontal == "LEFT_RIGHT":
        fields.append(f"left: {_g(placement.left)}")
        fields.append(f"right: {_g(placement.right)}")
    elif horizontal == "SCALE":
        fields.append(f"left: {_g(placement.left)}")
        if placement.width is not None:
            fields.append(f"width: {_g(placement.width)}")
        else:
            fields.append(f"right: {_g(placement.right)}")

    if _should_pin_bottom(placement, parent_height=parent_height):
        fields.append(
            f"bottom: {_g(_resolved_bottom_offset(placement, parent_height=parent_height))}"
        )
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "TOP":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "BOTTOM":
        fields.append(
            f"bottom: {_g(_resolved_bottom_offset(placement, parent_height=parent_height))}"
        )
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "CENTER":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None and placement.height > 0:
            fields.append(f"height: {_g(placement.height)}")
    elif vertical == "TOP_BOTTOM":
        fields.append(f"top: {_g(placement.top)}")
        fields.append(f"bottom: {_g(placement.bottom)}")
    elif vertical == "SCALE":
        fields.append(f"top: {_g(placement.top)}")
        if placement.height is not None:
            fields.append(f"height: {_g(placement.height)}")
        else:
            fields.append(f"bottom: {_g(placement.bottom)}")

    if not fields:
        fields.extend([f"left: {_g(placement.left)}", f"top: {_g(placement.top)}"])
    return fields


def _positioned_fields_from_pins(
    pins: AxisPins,
    *,
    render_boundary: bool = False,
    parent_height: float | None = None,
) -> list[str]:
    """Map geometry-planner ``AxisPins`` to Positioned fields (T2 pin law)."""

    def _g(value: float) -> str:
        if _snap_device_pixels_ctx.get():
            value = snap_to_device_pixel(value)
        return format_geometry_literal(value)

    fields: list[str] = []
    free_h = pins.free_horizontal
    if free_h == "left" and pins.left is not None:
        fields.append(f"left: {_g(pins.left)}")
        if pins.width is not None and pins.width > 0:
            fields.append(f"width: {_g(pins.width)}")
    elif free_h == "right" and pins.right is not None:
        fields.append(f"right: {_g(pins.right)}")
        if pins.width is not None and pins.width > 0:
            fields.append(f"width: {_g(pins.width)}")
    elif free_h == "width":
        if pins.left is not None:
            fields.append(f"left: {_g(pins.left)}")
        if pins.width is not None:
            fields.append(f"width: {_g(pins.width)}")
        elif pins.right is not None:
            fields.append(f"right: {_g(pins.right)}")
    if pins.left is not None and not any(field.startswith("left:") for field in fields):
        fields.append(f"left: {_g(pins.left)}")

    free_v = pins.free_vertical
    if free_v == "top" and pins.top is not None:
        fields.append(f"top: {_g(pins.top)}")
        if pins.height is not None and pins.height > 0:
            fields.append(f"height: {_g(pins.height)}")
    elif free_v == "bottom" and pins.bottom is not None:
        fields.append(f"bottom: {_g(pins.bottom)}")
        if pins.height is not None and pins.height > 0:
            fields.append(f"height: {_g(pins.height)}")
    elif free_v == "height":
        if pins.top is not None:
            fields.append(f"top: {_g(pins.top)}")
        if pins.height is not None:
            fields.append(f"height: {_g(pins.height)}")
        elif pins.bottom is not None:
            fields.append(f"bottom: {_g(pins.bottom)}")
    if pins.top is not None and not any(field.startswith("top:") for field in fields):
        fields.append(f"top: {_g(pins.top)}")

    if not fields:
        if pins.left is not None:
            fields.append(f"left: {_g(pins.left)}")
        if pins.top is not None:
            fields.append(f"top: {_g(pins.top)}")
    _ = parent_height
    return fields


def _apply_layout_slot_wraps(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None = None,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Apply planner-authorized wrappers (flex, T3 delta_top, T5 RepaintBoundary)."""
    slot = node.layout_slot
    if slot is None:
        return widget
    flex_parent_child = parent_type in {NodeType.ROW, NodeType.COLUMN}
    working = widget
    will_apply_flex_parent = flex_parent_child and (
        WrapKind.EXPANDED in slot.wraps or WrapKind.FLEXIBLE_LOOSE in slot.wraps
    )
    if WrapKind.CONSTRAINED_BOX in slot.wraps:
        from figma_flutter_agent.parser.interaction import stack_is_product_recommendation_hero

        product_card_hero = (
            stack_is_product_recommendation_hero(node)
            and parent_node is not None
            and parent_node.type == NodeType.CARD
        )
        if not product_card_hero:
            from figma_flutter_agent.generator.layout.flex_policy import (
                flex_host_prefers_min_height_pin,
                hoist_flex_parent_data,
            )
            from figma_flutter_agent.generator.layout.responsive import (
                current_responsive_emit,
                responsive_host_width_literal,
            )

            if will_apply_flex_parent:
                unwrapped = _unwrap_flex_parent_data_wrapper(working)
                if unwrapped is not None:
                    _, working = unwrapped

            width = node.sizing.width
            width_lit = responsive_host_width_literal(
                width,
                width_mode=node.sizing.width_mode,
            )
            ctx = current_responsive_emit()
            skip_redundant = (
                width_lit == "double.infinity"
                and ctx.enabled
                and WrapKind.CROSS_STRETCH_WIDTH in slot.wraps
            )

            def _constrained_box_inner(inner: str) -> str:
                from figma_flutter_agent.generator.layout.flex_policy.column import (
                    column_is_product_card_footer_margin,
                )

                if skip_redundant:
                    return inner
                height = node.sizing.height
                if column_is_product_card_footer_margin(node):
                    return f"SizedBox(width: {width_lit}, child: {inner})"
                if (
                    parent_type == NodeType.ROW
                    and height is not None
                    and height > 0
                    and node.sizing.height_mode in {SizingMode.FIXED, SizingMode.FILL}
                ):
                    height_lit = format_geometry_literal(height)
                    if flex_host_prefers_min_height_pin(node):
                        return (
                            f"ConstrainedBox("
                            f"constraints: BoxConstraints(minHeight: {height_lit}), "
                            f"child: {inner})"
                        )
                    return (
                        f"SizedBox(width: {width_lit}, "
                        f"height: {height_lit}, "
                        f"child: {inner})"
                    )
                return f"SizedBox(width: {width_lit}, child: {inner})"

            if will_apply_flex_parent:
                working = _constrained_box_inner(working)
            else:
                working = hoist_flex_parent_data(_constrained_box_inner, working)
    if WrapKind.DELTA_TOP_PADDING in slot.wraps:
        from figma_flutter_agent.generator.layout.flex_policy import (
            text_host_is_tight_positioned,
        )

        metrics = node.text_metrics_frame
        glyph = (node.text or "").strip()
        skip_centered_glyph_delta = (
            node.type == NodeType.TEXT
            and (node.style.text_align or "").upper() == "CENTER"
            and 0 < len(glyph) <= 3
        )
        if (
            metrics is not None
            and metrics.delta_top is not None
            and not text_host_is_tight_positioned(node)
            and not skip_centered_glyph_delta
        ):
            top = max(0.0, float(metrics.delta_top))
            if top > 0.0:
                top_lit = format_geometry_literal(top)
                working = (
                    f"Padding(padding: EdgeInsets.only(top: {top_lit}), child: {working})"
                )
    if WrapKind.REPAINT_BOUNDARY in slot.wraps:
        from figma_flutter_agent.generator.layout.flex_policy import hoist_flex_parent_data

        if will_apply_flex_parent:
            unwrapped = _unwrap_flex_parent_data_wrapper(working)
            if unwrapped is not None:
                _, working = unwrapped
            working = wrap_repaint_boundary(working)
        else:
            working = hoist_flex_parent_data(wrap_repaint_boundary, working)
    if slot.min_height is not None or slot.max_height is not None:
        min_height, max_height = normalize_box_constraints(
            slot.min_height,
            slot.max_height,
        )
        min_lit = (
            format_geometry_literal(min_height)
            if min_height is not None
            else "0.0"
        )
        max_lit = (
            format_geometry_literal(max_height)
            if max_height is not None
            else "double.infinity"
        )
        working = (
            f"ConstrainedBox("
            f"constraints: BoxConstraints(minHeight: {min_lit}, maxHeight: {max_lit}), "
            f"child: {working})"
        )
    # ``Expanded`` / ``Flexible`` must be direct ``Row``/``Column`` children — apply last.
    if flex_parent_child:
        if WrapKind.EXPANDED in slot.wraps:
            if _unwrap_flex_parent_data_wrapper(working) is None:
                working = f"Expanded(child: {working})"
        elif WrapKind.FLEXIBLE_LOOSE in slot.wraps:
            from figma_flutter_agent.generator.layout.flex_policy import emit_flexible_loose

            working = emit_flexible_loose(working)
        elif WrapKind.CROSS_STRETCH_WIDTH in slot.wraps and not _is_stretched_width_box(
            working
        ):
            working = f"SizedBox(width: double.infinity, child: {working})"
        elif WrapKind.CROSS_STRETCH_HEIGHT in slot.wraps:
            from figma_flutter_agent.generator.layout.flex_policy import (
                bind_row_cross_axis_height,
            )

            working = bind_row_cross_axis_height(node, working, parent_row=parent_node)
    from figma_flutter_agent.generator.layout.flex_policy.wrap import repair_flex_parent_data_order

    return repair_flex_parent_data_order(working)


def _is_stretched_width_box(widget: str) -> bool:
    trimmed = widget.lstrip()
    return trimmed.startswith("Expanded(") or trimmed.startswith(
        "SizedBox(width: double.infinity, child:"
    )


def _should_omit_positioned_height(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
) -> bool:
    """Let stack/flex hosts grow past fractional Figma frame heights when needed."""
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_bounded_slot_should_grow,
        stack_metadata_timestamp_host,
    )

    if column_bounded_slot_should_grow(node):
        return True
    if stack_metadata_timestamp_host(node, parent_node=parent_node):
        return True
    if node.type != NodeType.TEXT:
        return False
    placement = node.stack_placement
    if placement is None or placement.height is None or placement.height <= 0:
        return False
    text = node.text or ""
    if "\n" in text:
        return True
    font_size = node.style.font_size
    glyph_height = node.style.glyph_height
    if font_size is not None and glyph_height is not None:
        return glyph_height > font_size * 1.45
    if font_size is not None and font_size > 0:
        line_factor = node.style.line_height if node.style.line_height else 1.2
        if float(placement.height) >= font_size * line_factor * 1.35:
            return True
    return False
