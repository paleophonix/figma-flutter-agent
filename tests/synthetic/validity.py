"""Synthetic tree validity helpers."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode


def node_ids(tree: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(tree)
    return ids


def is_connected(tree: CleanDesignTreeNode) -> bool:
    return bool(tree.id) and all(is_connected(child) for child in tree.children)
