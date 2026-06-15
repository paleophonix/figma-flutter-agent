"""Clean-tree text descendant helpers."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def subtree_has_text_descendant(node: CleanDesignTreeNode) -> bool:
    """Return True when any descendant is a ``TEXT`` node (LAW-COLLAPSE-CONSERVE).

    Args:
        node: Clean-tree root to inspect.

    Returns:
        True when a presentational text leaf exists anywhere under ``node``.
    """
    for child in node.children:
        if child.type == NodeType.TEXT:
            return True
        if subtree_has_text_descendant(child):
            return True
    return False


__all__ = ["subtree_has_text_descendant"]
