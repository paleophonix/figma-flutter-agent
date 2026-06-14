"""Stack layering helpers for docked bottom navigation chrome."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.positioned import (
    _stack_has_bottom_anchored_child,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def is_bottom_docked_stack_child(child: CleanDesignTreeNode) -> bool:
    """Return True when a stack child is bottom navigation chrome."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        is_viewport_chrome_band,
    )

    if is_viewport_chrome_band(child):
        return False
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
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        is_viewport_chrome_band,
        stack_child_should_use_pin_bottom_scroll_host,
    )

    for child, widget in zip(child_nodes, child_widgets, strict=True):
        if is_bottom_docked_stack_child(child):
            pinned.append(widget)
            continue
        if is_viewport_chrome_band(child):
            pinned.append(widget)
            continue
        if not stack_child_should_use_pin_bottom_scroll_host(child):
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


def pin_bottom_flow_column_scroll_wrap(
    widget_expr: str,
    *,
    allow_outward_paint: bool = False,
    bottom_padding: float = 0.0,
) -> str:
    """Wrap a flow-column stack slot in ``Expanded`` + ``SingleChildScrollView``."""
    clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
    padding = (
        f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(bottom_padding)}), "
        if bottom_padding > 0
        else ""
    )
    return (
        f"Expanded(child: SingleChildScrollView({clip}{padding}"
        f"child: {widget_expr}))"
    )
