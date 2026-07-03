"""Nightly property budget (Program 08 P2, advisory)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_node_multiset_preserved,
)
from tests.synthetic.builders import column_tree
from tests.synthetic.strategies import depth_strategy


@pytest.mark.property_nightly
@given(depth=depth_strategy)
@settings(max_examples=50)
def test_nightly_multiset_smoke(depth: int) -> None:
    tree = column_tree(depth=depth)
    assert check_node_multiset_preserved(tree, tree) == []
