"""Selection affordances for payment and option cards."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_SELECTION_GREEN = "0xFF28A745"
_DEFAULT_CARD_FILL = "0xFFF6F6F2"


def hosts_payment_selection_indicator(node: CleanDesignTreeNode) -> bool:
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
        child.type in {NodeType.ROW, NodeType.STACK}
        and child.style.border_color
        for child in node.children
    )


def _node_has_green_selection_fill(node: CleanDesignTreeNode) -> bool:
    if node.style.background_color == _SELECTION_GREEN:
        return True
    return any(_node_has_green_selection_fill(child) for child in node.children)


def _background_is_selection_highlight(color: str | None) -> bool:
    """Detect light green selection washes distinct from neutral card greys."""
    if not color or color == _DEFAULT_CARD_FILL:
        return False
    raw = color.removeprefix("0x").removeprefix("0X")
    if len(raw) != 8:
        return False
    try:
        value = int(raw, 16)
    except ValueError:
        return False
    red = (value >> 16) & 0xFF
    green = (value >> 8) & 0xFF
    blue = value & 0xFF
    if green <= red or green <= blue:
        return False
    return green - red >= 6 and green - blue >= 6 and green >= 220


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
    return any(
        hosts_payment_selection_indicator(item) for item in _descendant_nodes(node, 6)
    )


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


def payment_option_button_is_selected(node: CleanDesignTreeNode | None) -> bool:
    """Return True when an option-card button uses the selected highlight fill."""
    if node is None or node.type != NodeType.BUTTON:
        return False
    if _background_is_selection_highlight(node.style.background_color):
        return True
    return _node_has_green_selection_fill(node)


