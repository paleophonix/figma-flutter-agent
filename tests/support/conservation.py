"""Standalone conservation helpers for EPIC 0 (promoted to E1.2 pass manager later)."""

from __future__ import annotations

from collections import Counter

from figma_flutter_agent.generator.ir.tree import merge_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, ScreenIr


def _collect_node_ids(root: CleanDesignTreeNode) -> list[str]:
    ids: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        ids.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _stack_child_orders(root: CleanDesignTreeNode) -> dict[str, list[str]]:
    orders: dict[str, list[str]] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        if node.type == NodeType.STACK:
            orders[node.id] = [child.id for child in node.children]
        for child in node.children:
            walk(child)

    walk(root)
    return orders


def assert_node_multiset_preserved(
    clean_tree: CleanDesignTreeNode,
    screen_ir: ScreenIr,
) -> None:
    """Assert merge preserves the multiset of Figma node ids (minus omit list)."""
    omit_ids = frozenset(screen_ir.omit_figma_ids or [])
    expected = Counter(
        node_id for node_id in _collect_node_ids(clean_tree) if node_id not in omit_ids
    )
    merged = merge_screen_ir(clean_tree, screen_ir)
    actual = Counter(_collect_node_ids(merged))
    assert actual == expected


def assert_stack_z_order_preserved(
    clean_tree: CleanDesignTreeNode,
    result_tree: CleanDesignTreeNode,
) -> None:
    """Assert STACK paint order matches the source clean tree at every stack id."""
    clean_orders = _stack_child_orders(clean_tree)
    result_orders = _stack_child_orders(result_tree)
    for stack_id, clean_order in clean_orders.items():
        assert result_orders.get(stack_id) == clean_order, (
            f"stack {stack_id!r}: expected {clean_order}, got {result_orders.get(stack_id)}"
        )
