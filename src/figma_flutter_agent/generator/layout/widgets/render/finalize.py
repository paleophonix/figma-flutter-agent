"""Accessibility, min-touch-target, opacity, and render-boundary wrapping."""

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
from .decoration import (
    _decorate_widget_with_box_decoration,
    _wrap_content_layer_blur,
)
from .layout import (
    _apply_layout_slot_wraps,
    _positioned_fields,
    _positioned_fields_from_pins,
    _wrap_sizing,
)
from .position import _wrap_root_stack_viewport
from .text import _apply_stack_position

def _wrap_accessibility(node: CleanDesignTreeNode, widget: str) -> str:
    if node.type in {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.DIALOG,
        NodeType.SLIDER,
    }:
        return widget
    if not node.accessibility_label:
        return widget
    label = escape_dart_string(node.accessibility_label)
    return f"Semantics(label: '{label}', child: {widget})"


def _wrap_min_touch_target(node: CleanDesignTreeNode, widget: str) -> str:
    from figma_flutter_agent.generator.layout.flex_policy import (
        row_is_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.parser.interaction import (
        looks_like_checkbox_control,
        looks_like_input_trailing_icon_button,
    )

    if looks_like_input_trailing_icon_button(node):
        return widget
    if looks_like_checkbox_control(node):
        return widget
    if node.type == NodeType.BUTTON and node.children:
        row_host = node.children[0]
        if row_host.type == NodeType.ROW and row_is_tight_horizontal_pill_label(row_host):
            return widget
        width = node.sizing.width
        height = node.sizing.height
        if (
            width is not None
            and height is not None
            and width > 0
            and height > 0
            and float(width) > float(height) * 1.15
        ):
            return widget
    target = node.min_touch_target
    if target is None or target <= 0:
        return widget
    size = format_geometry_literal(target)
    return f"SizedBox(width: {size}, height: {size}, child: Center(child: {widget}))"


def _wrap_non_interactive_screen_chrome(node: CleanDesignTreeNode, widget: str) -> str:
    from figma_flutter_agent.parser.stack_paint import _is_bottom_screen_chrome

    if node.type == NodeType.BOTTOM_NAV:
        return widget
    if _is_bottom_screen_chrome(node):
        return f"IgnorePointer(ignoring: true, child: {widget})"
    return widget


def _should_offer_render_boundary_tap(node: CleanDesignTreeNode) -> bool:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    if width <= 0.0 or height <= 0.0:
        return False
    area = width * height
    if area > 250_000.0:
        return False
    if area < 12_000.0:
        return bool(node.vector_asset_key and 1_600.0 <= area <= 12_000.0)
    placement = node.stack_placement
    return not (
        placement is not None and (placement.top or 0.0) < 280.0 and area > 80_000.0
    )


def _wrap_render_boundary_tap(node: CleanDesignTreeNode, widget: str) -> str:
    if not _should_offer_render_boundary_tap(node):
        return widget
    return (
        "GestureDetector("
        f"onTap: () {{ {inline_custom_code_comment(custom_code_zone_id(node.id, 'card-action'))} }}, "
        "behavior: HitTestBehavior.opaque, "
        f"child: {widget})"
    )


def _wrap_group_opacity(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply frame opacity to the whole subtree (FID-12)."""
    opacity = node.style.opacity
    if opacity is None or opacity >= 1.0 - 1e-6 or opacity <= 0.0:
        return widget
    value = format_micro_style_literal(opacity)
    return f"Opacity(opacity: {value}, child: {widget})"


def _finalize_widget(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    parent_type: NodeType | None,
    parent_node: CleanDesignTreeNode | None = None,
    fill_parent: bool = False,
    scroll_content_root: bool = False,
) -> str:
    wrapped = _wrap_accessibility(node, widget)
    wrapped = _wrap_group_opacity(node, wrapped)
    wrapped = _wrap_content_layer_blur(node, wrapped)
    wrapped = _wrap_min_touch_target(node, wrapped)
    wrapped = _wrap_non_interactive_screen_chrome(node, wrapped)
    wrapped = _wrap_sizing(
        node, wrapped, parent_type=parent_type, parent_node=parent_node
    )
    from figma_flutter_agent.generator.layout.flex_policy import (
        post_flex_layout_slot_extents,
        prepare_flex_child_extents,
    )

    wrapped = prepare_flex_child_extents(
        wrapped,
        parent_type=parent_type,
        node=node,
    )
    wrapped = _apply_layout_slot_wraps(
        node,
        wrapped,
        parent_type=parent_type,
        parent_node=parent_node,
    )
    wrapped = post_flex_layout_slot_extents(
        wrapped,
        parent_type=parent_type,
        node=node,
        parent_node=parent_node,
    )
    return _apply_stack_position(
        node,
        wrapped,
        parent_type=parent_type,
        parent_node=parent_node,
        fill_parent=fill_parent,
        scroll_content_root=scroll_content_root,
    )


