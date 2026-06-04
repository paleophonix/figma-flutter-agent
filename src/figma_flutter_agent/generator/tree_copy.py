"""Immutable clean-tree helpers (WP-B): deep copy, hashing, structural updates."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode


def deep_copy_clean_tree(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Return a deep copy of a clean tree suitable for in-place guard passes."""
    return node.model_copy(deep=True)


def hash_clean_tree(node: CleanDesignTreeNode) -> str:
    """Stable content hash for side-effect-free validation tests."""
    payload = node.model_dump(mode="json", by_alias=True)
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def map_clean_tree(
    node: CleanDesignTreeNode,
    mapper: Callable[[CleanDesignTreeNode], CleanDesignTreeNode],
) -> CleanDesignTreeNode:
    """Apply ``mapper`` to every node in the tree (bottom-up rebuild)."""

    def walk(current: CleanDesignTreeNode) -> CleanDesignTreeNode:
        mapped_children = [walk(child) for child in current.children]
        with_children = current.model_copy(update={"children": mapped_children})
        return mapper(with_children)

    return walk(node)


def replace_clean_tree_node(
    root: CleanDesignTreeNode,
    node_id: str,
    replacer: Callable[[CleanDesignTreeNode], CleanDesignTreeNode],
) -> CleanDesignTreeNode:
    """Return a new tree with one node replaced via ``replacer``."""

    def mapper(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        if node.id == node_id:
            return replacer(node)
        return node

    return map_clean_tree(root, mapper)


def patch_clean_tree_node(
    root: CleanDesignTreeNode,
    node_id: str,
    **updates: Any,
) -> CleanDesignTreeNode:
    """Return a new tree with shallow field updates on ``node_id``."""

    def replacer(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        return node.model_copy(update=updates)

    return replace_clean_tree_node(root, node_id, replacer)
