"""Cycle-safe clean-tree depth-first walks."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import CleanDesignTreeNode

Carry = TypeVar("Carry")


class CleanTreeCycleError(GenerationError):
    """Raised when a clean-tree walk revisits the same node object.

    Attributes:
        node_id: Figma node id of the repeated instance when available.
        path: Human-readable walk path of node ids leading to the cycle.
        phase: Compiler phase label (e.g. ``dedup_prune``, ``dedup_hydrate``).
    """

    def __init__(
        self,
        message: str,
        *,
        node_id: str | None = None,
        path: tuple[str, ...] = (),
        phase: str | None = None,
    ) -> None:
        super().__init__(message)
        self.node_id = node_id
        self.path = path
        self.phase = phase


def _raise_cycle(
    node: CleanDesignTreeNode,
    path_ids: list[str],
    *,
    phase: str | None,
) -> None:
    node_id = node.id or None
    path_tuple = tuple(path_ids)
    msg = (
        f"Clean tree traversal cycle detected during compiler walk"
        f" (node_id={node_id!r}, phase={phase!r}, path={'/'.join(path_tuple)})"
    )
    raise CleanTreeCycleError(msg, node_id=node_id, path=path_tuple, phase=phase)


def walk_clean_tree(
    root: CleanDesignTreeNode,
    visitor: Callable[[CleanDesignTreeNode], None],
    *,
    post_order: bool = False,
    phase: str | None = None,
) -> None:
    """Visit every node in ``root`` once; fail loud on object-identity cycles.

    Args:
        root: Clean design tree root.
        visitor: Callback invoked per node.
        post_order: When true, invoke ``visitor`` after children (post-order DFS).
        phase: Optional compiler phase label attached to ``CleanTreeCycleError``.

    Raises:
        CleanTreeCycleError: When the same node instance appears twice on the walk path.
    """
    visited: set[int] = set()

    def dfs(node: CleanDesignTreeNode, path_ids: list[str]) -> None:
        node_key = id(node)
        if node_key in visited:
            _raise_cycle(node, path_ids, phase=phase)
        visited.add(node_key)
        current_path = [*path_ids, node.id or "?"]
        if not post_order:
            visitor(node)
        for child in node.children:
            dfs(child, current_path)
        if post_order:
            visitor(node)

    dfs(root, [])


def walk_clean_tree_with_parent(
    root: CleanDesignTreeNode,
    visitor: Callable[[CleanDesignTreeNode, CleanDesignTreeNode | None], None],
    *,
    phase: str | None = None,
) -> None:
    """Pre-order DFS with parent pointer; fail loud on object-identity cycles.

    Args:
        root: Clean design tree root.
        visitor: Callback invoked as ``visitor(node, parent_node)``.
        phase: Optional compiler phase label attached to ``CleanTreeCycleError``.

    Raises:
        CleanTreeCycleError: When the same node instance appears twice on the walk path.
    """
    visited: set[int] = set()

    def dfs(
        node: CleanDesignTreeNode,
        parent: CleanDesignTreeNode | None,
        path_ids: list[str],
    ) -> None:
        node_key = id(node)
        if node_key in visited:
            _raise_cycle(node, path_ids, phase=phase)
        visited.add(node_key)
        current_path = [*path_ids, node.id or "?"]
        visitor(node, parent)
        for child in node.children:
            dfs(child, node, current_path)

    dfs(root, None, [])


def walk_clean_tree_with_carry(
    root: CleanDesignTreeNode,
    visitor: Callable[[CleanDesignTreeNode, Carry], None],
    carry: Callable[[CleanDesignTreeNode, Carry], Carry],
    initial: Carry,
    *,
    phase: str | None = None,
) -> None:
    """Pre-order DFS with downward-propagated carry state (cycle-safe).

    Args:
        root: Clean design tree root.
        visitor: ``visitor(node, carry)`` invoked pre-order.
        carry: ``carry(node, parent_carry)`` produces child carry state.
        initial: Carry state before visiting ``root``.
        phase: Optional compiler phase label for ``CleanTreeCycleError``.

    Raises:
        CleanTreeCycleError: When the same node instance appears twice on the walk path.
    """
    visited: set[int] = set()

    def dfs(node: CleanDesignTreeNode, state: Carry, path_ids: list[str]) -> None:
        node_key = id(node)
        if node_key in visited:
            _raise_cycle(node, path_ids, phase=phase)
        visited.add(node_key)
        current_path = [*path_ids, node.id or "?"]
        visitor(node, state)
        child_state = carry(node, state)
        for child in node.children:
            dfs(child, child_state, current_path)

    dfs(root, initial, [])
