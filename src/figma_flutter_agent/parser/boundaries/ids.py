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


def collect_descendant_conservation_ids(node: CleanDesignTreeNode) -> list[str]:
    """Return descendant ids for cluster dedup flatten metadata.

    Includes live child ids plus ``flatten_figma_node_ids`` already carried by
    nested pruned stubs so ``CP0b_reprune`` multiset conservation stays intact.
    """
    ids: list[str] = []
    for child in node.children:
        ids.append(child.id)
        ids.extend(child.flatten_figma_node_ids or ())
        ids.extend(collect_descendant_conservation_ids(child))
    return ids
