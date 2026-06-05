"""Baseline oracle learning and bundled-font fallback."""

from __future__ import annotations

import pytest

from figma_flutter_agent.fonts.metrics import typographic_baseline_ratio
from figma_flutter_agent.generator.geometry.baseline import (
    clear_baseline_oracle_cache,
    flutter_baseline_offset,
    learn_baseline_ratios_from_tree,
    resolve_baseline_ratio,
    seed_baseline_oracle,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


@pytest.fixture(autouse=True)
def _reset_baseline_cache() -> None:
    clear_baseline_oracle_cache()


def _text_node(
    *,
    node_id: str,
    family: str,
    font_size: float,
    glyph_top_offset: float,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Label",
        type=NodeType.TEXT,
        style=NodeStyle(
            font_family=family,
            font_size=font_size,
            glyph_top_offset=glyph_top_offset,
        ),
    )


def test_learn_baseline_ratios_from_tree_median() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        children=[
            _text_node(
                node_id="a",
                family="Golos Text",
                font_size=16.0,
                glyph_top_offset=11.52,
            ),
            _text_node(
                node_id="b",
                family="Golos Text",
                font_size=20.0,
                glyph_top_offset=15.0,
            ),
        ],
    )
    learned = learn_baseline_ratios_from_tree(tree)
    assert learned["golos text"] == pytest.approx(0.735, abs=0.001)


def test_seed_baseline_oracle_uses_learned_family() -> None:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.COLUMN,
        children=[
            _text_node(
                node_id="a",
                family="Golos Text",
                font_size=16.0,
                glyph_top_offset=11.52,
            ),
        ],
    )
    seed_baseline_oracle(tree)
    assert resolve_baseline_ratio("Golos Text") == pytest.approx(0.72, abs=0.001)
    assert flutter_baseline_offset(16.0, font_family="Golos Text") == pytest.approx(
        11.52,
        abs=0.01,
    )


def test_unknown_family_uses_default_without_builtin_warning() -> None:
    assert resolve_baseline_ratio("Totally Custom Sans") == 0.72


def test_typographic_baseline_ratio_rejects_invalid_bytes() -> None:
    assert typographic_baseline_ratio(b"not-a-font") is None
