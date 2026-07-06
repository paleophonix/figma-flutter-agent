"""Regression tests for visible vector asset binding validation."""

from __future__ import annotations

import pytest

from figma_flutter_agent.assets.vector_binding import (
    assert_visible_vectors_bound,
    collect_unbound_visible_vector_ids,
)
from figma_flutter_agent.errors import MissingVectorAssetError
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def _visible_vector_node(*, asset_key: str | None = None) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="I_test;vector",
        name="Vector",
        type=NodeType.VECTOR,
        sizing=Sizing(width=13.3, height=13.3),
        style=NodeStyle(background_color="0xFFFFFFFF"),
        vector_asset_key=asset_key,
    )


def test_collect_unbound_visible_vector_ids_lists_missing_assets() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        children=[_visible_vector_node()],
    )
    assert collect_unbound_visible_vector_ids(root) == ["I_test;vector"]


def test_assert_visible_vectors_bound_strict_raises_named_error() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        children=[_visible_vector_node()],
    )
    with pytest.raises(MissingVectorAssetError, match="I_test;vector"):
        assert_visible_vectors_bound(
            root,
            strict=True,
            failed_export_node_ids=frozenset({"I_test;vector"}),
        )


def test_assert_visible_vectors_bound_non_strict_returns_ids() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="Signal",
        type=NodeType.STACK,
        sizing=Sizing(width=16.0, height=16.0),
        children=[_visible_vector_node(asset_key="assets/icons/test.svg")],
    )
    assert assert_visible_vectors_bound(root, strict=True) == []
