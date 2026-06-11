"""E0.0 conservation harness (multiset + z-order invariants)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.tree import default_screen_ir, merge_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)
from tests.support.conservation import (
    assert_node_multiset_preserved,
    assert_stack_z_order_preserved,
)


def _row_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="stack:root",
        name="Row",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="b", name="B", type=NodeType.TEXT, text="B"),
        ],
    )


def test_assert_node_multiset_preserved_passes_on_identity_merge() -> None:
    tree = _row_stack()
    assert_node_multiset_preserved(tree, default_screen_ir(tree))


def test_assert_stack_z_order_preserved_detects_reorder() -> None:
    clean = _row_stack()
    merged = merge_screen_ir(
        clean,
        ScreenIr(
            root=WidgetIrNode(
                figma_id="stack:root",
                kind=WidgetIrKind.STACK,
                children=[
                    WidgetIrNode(figma_id="b", kind=WidgetIrKind.AUTO),
                    WidgetIrNode(figma_id="a", kind=WidgetIrKind.AUTO),
                ],
            ),
            stack_child_order=["b", "a"],
        ),
    )
    assert_stack_z_order_preserved(clean, merged)
