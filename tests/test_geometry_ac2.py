"""AC-2: geometry classifier ignores layer names and marketing copy."""

from __future__ import annotations

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.parser.geometry import find_social_auth_row, social_auth_row_confidence
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, StackPlacement


def test_music_v2_and_ru_dirty_share_geometry_scores() -> None:
    clean = load_layout_tree("music_v2")
    dirty = load_layout_tree("music_v2_ru_dirty")
    clean_row = find_social_auth_row(clean)
    dirty_row = find_social_auth_row(dirty)
    assert clean_row is not None
    assert dirty_row is not None
    assert clean_row.id == dirty_row.id == "social-row"
    assert social_auth_row_confidence(clean_row) == social_auth_row_confidence(dirty_row)


def test_geometry_does_not_use_name_or_text_fields() -> None:
    row = CleanDesignTreeNode(
        id="social-row",
        name="Rectangle 999",
        type=NodeType.ROW,
        text="SHOULD NOT MATTER",
        children=[
            CleanDesignTreeNode(
                id="i",
                name="x",
                type=NodeType.VECTOR,
                stack_placement=StackPlacement(
                    left=16.0,
                    top=16.0,
                    width=24.0,
                    height=24.0,
                ),
            ),
            CleanDesignTreeNode(
                id="t",
                name="y",
                type=NodeType.TEXT,
                text="IGNORED",
                stack_placement=StackPlacement(
                    left=56.0,
                    top=20.0,
                    width=240.0,
                    height=16.0,
                ),
            ),
        ],
        stack_placement=StackPlacement(left=40.0, top=520.0, width=334.0, height=56.0),
    )
    assert social_auth_row_confidence(row) >= 0.7
