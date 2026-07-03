"""Property-based conservation smoke tests (Program 08 P0-3)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_graph_sync,
    check_node_multiset_preserved,
    check_stack_paint_order_preserved,
)
from figma_flutter_agent.generator.geometry.invariants.type_truth import capture_type_baseline
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from tests.synthetic.builders import column_tree, stack_pair


@pytest.mark.property_fast
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_multiset_preserved_on_identity_transform(depth: int) -> None:
    tree = column_tree(depth=depth)
    clone = column_tree(depth=depth)
    assert check_node_multiset_preserved(tree, clone) == []


@pytest.mark.property_fast
def test_graph_sync_on_default_screen_ir() -> None:
    tree = stack_pair()
    screen_ir = default_screen_ir(tree)
    assert check_graph_sync(screen_ir, tree) == []


@pytest.mark.property_fast
def test_paint_order_stable_on_clone() -> None:
    tree = stack_pair()
    clone = stack_pair()
    assert check_stack_paint_order_preserved(tree, clone) == []


@pytest.mark.property_fast
def test_type_baseline_matches_tree(depth: int = 2) -> None:
    tree = column_tree(depth=depth)
    baseline = capture_type_baseline(tree)
    assert baseline["root"] == tree.type
    assert len(baseline) == depth + 1
