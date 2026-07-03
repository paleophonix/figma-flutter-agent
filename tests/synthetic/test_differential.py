"""Hypothesis-backed conservation properties (Program 08 P1)."""

from __future__ import annotations

import copy

import pytest
from hypothesis import given

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_node_multiset_preserved,
)
from tests.synthetic.builders import column_tree
from tests.synthetic.strategies import depth_strategy


@pytest.mark.property_fast
@given(depth=depth_strategy)
def test_duplicate_instance_preserves_multiset(depth: int) -> None:
    tree = column_tree(depth=depth)
    duplicate = copy.deepcopy(tree)
    assert check_node_multiset_preserved(tree, duplicate) == []


@pytest.mark.property_fast
@given(depth=depth_strategy)
def test_sibling_permutation_preserves_multiset(depth: int) -> None:
    if depth < 2:
        return
    tree = column_tree(depth=depth)
    permuted = copy.deepcopy(tree)
    permuted.children = list(reversed(permuted.children))
    assert check_node_multiset_preserved(tree, permuted) == []
