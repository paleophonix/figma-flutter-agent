"""Test helpers re-exporting production conservation validators (EPIC 1)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_stack_paint_order_preserved,
    conservation_node_multiset,
)
from figma_flutter_agent.generator.ir.tree import merge_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr


def assert_node_multiset_preserved(
    clean_tree: CleanDesignTreeNode,
    screen_ir: ScreenIr,
) -> None:
    """Assert merge preserves the multiset of Figma node ids (minus omit list)."""
    omit_ids = frozenset(screen_ir.omit_figma_ids or [])
    expected = conservation_node_multiset(clean_tree, omit_ids=omit_ids)
    merged = merge_screen_ir(clean_tree, screen_ir)
    actual = conservation_node_multiset(merged, omit_ids=omit_ids)
    assert actual == expected


def assert_stack_z_order_preserved(
    clean_tree: CleanDesignTreeNode,
    result_tree: CleanDesignTreeNode,
) -> None:
    """Assert STACK paint order matches the source clean tree at every stack id."""
    violations = check_stack_paint_order_preserved(clean_tree, result_tree)
    assert not violations, violations
