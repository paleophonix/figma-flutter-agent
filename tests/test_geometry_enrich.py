"""Tests for geometry enrichment on clean design trees."""

from __future__ import annotations

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.parser.geometry import enrich_clean_tree_from_geometry, find_node_by_id
from figma_flutter_agent.schemas import NodeType


def test_enrich_promotes_social_row_to_button() -> None:
    tree = load_layout_tree("music_v2_ru_dirty")
    enrich_clean_tree_from_geometry(tree)
    row = find_node_by_id(tree, "social-row")
    assert row is not None
    assert row.type == NodeType.BUTTON


def test_enrich_idempotent_for_music_v2() -> None:
    tree = load_layout_tree("music_v2")
    enrich_clean_tree_from_geometry(tree)
    row = find_node_by_id(tree, "social-row")
    assert row is not None
    assert row.type == NodeType.BUTTON
    enrich_clean_tree_from_geometry(tree)
    assert row.type == NodeType.BUTTON
