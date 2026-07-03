"""Tests for clean-tree cycle guard on dedup walks (04-P0-1)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.parser.dedup.hydrate import hydrate_pruned_cluster_instances
from figma_flutter_agent.parser.dedup.prune import prune_extracted_subtree_nodes
from figma_flutter_agent.parser.tree_walk import CleanTreeCycleError, walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _cycle_tree() -> CleanDesignTreeNode:
    a = CleanDesignTreeNode(id="a", name="a", type=NodeType.CONTAINER, children=[])
    b = CleanDesignTreeNode(id="b", name="b", type=NodeType.CONTAINER, children=[])
    a.children = [b]
    b.children = [a]
    return a


def test_dedup_cluster_collect_cycle_error() -> None:
    root = _cycle_tree()
    with pytest.raises(CleanTreeCycleError) as exc_info:
        prune_extracted_subtree_nodes(root, frozenset({"never"}))
    assert exc_info.value.phase == "dedup_prune_extracted"


def test_prune_extracted_subtree_cycle_error_has_path() -> None:
    root = _cycle_tree()
    with pytest.raises(CleanTreeCycleError) as exc_info:
        prune_extracted_subtree_nodes(root, frozenset({"missing"}))
    assert exc_info.value.path


def test_hydrate_cycle_error_has_node_id() -> None:
    root = _cycle_tree()
    with pytest.raises(CleanTreeCycleError) as exc_info:
        hydrate_pruned_cluster_instances(root)
    assert exc_info.value.node_id in {"a", "b"}


def test_walk_clean_tree_phase_label() -> None:
    root = _cycle_tree()
    with pytest.raises(CleanTreeCycleError) as exc_info:
        walk_clean_tree(root, lambda _n: None, phase="inventory_test")
    assert exc_info.value.phase == "inventory_test"
