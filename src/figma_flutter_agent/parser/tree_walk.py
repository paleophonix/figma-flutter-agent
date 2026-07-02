"""Cycle-safe clean-tree depth-first walks."""

from __future__ import annotations

from collections.abc import Callable

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import CleanDesignTreeNode


class CleanTreeCycleError(GenerationError):
    """Raised when a clean-tree walk revisits the same node object."""


def walk_clean_tree(
    root: CleanDesignTreeNode,
    visitor: Callable[[CleanDesignTreeNode], None],
    *,
    post_order: bool = False,
) -> None:
    """Visit every node in ``root`` once; fail loud on object-identity cycles.

    Args:
        root: Clean design tree root.
        visitor: Callback invoked per node.
        post_order: When true, invoke ``visitor`` after children (post-order DFS).

    Raises:
        CleanTreeCycleError: When the same node instance appears twice on the walk path.
    """
    visited: set[int] = set()

    def dfs(node: CleanDesignTreeNode) -> None:
        node_key = id(node)
        if node_key in visited:
            msg = "Clean tree traversal cycle detected during compiler walk"
            raise CleanTreeCycleError(msg)
        visited.add(node_key)
        if not post_order:
            visitor(node)
        for child in node.children:
            dfs(child)
        if post_order:
            visitor(node)

    dfs(root)


def walk_clean_tree_with_parent(
    root: CleanDesignTreeNode,
    visitor: Callable[[CleanDesignTreeNode, CleanDesignTreeNode | None], None],
) -> None:
    """Pre-order DFS with parent pointer; fail loud on object-identity cycles.

    Args:
        root: Clean design tree root.
        visitor: Callback invoked as ``visitor(node, parent_node)``.

    Raises:
        CleanTreeCycleError: When the same node instance appears twice on the walk path.
    """
    visited: set[int] = set()

    def dfs(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        node_key = id(node)
        if node_key in visited:
            msg = "Clean tree traversal cycle detected during compiler walk"
            raise CleanTreeCycleError(msg)
        visited.add(node_key)
        visitor(node, parent)
        for child in node.children:
            dfs(child, node)

    dfs(root, None)
