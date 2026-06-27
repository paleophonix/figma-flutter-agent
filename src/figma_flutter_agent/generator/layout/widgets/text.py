"""Text layout emitters: multiline, button-label, stack-position wrappers."""

from __future__ import annotations

from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
)
from figma_flutter_agent.generator.layout.style import (
    text_widget_trailing_params,
)
from figma_flutter_agent.generator.layout.widgets.shared import _snap_device_pixels_ctx
from figma_flutter_agent.generator.render_units import snap_to_device_pixel
from figma_flutter_agent.parser.interaction import (
    _is_footer_link_text_node,
    _label_matches_action_hint,
    _local_nodes,
    _stack_spans_primary_button_and_footer_link,
    button_stack_has_left_icon,
    layout_fact_stack_category_component_tile,
    layout_fact_stack_vertical_icon_label_chip_tile,
    primary_surface_node,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
)
from figma_flutter_agent.parser.render_bounds import (
    child_has_outward_paint,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    StackPlacement,
)

from .layout import (
    _positioned_fields,
    _positioned_fields_from_pins,
    _should_omit_positioned_height,
)
from .position import (
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
)
from .shared import _node_layout_size
from .svg import (
    _effective_svg_dimensions,
    _is_skip_control_stack,
    _stroke_line_top_adjustment,
)


def _render_explicit_multiline_text_lines(
    node: CleanDesignTreeNode,
    *,
    style_expr: str,
    text_align_suffix: str,
) -> str | None:
    """Preserve Figma hard line breaks in one ``Text`` without ``maxLines: 1`` clipping."""
    if node.text_spans:
        return None
    raw = (node.text or "").strip()
    if "\n" not in raw:
        return None
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    from figma_flutter_agent.parser.interaction.forms import text_is_payment_option_secondary

    payment_subtitle = text_is_payment_option_secondary(node)
    trailing = text_widget_trailing_params(
        node.style,
        text_align_suffix=text_align_suffix,
        soft_wrap=False,
        omit_strut=payment_subtitle,
        optical_center=payment_subtitle,
    )
    text = escape_dart_string(raw)
    return f"Text('{text}', style: {style_expr}, {trailing})"


def _wrap_bounded_positioned_slot_child(
    widget: str,
    *,
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None = None,
) -> str:
    """Clip slot overflow without ``RenderFlex`` layout assertions.

    ``ClipRect`` alone only affects painting. When a ``Column`` with
    ``mainAxisSize: min`` is fractionally taller than its ``Positioned`` slot
    (text metrics rounding, flex ``spacing``), Flutter still throws overflow.
    ``OverflowBox`` loosens the flex axis while the outer ``Positioned`` slot
    keeps the painted bounds stable.
    """
    from figma_flutter_agent.generator.layout.flex_policy import (
        column_bounded_slot_needs_vertical_scroll,
        column_bounded_slot_should_grow,
        stack_metadata_timestamp_host,
    )

    if stack_metadata_timestamp_host(node, parent_node=parent_node):
        return widget

    if column_bounded_slot_should_grow(node):
        return widget

    if column_bounded_slot_needs_vertical_scroll(node):
        scroll_body = f"SingleChildScrollView(child: {widget})"
        if child_has_outward_paint(node):
            return scroll_body
        return f"ClipRect(child: {scroll_body})"

    placement = node.stack_placement
    width, height = _node_layout_size(node, placement)
    # ``widget`` already includes this node's ``Padding`` (applied in ``_finalize_widget``
    # before ``_apply_stack_position``). ``OverflowBox`` max extent must therefore match
    # the full positioned slot — subtracting padding here double-counts and starves flex
    # children (e.g. 84px slot + 36px padding → 12px for ``Column`` → RenderFlex overflow).
    if node.type == NodeType.ROW:
        align = "Alignment.centerLeft"
        if width is not None and width > 0:
            loosen = f"maxWidth: {format_geometry_literal(width)}, "
        else:
            loosen = "maxWidth: double.infinity, "
    else:
        align = "Alignment.topCenter"
        if height is not None and height > 0:
            loosen = f"maxHeight: {format_geometry_literal(height)}, "
        else:
            loosen = "maxHeight: double.infinity, "
    inner = (
        f"Align(alignment: {align}, child: OverflowBox("
        f"alignment: {align}, {loosen}"
        f"child: {widget}))"
    )
    if child_has_outward_paint(node):
        return inner
    return f"ClipRect(child: {inner})"


