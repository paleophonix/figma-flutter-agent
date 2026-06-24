"""Selection affordances for payment and option cards."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import is_greenish_fill
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def layout_fact_hosts_payment_selection_indicator(node: CleanDesignTreeNode) -> bool:
    """True when a compact trailing margin hosts a circular payment radio badge."""
    if node.type != NodeType.COLUMN:
        return False
    if (node.name or "").lower() != "margin":
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (18.0 <= float(width) <= 24.0 and 20.0 <= float(height) <= 28.0):
        return False
    return node.cluster_id is not None or any(
        child.type in {NodeType.ROW, NodeType.STACK} and child.style.border_color
        for child in node.children
    )


def _subtree_has_greenish_fill(node: CleanDesignTreeNode) -> bool:
    if is_greenish_fill(node.style.background_color):
        return True
    return any(_subtree_has_greenish_fill(child) for child in node.children)


def _background_is_selection_highlight(color: str | None) -> bool:
    """Detect light green selection washes distinct from neutral card greys."""
    return is_greenish_fill(color)


def button_is_payment_option_card(node: CleanDesignTreeNode) -> bool:
    """Tappable card with a title block and trailing circular payment radio."""
    from figma_flutter_agent.parser.interaction.buttons import (
        button_has_composite_row_body,
    )
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    if node.type != NodeType.BUTTON or not node.style.background_color:
        return False
    if not button_has_composite_row_body(node):
        return False
    return any(layout_fact_hosts_payment_selection_indicator(item) for item in _descendant_nodes(node, 6))


def payment_selection_circle_node(root: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the bordered circular badge inside a payment selection margin column."""
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    for item in _descendant_nodes(root, 5):
        width = item.sizing.width
        height = item.sizing.height
        if width is None or height is None:
            continue
        if not (14.0 <= float(width) <= 24.0 and 14.0 <= float(height) <= 24.0):
            continue
        if abs(float(width) - float(height)) > 2.0:
            continue
        if item.style.border_color and item.style.border_width:
            return item
    return None


def layout_fact_compact_radio_glyph(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Radio control with an external label sibling should emit a glyph, not a ListTile."""
    if node.type != NodeType.RADIO or parent_node is None:
        return False
    if parent_node.type not in {NodeType.ROW, NodeType.COLUMN}:
        return False
    return any(
        child.type == NodeType.TEXT and child.id != node.id for child in parent_node.children
    )


def payment_option_button_is_selected(node: CleanDesignTreeNode | None) -> bool:
    """Return True when an option-card button uses the selected highlight fill."""
    if node is None or node.type != NodeType.BUTTON:
        return False
    if _background_is_selection_highlight(node.style.background_color):
        return True
    return _subtree_has_greenish_fill(node)
