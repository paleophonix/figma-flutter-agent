"""T0.3: layout reconcile runs once per plan path."""

from __future__ import annotations

from unittest.mock import patch

from figma_flutter_agent.generator.normalize import reconcile_layout_tree
from figma_flutter_agent.parser.layout import reconcile_stack_placements_in_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_reconcile_layout_tree_calls_stack_reconcile_once() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        children=[],
    )
    with patch(
        "figma_flutter_agent.parser.layout.reconcile_stack_placements_in_tree",
        wraps=reconcile_stack_placements_in_tree,
    ) as stack_mock:
        reconcile_layout_tree(root)
    assert stack_mock.call_count == 1