def _apply_stack_position(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
    fill_parent: bool = False,
    scroll_content_root: bool = False,
) -> str:
    if scroll_content_root:
        return widget
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_should_emit_positioned,
    )

    if not stack_child_should_emit_positioned(
        node,
        parent_type=parent_type,
        parent_node=parent_node,
    ):
        return widget
    if fill_parent:
        return f"Positioned.fill(child: {widget})"
    placement = node.stack_placement
    if placement is None and node.layout_positioning == "ABSOLUTE":
        placement = StackPlacement(left=node.offset_x, top=node.offset_y)
    if placement is None:
        return widget
    if parent_node is not None:
        from figma_flutter_agent.generator.layout.widgets.position import (
            top_navigation_bar_title_lane_placement,
        )

        lane_placement = top_navigation_bar_title_lane_placement(node, parent_node)
        if lane_placement is not None:
            placement = lane_placement
    parent_width: float | None = None
    if parent_node is not None and parent_node.type == NodeType.STACK and not node.render_boundary:
        parent_width = parent_node.sizing.width
        if parent_width is None and parent_node.stack_placement is not None:
            parent_width = parent_node.stack_placement.width
        if parent_width is not None and parent_width > 0:
            from figma_flutter_agent.parser.layout import (
                clamp_stack_child_placement_to_parent,
            )

            placement = clamp_stack_child_placement_to_parent(
                placement,
                float(parent_width),
            )
    parent_height: float | None = None
    if parent_node is not None:
        parent_height = parent_node.sizing.height
        if parent_height is None and parent_node.stack_placement is not None:
            parent_height = parent_node.stack_placement.height
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_numeric_glyph_overlay_host,
    )

    prefer_top_pin = (
        parent_node is not None
        and layout_fact_stack_numeric_glyph_overlay_host(parent_node)
        and node.type == NodeType.TEXT
        and (node.text or "").strip().isdigit()
    )
    slot = node.layout_slot
    if slot is not None and slot.positioned_pins is not None:
        fields = _positioned_fields_from_pins(
            slot.positioned_pins,
            render_boundary=node.render_boundary,
            parent_height=parent_height,
        )
    else:
        fields = _positioned_fields(
            placement,
            render_boundary=node.render_boundary,
            parent_height=parent_height,
            prefer_top_pin=prefer_top_pin,
        )
    from figma_flutter_agent.generator.layout.widgets.position import (
        placement_dual_horizontal_insets_overconstrain,
    )

    if (
        placement is not None
        and placement.horizontal == "CENTER"
        and placement.left is not None
        and placement.right is not None
        and float(placement.left) > 1.5
        and float(placement.right) > 1.5
        and not placement_dual_horizontal_insets_overconstrain(placement, parent_width)
    ):

        def _g_center(value: float) -> str:
            if _snap_device_pixels_ctx.get():
                value = snap_to_device_pixel(value)
            return format_geometry_literal(value)

        vertical_fields = [
            field for field in fields if field.startswith(("top:", "bottom:", "height:"))
        ]
        fields = [
            f"left: {_g_center(placement.left)}",
            f"right: {_g_center(placement.right)}",
            *vertical_fields,
        ]
    if _child_needs_positioned_bounds(node, widget):
        _ensure_positioned_stack_bounds(
            fields,
            node,
            placement,
            parent_width=parent_width,
            parent_height=parent_height,
            prefer_top_pin=prefer_top_pin,
        )
    from figma_flutter_agent.generator.layout.widgets.position import (
        top_navigation_bar_child_vertical_fields,
    )

    width, height = _node_layout_size(node, placement)
    nav_vertical = top_navigation_bar_child_vertical_fields(
        parent_node,
        child_height=float(height or placement.height or node.sizing.height or 0.0),
    )
    if nav_vertical is not None:
        fields[:] = [
            field
            for field in fields
            if not field.startswith(("top:", "bottom:", "height:"))
        ]
        fields.extend(nav_vertical)
    if _should_omit_positioned_height(node, parent_node=parent_node):
        fields[:] = [field for field in fields if not field.startswith("height:")]
    from figma_flutter_agent.generator.layout.responsive import (
        should_stretch_bottom_positioned_horizontal,
        stretch_positioned_fields_horizontal,
    )

    if placement is not None and should_stretch_bottom_positioned_horizontal(placement):
        stretch_positioned_fields_horizontal(fields)
    _raw_width, effective_height = _effective_svg_dimensions(node, width, height)
    adjusted_top = _stroke_line_top_adjustment(node, placement, effective_height)
    if (
        adjusted_top is not None
        and placement.top is not None
        and adjusted_top != placement.top
        and nav_vertical is None
    ):
        fields = [
            field if not field.startswith("top:") else f"top: {adjusted_top}" for field in fields
        ]
    fields_str = ", ".join(fields)
    child = widget
    from figma_flutter_agent.generator.geometry.text_metrics import (
        placement_is_center_pinned_horizontal,
    )
    from figma_flutter_agent.generator.layout.widgets.position import (
        top_navigation_bar_title_should_screen_center,
    )

    if node.type == NodeType.TEXT and (
        placement_is_center_pinned_horizontal(placement)
        if placement is not None
        else False
    ) or top_navigation_bar_title_should_screen_center(node, parent_node):
        child = f"SizedBox(width: double.infinity, child: Center(child: {child}))"
    slot_height = placement.height
    if (
        slot_height is not None
        and slot_height > 0
        and node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.CONTAINER, NodeType.INPUT, NodeType.STACK}
    ):
        child = _wrap_bounded_positioned_slot_child(
            child,
            node=node,
            parent_node=parent_node,
        )
    if (
        node.render_boundary
        and parent_node is not None
        and parent_node.sizing.width is not None
        and parent_node.sizing.height is not None
        and float(parent_node.sizing.width) >= 360.0
        and 180.0 <= float(parent_node.sizing.height) <= 320.0
    ):
        child = f"ClipRect(child: {child})"
    return f"Positioned({fields_str}, {figma_value_key_arg(node.id)}, child: {child})"


