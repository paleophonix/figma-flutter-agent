"""Figma node-id helpers for render boundaries."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode


def collect_descendant_figma_ids(node: CleanDesignTreeNode) -> list[str]:
    """Return Figma node ids for all descendants (depth-first, pre-order)."""
    ids: list[str] = []
    for child in node.children:
        ids.append(child.id)
        ids.extend(collect_descendant_figma_ids(child))
    return ids
