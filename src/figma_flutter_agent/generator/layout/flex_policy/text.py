"""Text-specific predicates for flex policy."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def text_in_card_metadata_rail(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
    *,
    parent_type: NodeType | None = None,
) -> bool:
    """True when copy sits in the narrow right-hand metadata rail of a list card."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        row_is_card_composite_body,
        row_is_status_pill_badge,
        _CARD_METADATA_STACK_MAX_WIDTH,
    )
    from figma_flutter_agent.generator.layout.flex_policy.column import column_is_card_metadata_slot

    if node.type != NodeType.TEXT or parent_node is None:
        return False
    if row_is_status_pill_badge(parent_node):
        return False
    if parent_type == NodeType.COLUMN and column_is_card_metadata_slot(parent_node):
        return True
    if parent_type == NodeType.ROW and row_is_card_composite_body(parent_node):
        child_width = float(node.sizing.width or 0.0)
        return 0 < child_width <= _CARD_METADATA_STACK_MAX_WIDTH
    if parent_node.type == NodeType.STACK:
        width = parent_node.sizing.width
        return width is not None and 0 < width <= _CARD_METADATA_STACK_MAX_WIDTH
    return False


def _text_has_multiple_lines(node: CleanDesignTreeNode) -> bool:
    """Return True when Figma text content spans more than one line."""
    if node.type != NodeType.TEXT:
        return False
    raw = (node.text or "").strip()
    if not raw:
        return False
    return "\n" in raw or len(raw.splitlines()) > 1


def _subtree_has_input(node: CleanDesignTreeNode) -> bool:
    """Return True when an ``INPUT`` appears anywhere under ``node``."""
    if node.type == NodeType.INPUT:
        return True
    return any(_subtree_has_input(child) for child in node.children)