def _should_center_text_in_button_stack(
    parent_node: CleanDesignTreeNode | None,
    text_node: CleanDesignTreeNode,
) -> bool:
    from figma_flutter_agent.parser.interaction import _is_footer_link_text_node

    if parent_node is None or text_node.type != NodeType.TEXT:
        return False
    if _is_footer_link_text_node(text_node):
        return False
    font_size = text_node.style.font_size if text_node.style else None
    if font_size is not None and float(font_size) >= 22.0:
        return False
    if _is_skip_control_stack(parent_node):
        return False
    if layout_fact_stack_category_component_tile(parent_node):
        return False
    if layout_fact_stack_vertical_icon_label_chip_tile(parent_node):
        return False
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_active_tab_pill,
    )

    if layout_fact_stack_bottom_nav_active_tab_pill(parent_node):
        return False
    if parent_node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction import (
            button_has_list_tile_row_body,
            button_is_left_aligned_text_label,
            button_stack_has_left_icon,
        )

        if button_has_list_tile_row_body(parent_node):
            return False
        if button_stack_has_left_icon(parent_node):
            return False
        return not button_is_left_aligned_text_label(parent_node)
    if parent_node.type != NodeType.STACK:
        return False
    if stack_interaction_kind(parent_node) == "button":
        if layout_fact_stack_vertical_icon_label_chip_tile(parent_node):
            return False
        if layout_fact_stack_bottom_nav_active_tab_pill(parent_node):
            return False
        return True
    text_nodes = [
        item for item in _local_nodes(parent_node, 2) if item.type == NodeType.TEXT and item.text
    ]
    return _stack_spans_primary_button_and_footer_link(parent_node, text_nodes=text_nodes)


def _button_sole_cta_should_center(
    parent_node: CleanDesignTreeNode,
    text_node: CleanDesignTreeNode,
) -> bool:
    """Center a sole label across a painted BUTTON host (LAW-BTN-LABEL-CENTER)."""
    from figma_flutter_agent.parser.interaction import (
        _is_footer_link_text_node,
        button_has_list_tile_row_body,
        button_stack_has_left_icon,
    )

    if parent_node.type != NodeType.BUTTON:
        return False
    if button_has_list_tile_row_body(parent_node) or button_stack_has_left_icon(parent_node):
        return False
    if _is_footer_link_text_node(text_node):
        return False
    text_nodes = [
        item for item in _local_nodes(parent_node, 2) if item.type == NodeType.TEXT and item.text
    ]
    if len(text_nodes) != 1 or text_nodes[0].id != text_node.id:
        return False
    parent_width = parent_node.sizing.width
    if parent_width is None or float(parent_width) <= 0:
        return False
    return any(
        child.type == NodeType.CONTAINER
        and child.style.background_color is not None
        and child.sizing.width is not None
        and float(child.sizing.width) >= float(parent_width) * 0.9
        for child in parent_node.children
    )


def _button_label_should_center_in_parent(
    parent_node: CleanDesignTreeNode,
    *,
    placement: StackPlacement,
    text_node: CleanDesignTreeNode,
) -> bool:
    """Center CTA copy in the full button when an icon sits left or the label is wide."""
    if _button_sole_cta_should_center(parent_node, text_node):
        return True
    if button_stack_has_left_icon(parent_node):
        return True
    parent_width = parent_node.sizing.width
    text_width = placement.width if placement.width is not None else text_node.sizing.width
    if parent_width is None or text_width is None or parent_width <= 0:
        return False
    return float(text_width) >= float(parent_width) * 0.55


