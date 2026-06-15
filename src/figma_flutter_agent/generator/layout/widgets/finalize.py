"""Accessibility, min-touch-target, opacity, and render-boundary wrapping."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.common import (
    escape_dart_string,
)
from figma_flutter_agent.parser.interaction import (
    layout_fact_checkbox_control,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
)

from .decoration import (
    _wrap_content_layer_blur,
)
from .layout import (
    _apply_layout_slot_wraps,
    _wrap_sizing,
)
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
        layout_fact_row_tight_horizontal_pill_label,
    )
    from figma_flutter_agent.parser.interaction import (
        layout_fact_input_trailing_icon_button,
    )

    if layout_fact_input_trailing_icon_button(node):
        return widget
    if layout_fact_checkbox_control(node):
        return widget
    if node.type == NodeType.BUTTON and node.children:
        row_host = node.children[0]
        if row_host.type == NodeType.ROW and layout_fact_row_tight_horizontal_pill_label(row_host):
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
    return not (placement is not None and (placement.top or 0.0) < 280.0 and area > 80_000.0)


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
    wrapped = _wrap_sizing(node, wrapped, parent_type=parent_type, parent_node=parent_node)
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
