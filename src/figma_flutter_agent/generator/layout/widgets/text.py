"""Text layout emitters: multiline, button-label, stack-position wrappers."""

from __future__ import annotations

import math
from collections.abc import Callable

from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant
from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.emit_text_span import (
    emit_text_rich,
    emit_text_span_children_from_node,
)
from figma_flutter_agent.generator.figma_anchor import figma_value_key_arg
from figma_flutter_agent.generator.geometry.affine import (
    matrix4_close_suffix,
    matrix4_compose_expr,
    requires_raster_tier,
)
from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
    normalize_box_constraints,
    wrap_repaint_boundary,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_back_nav_stack as cupertino_wrap_back_nav_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_button_stack as cupertino_wrap_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_circular_button_stack as cupertino_wrap_circular_button_stack,
)
from figma_flutter_agent.generator.layout.cupertino import (
    wrap_scroll_viewport,
)
from figma_flutter_agent.generator.layout.form import (
    render_button,
    render_checkbox,
    render_dialog,
    render_dropdown,
    render_input,
    render_radio,
    render_radio_group,
    render_slider,
    render_switch,
    wrap_material_input_child,
)
from figma_flutter_agent.generator.layout.navigation.bottom import render_bottom_navigation
from figma_flutter_agent.generator.layout.navigation.tabs import (
    render_carousel,
    render_tabs,
)
from figma_flutter_agent.generator.layout.responsive import (
    should_apply_responsive_column_reflow,
    wrap_responsive_root_column,
)
from figma_flutter_agent.generator.layout.scroll import (
    render_both_axis_scroll,
    render_grid_view,
    render_scroll_list,
    scroll_axis_for_list,
    wrap_flex_auto_layout_padding,
)
from figma_flutter_agent.generator.layout.style import (
    border_radius_expr,
    box_decoration_expr,
    box_foreground_decoration_expr,
    card_elevation_expr,
    dart_color_expr,
    has_box_decoration,
    is_dark_fill_color,
    should_emit_strut_style,
    strut_style_expr,
    text_align_expr,
    text_style_expr,
    text_widget_trailing_params,
    wrap_tight_chip_label,
)
from figma_flutter_agent.generator.layout.style.decoration import _shadow_expr
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_sigma_literal,
    snap_to_device_pixel,
)
from figma_flutter_agent.generator.variant.state import variant_blocks_interaction
from figma_flutter_agent.parser.interaction import (
    _BACK_NAV_DESCENDANT_DEPTH,
    _descendant_nodes,
    _has_circular_container,
    _is_footer_link_text_node,
    _label_matches_action_hint,
    _local_nodes,
    _stack_spans_primary_button_and_footer_link,
    button_stack_has_left_icon,
    input_children_are_presentational,
    input_flex_value_text,
    input_hint_node,
    input_value_style_node,
    input_hint_text,
    input_surface_node,
    input_trailing_chrome_nodes,
    interaction_surface_node,
    is_back_navigation_icon_stack,
    is_link_text,
    looks_like_back_nav_stack,
    looks_like_bottom_docked_sheet,
    looks_like_checkbox_control,
    looks_like_compact_icon_action_button,
    looks_like_compact_icon_action_stack,
    looks_like_password_field_stack,
    looks_like_play_pause_control_stack,
    looks_like_skip_control_stack,
    looks_like_textarea_field,
    primary_surface_node,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
    round_geometry,
)
from figma_flutter_agent.parser.render_bounds import (
    child_has_outward_paint,
    stack_needs_soft_clip,
)
from figma_flutter_agent.parser.stack_paint import (
    sort_absolute_stack_children as _sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import (
    AxisPins,
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    SizingMode,
    StackPlacement,
    WrapKind,
)

from .shared import _node_layout_size, figma_positioned_dimensions
from .decoration import _decorate_widget_with_box_decoration, _wrap_widget_with_box_decoration
from .layout import (
    _apply_layout_slot_wraps,
    _flex_parent_data_wrapper,
    _positioned_fields,
    _positioned_fields_from_pins,
    _resolved_bottom_offset,
    _should_omit_positioned_height,
    _should_pin_bottom,
    _stack_has_bottom_anchored_child,
    _wrap_sizing,
)
from .position import (
    _child_needs_positioned_bounds,
    _ensure_positioned_stack_bounds,
    _node_has_nested_stack,
    _positioned_horizontal_box_fields,
    _render_leaf_surface,
    _wrap_root_column_viewport,
    _wrap_root_stack_viewport,
)
from .svg import (
    _apply_node_transform,
    _effective_svg_dimensions,
    _is_skip_control_stack,
    _render_svg_picture,
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
    trailing = text_widget_trailing_params(
        node.style,
        text_align_suffix=text_align_suffix,
        soft_wrap=True,
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
    if parent_type not in {NodeType.STACK, NodeType.BUTTON}:
        return widget
    if (
        parent_node is not None
        and parent_node.type == NodeType.STACK
    ):
        from figma_flutter_agent.generator.layout.flex_policy import (
            stack_should_flow_as_column,
            stack_should_flow_as_centered_wrap,
        )

        if stack_should_flow_as_column(parent_node):
            return widget
        if stack_should_flow_as_centered_wrap(parent_node):
            return widget
    if fill_parent:
        return f"Positioned.fill(child: {widget})"
    placement = node.stack_placement
    if placement is None and node.layout_positioning == "ABSOLUTE":
        placement = StackPlacement(left=node.offset_x, top=node.offset_y)
    if placement is None:
        return widget
    if parent_node is not None and parent_node.type == NodeType.STACK:
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
        )
    if _child_needs_positioned_bounds(node, widget):
        _ensure_positioned_stack_bounds(
            fields, node, placement, parent_height=parent_height
        )
    if _should_omit_positioned_height(node, parent_node=parent_node):
        fields[:] = [field for field in fields if not field.startswith("height:")]
    from figma_flutter_agent.generator.layout.responsive import (
        should_stretch_bottom_positioned_horizontal,
        stretch_positioned_fields_horizontal,
    )

    if placement is not None and should_stretch_bottom_positioned_horizontal(placement):
        stretch_positioned_fields_horizontal(fields)
    width, height = _node_layout_size(node, placement)
    _raw_width, effective_height = _effective_svg_dimensions(node, width, height)
    adjusted_top = _stroke_line_top_adjustment(node, placement, effective_height)
    if (
        adjusted_top is not None
        and placement.top is not None
        and adjusted_top != placement.top
    ):
        fields = [
            field if not field.startswith("top:") else f"top: {adjusted_top}"
            for field in fields
        ]
    fields_str = ", ".join(fields)
    child = widget
    slot_height = placement.height
    if (
        slot_height is not None
        and slot_height > 0
        and node.type in {NodeType.COLUMN, NodeType.ROW, NodeType.CONTAINER}
    ):
        child = _wrap_bounded_positioned_slot_child(
            child,
            node=node,
            parent_node=parent_node,
        )
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
    if parent_node.type == NodeType.BUTTON:
        from figma_flutter_agent.parser.interaction import (
            button_has_list_tile_row_body,
            button_stack_has_left_icon,
        )

        if button_has_list_tile_row_body(parent_node):
            return False
        if button_stack_has_left_icon(parent_node):
            return False
        return True
    if parent_node.type != NodeType.STACK:
        return False
    if stack_interaction_kind(parent_node) == "button":
        return True
    text_nodes = [
        item
        for item in _local_nodes(parent_node, 2)
        if item.type == NodeType.TEXT and item.text
    ]
    return _stack_spans_primary_button_and_footer_link(
        parent_node, text_nodes=text_nodes
    )


def _button_label_should_center_in_parent(
    parent_node: CleanDesignTreeNode,
    *,
    placement: StackPlacement,
    text_node: CleanDesignTreeNode,
) -> bool:
    """Center CTA copy in the full button when an icon sits left or the label is wide."""
    if button_stack_has_left_icon(parent_node):
        return True
    parent_width = parent_node.sizing.width
    text_width = (
        placement.width if placement.width is not None else text_node.sizing.width
    )
    if parent_width is None or text_width is None or parent_width <= 0:
        return False
    return float(text_width) >= float(parent_width) * 0.55


def _ensure_text_center_align(widget: str) -> str:
    """Add ``textAlign: TextAlign.center`` when the label is centered in a button row."""
    if "textAlign:" in widget:
        return widget
    if "Text(" in widget and "textScaler:" in widget:
        return widget.replace(
            "textScaler:", "textAlign: TextAlign.center, textScaler:", 1
        )
    return widget


def _position_button_stack_label(
    widget: str,
    *,
    text_node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> str:
    """Vertically center CTA labels inside absolute button stacks."""
    parent_height = parent_node.sizing.height
    parent_width = parent_node.sizing.width
    text_nodes = [
        item
        for item in _local_nodes(parent_node, 2)
        if item.type == NodeType.TEXT and item.text
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
            if _label_matches_action_hint(
                (item.text or item.name or "").strip().lower()
            )
            and not _is_footer_link_text_node(item)
        ]
        if (
            stack_interaction_kind(parent_node) == "button"
            and len(text_nodes) == 1
            and len(action_labels) == 1
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
        width = (
            placement.width if placement.width is not None else text_node.sizing.width
        )
        fields = [
            f"left: {format_geometry_literal(left)}",
            "top: 0.0",
            f"height: {format_geometry_literal(parent_height)}",
        ]
        if width is not None and width > 0:
            fields.insert(1, f"width: {format_geometry_literal(width)}")
        centered = f"Align(alignment: Alignment.centerLeft, child: {widget})"
    return f"Positioned({', '.join(fields)}, {figma_value_key_arg(text_node.id)}, child: {centered})"