def _ensure_text_center_align(widget: str) -> str:
    """Add ``textAlign: TextAlign.center`` when the label is centered in a button row."""
    if "textAlign:" in widget:
        return widget
    if "Text(" in widget and "textScaler:" in widget:
        return widget.replace("textScaler:", "textAlign: TextAlign.center, textScaler:", 1)
    return widget


def _position_button_stack_label(
    widget: str,
    *,
    text_node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> str:
    """Vertically center CTA labels inside absolute button stacks."""
    if layout_fact_stack_vertical_icon_label_chip_tile(parent_node):
        width = placement.width if placement.width is not None else text_node.sizing.width
        if width is None or float(width) <= 0:
            width = parent_node.sizing.width
        fields: list[str] = ["bottom: 0.0"]
        if width is not None and float(width) > 0:
            if (placement.horizontal or "").upper() in {"LEFT_RIGHT", "STRETCH"}:
                fields = ["left: 0.0", "right: 0.0", *fields]
            else:
                left = placement.left if placement.left is not None else 0.0
                fields = [
                    f"left: {format_geometry_literal(float(left))}",
                    f"width: {format_geometry_literal(float(width))}",
                    *fields,
                ]
        return (
            f"Positioned({', '.join(fields)}, {figma_value_key_arg(text_node.id)}, child: {widget})"
        )
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_active_tab_pill,
    )

    if layout_fact_stack_bottom_nav_active_tab_pill(parent_node):
        return _apply_stack_position(
            text_node,
            widget,
            parent_type=NodeType.STACK,
            fill_parent=False,
        )
    from figma_flutter_agent.generator.layout.flex_policy.buttons import (
        button_is_pill_with_centered_label,
        button_should_center_sole_text_label,
    )

    if parent_node.type == NodeType.BUTTON and (
        button_is_pill_with_centered_label(parent_node)
        or button_should_center_sole_text_label(parent_node)
    ):
        return f"Center(child: {_ensure_text_center_align(widget)})"
    parent_height = parent_node.sizing.height
    parent_width = parent_node.sizing.width
    text_nodes = [
        item for item in _local_nodes(parent_node, 2) if item.type == NodeType.TEXT and item.text
    ]
    if _stack_spans_primary_button_and_footer_link(parent_node, text_nodes=text_nodes):
        surface = primary_surface_node(parent_node)
        if surface is not None:
            if surface.sizing.height is not None and surface.sizing.height > 0:
                parent_height = surface.sizing.height
            if surface.sizing.width is not None and surface.sizing.width > 0:
                parent_width = surface.sizing.width
    if parent_height is None or parent_height <= 0:
        return _apply_stack_position(
            text_node,
            widget,
            parent_type=NodeType.STACK,
            fill_parent=False,
        )
    center_in_parent = _button_label_should_center_in_parent(
        parent_node,
        placement=placement,
        text_node=text_node,
    )
    if not center_in_parent:
        action_labels = [
            item
            for item in text_nodes
            if _label_matches_action_hint((item.text or item.name or "").strip().lower())
            and not _is_footer_link_text_node(item)
        ]
        if (
            (stack_interaction_kind(parent_node) == "button" or parent_node.type == NodeType.BUTTON)
            and len(text_nodes) == 1
            and len(action_labels) == 1
            and not layout_fact_stack_vertical_icon_label_chip_tile(parent_node)
        ):
            center_in_parent = True
        else:
            center_in_parent = _stack_spans_primary_button_and_footer_link(
                parent_node,
                text_nodes=text_nodes,
            )
    if center_in_parent and parent_width is not None and parent_width > 0:
        fields = [
            "left: 0.0",
            f"width: {format_geometry_literal(parent_width)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        label_widget = _ensure_text_center_align(widget)
        centered = f"Align(alignment: Alignment.center, child: {label_widget})"
    else:
        left = placement.left if placement.left is not None else 0.0
        width = placement.width if placement.width is not None else text_node.sizing.width
        fields = [
            f"left: {format_geometry_literal(left)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        if width is not None and width > 0:
            fields.insert(1, f"width: {format_geometry_literal(width)}")
        centered = f"Align(alignment: Alignment.centerLeft, child: {widget})"
    return (
        f"Positioned({', '.join(fields)}, {figma_value_key_arg(text_node.id)}, child: {centered})"
    )
