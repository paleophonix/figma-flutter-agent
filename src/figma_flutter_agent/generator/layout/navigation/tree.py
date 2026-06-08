"""Tree queries for navigation layout planning."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def tree_contains_node_type(tree: CleanDesignTreeNode, node_type: NodeType) -> bool:
    """Return True when ``node_type`` appears anywhere in the clean tree."""
    if tree.type == node_type:
        return True
    return any(tree_contains_node_type(child, node_type) for child in tree.children)


def first_node_id_of_type(tree: CleanDesignTreeNode, node_type: NodeType) -> str | None:
    """Return the first ``node_type`` id in depth-first order."""
    if tree.type == node_type:
        return tree.id
    for child in tree.children:
        found = first_node_id_of_type(child, node_type)
        if found is not None:
            return found
    return None
