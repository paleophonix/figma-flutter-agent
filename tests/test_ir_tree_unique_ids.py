"""Duplicate node id fail-fast (ROB-09)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import index_clean_tree, validate_unique_node_ids
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_validate_unique_node_ids_raises_on_duplicate() -> None:
    duplicate = CleanDesignTreeNode(
        id="dup",
        name="Child",
        type=NodeType.TEXT,
        text="A",
        sizing=Sizing(width=10.0, height=10.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=100.0, height=100.0),
        children=[
            duplicate,
            duplicate.model_copy(update={"text": "B"}),
        ],
    )
    with pytest.raises(GenerationError, match="duplicate node id 'dup'"):
        validate_unique_node_ids(root)


def test_index_clean_tree_validates_before_indexing() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=100.0, height=100.0),
        children=[
            CleanDesignTreeNode(
                id="child",
                name="Child",
                type=NodeType.TEXT,
                text="Hi",
                sizing=Sizing(width=10.0, height=10.0),
            )
        ],
    )
    indexed = index_clean_tree(root)
    assert indexed["child"].text == "Hi"
