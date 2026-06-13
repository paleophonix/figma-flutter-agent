"""Stack layering helpers for docked bottom navigation chrome."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.positioned import (
    _stack_has_bottom_anchored_child,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def is_bottom_docked_stack_child(child: CleanDesignTreeNode) -> bool:
    """Return True when a stack child is bottom navigation chrome."""
    if child.type == NodeType.BOTTOM_NAV:
        return True
    placement = child.stack_placement
    if placement is None:
        return False
    return placement.vertical == "BOTTOM"


def bottom_chrome_clearance_height(stack: CleanDesignTreeNode) -> float:
    """Return scroll inset for content layered under docked bottom chrome."""
    chrome_height = 0.0
    for child in stack.children:
        if not is_bottom_docked_stack_child(child):
            continue
        placement = child.stack_placement
        height = (
            (placement.height if placement is not None else None)
            or child.sizing.height
            or 0.0
        )
        chrome_height = max(chrome_height, float(height))
    padding_bottom = stack.padding.bottom if stack.padding is not None else 0.0
    return max(chrome_height, float(padding_bottom))


def column_hoists_docked_bottom_nav_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when a column root hosts a single stack with bottom chrome."""
    if node.type != NodeType.COLUMN or len(node.children) != 1:
        return False
    child = node.children[0]
    return child.type == NodeType.STACK and _stack_has_bottom_anchored_child(child)


def apply_pin_bottom_chrome_to_stack_layers(
    stack_node: CleanDesignTreeNode,
    child_nodes: list[CleanDesignTreeNode],
    child_widgets: list[str],
    *,
    allow_outward_paint: bool = False,
) -> list[str]:
    """Wrap non-bottom stack layers in a fill scroll host for docked bottom chrome."""
    if not _stack_has_bottom_anchored_child(stack_node):
        return child_widgets
    clearance = bottom_chrome_clearance_height(stack_node)
    clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
    padding = (
        f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(clearance)}), "
        if clearance > 0
        else ""
    )
    pinned: list[str] = []
    for child, widget in zip(child_nodes, child_widgets, strict=True):
        if is_bottom_docked_stack_child(child):
            pinned.append(widget)
            continue
        pinned.append(
            f"Positioned.fill(child: SingleChildScrollView({clip}{padding}child: {widget}))"
        )
    return pinned


def pin_bottom_scroll_layer_expr(
    widget_expr: str,
    *,
    allow_outward_paint: bool = False,
    bottom_padding: float = 0.0,
) -> str:
    """Wrap a decomposed stack layer in the scroll host used for bottom chrome."""
    clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
    padding = (
        f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(bottom_padding)}), "
        if bottom_padding > 0
        else ""
    )
    return f"Positioned.fill(child: SingleChildScrollView({clip}{padding}child: {widget_expr}))"


def stack_is_viewport_device_chrome_sandwich(node: CleanDesignTreeNode) -> bool:
    """Return True for status bar + scrollable body + home indicator phone shells."""
    if node.type != NodeType.STACK or len(node.children) != 3:
        return False
    from figma_flutter_agent.parser.interaction import is_device_system_chrome_node

    return is_device_system_chrome_node(node.children[0]) and is_device_system_chrome_node(
        node.children[-1]
    )


def is_viewport_chrome_sandwich_middle(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Return True for the scrollable body between status bar and home indicator chrome."""
    if parent_node is None or not stack_is_viewport_device_chrome_sandwich(parent_node):
        return False
    return parent_node.children[1].id == node.id


def device_home_indicator_bar_expr(height: float | None = None) -> str:
    """Emit the iOS-style home indicator pill at the bottom of phone shells."""
    bar_height = format_geometry_literal(height or 34.0)
    return (
        f"SizedBox("
        f"width: double.infinity, "
        f"height: {bar_height}, "
        f"child: Align("
        f"alignment: Alignment.bottomCenter, "
        f"child: Container("
        f"width: 134.0, height: 5.0, "
        f"decoration: BoxDecoration("
        f"color: Colors.black, "
        f"borderRadius: BorderRadius.circular(100.0)"
        f")))))"
    )


def emit_viewport_device_chrome_sandwich_column(
    stack_node: CleanDesignTreeNode,
    child_nodes: list[CleanDesignTreeNode],
    child_widgets: list[str],
) -> str:
    """Emit a full-height column with fixed chrome bands and an expanded body."""
    status_node, content_node, home_node = child_nodes
    status_widget, content_widget, home_widget = child_widgets
    status_height = status_node.sizing.height
    if status_height is None and status_node.stack_placement is not None:
        status_height = status_node.stack_placement.height
    home_height = home_node.sizing.height
    if home_height is None and home_node.stack_placement is not None:
        home_height = home_node.stack_placement.height
    status_band = (
        f"SizedBox(height: {format_geometry_literal(float(status_height))}, child: {status_widget})"
        if status_height is not None and float(status_height) > 0
        else status_widget
    )
    if "SizedBox.shrink()" in home_widget or "home indicator" in (home_node.name or "").lower():
        home_band = device_home_indicator_bar_expr(
            float(home_height) if home_height is not None else None
        )
    elif home_height is not None and float(home_height) > 0:
        home_band = (
            f"SizedBox(height: {format_geometry_literal(float(home_height))}, child: {home_widget})"
        )
    else:
        home_band = home_widget
    return (
        "Column("
        "crossAxisAlignment: CrossAxisAlignment.stretch, "
        "children: ["
        f"{status_band}, "
        f"Expanded(child: {content_widget}), "
        f"{home_band}"
        "])"
    )
