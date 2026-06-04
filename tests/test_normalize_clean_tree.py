"""Tests for unified clean-tree canonicalization (WP-A / INV-1)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.generator.ir_validate import apply_ir_guards
from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)


def _minimal_stack_screen() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[
            CleanDesignTreeNode(
                id="btn",
                name="CTA",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(
                    left=10.0,
                    top=10.0,
                    width=16.0,
                    height=16.0,
                ),
            ),
        ],
    )


def test_normalize_applies_min_touch_target_guard() -> None:
    root = _minimal_stack_screen()
    normalized = normalize_clean_tree(root)
    assert normalized.children[0].min_touch_target == 44.0
    assert root.children[0].min_touch_target is None


def test_normalize_matches_reconcile_then_default_ir_guards() -> None:
    from figma_flutter_agent.generator.normalize import reconcile_layout_tree

    root = _minimal_stack_screen()
    normalized = normalize_clean_tree(root)
    reconciled = reconcile_layout_tree(root)
    guarded = apply_ir_guards(default_screen_ir(reconciled), reconciled)
    assert normalized.children[0].min_touch_target == guarded.children[0].min_touch_target
