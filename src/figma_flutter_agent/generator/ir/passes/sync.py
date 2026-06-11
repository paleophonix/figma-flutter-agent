"""Dual-graph synchronization utilities for IR layout passes."""

from __future__ import annotations

from collections.abc import Callable

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def index_ir_nodes(root: WidgetIrNode) -> dict[str, WidgetIrNode]:
    """Map figma id to IR node for the full screen IR tree."""
    indexed: dict[str, WidgetIrNode] = {}

    def walk(node: WidgetIrNode) -> None:
        indexed[node.figma_id] = node
        for child in node.children:
            walk(child)

    walk(root)
    return indexed


def update_ir_subtree(
    root: WidgetIrNode,
    node_id: str,
    updater: Callable[[WidgetIrNode], WidgetIrNode],
) -> WidgetIrNode:
    """Return a copy of ``root`` with ``updater`` applied to the node matching ``node_id``."""
    if root.figma_id == node_id:
        return updater(root)
    if not root.children:
        return root
    return root.model_copy(
        update={
            "children": [
                update_ir_subtree(child, node_id, updater) for child in root.children
            ],
        },
    )


def update_clean_subtree(
    root: CleanDesignTreeNode,
    node_id: str,
    updater: Callable[[CleanDesignTreeNode], CleanDesignTreeNode],
) -> CleanDesignTreeNode:
    """Return a copy of ``root`` with ``updater`` applied to the node matching ``node_id``."""
    if root.id == node_id:
        return updater(root)
    if not root.children:
        return root
    return root.model_copy(
        update={
            "children": [
                update_clean_subtree(child, node_id, updater) for child in root.children
            ],
        },
    )


def ir_kind_for_node_type(node_type: str) -> WidgetIrKind:
    """Map clean-tree container type to IR kind."""
    mapping = {
        "COLUMN": WidgetIrKind.COLUMN,
        "ROW": WidgetIrKind.ROW,
        "WRAP": WidgetIrKind.WRAP,
        "STACK": WidgetIrKind.STACK,
    }
    return mapping.get(node_type, WidgetIrKind.AUTO)


def walk_clean_postorder(
    root: CleanDesignTreeNode,
    visitor: Callable[[CleanDesignTreeNode], CleanDesignTreeNode],
) -> CleanDesignTreeNode:
    """Apply ``visitor`` to each node in post-order (children first)."""
    updated_children = [walk_clean_postorder(child, visitor) for child in root.children]
    node = root.model_copy(update={"children": updated_children})
    return visitor(node)


def walk_ir_postorder(
    root: WidgetIrNode,
    visitor: Callable[[WidgetIrNode], WidgetIrNode],
) -> WidgetIrNode:
    """Apply ``visitor`` to each IR node in post-order."""
    updated_children = [walk_ir_postorder(child, visitor) for child in root.children]
    node = root.model_copy(update={"children": updated_children})
    return visitor(node)


def replace_screen_ir_root(screen_ir: ScreenIr, new_root: WidgetIrNode) -> ScreenIr:
    """Return a copy of ``screen_ir`` with an updated root node."""
    return screen_ir.model_copy(update={"root": new_root})


__all__ = [
    "index_ir_nodes",
    "ir_kind_for_node_type",
    "replace_screen_ir_root",
    "update_clean_subtree",
    "update_ir_subtree",
    "walk_clean_postorder",
    "walk_ir_postorder",
]
