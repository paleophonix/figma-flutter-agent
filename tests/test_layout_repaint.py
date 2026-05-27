"""Tests for RepaintBoundary wrapping in deterministic layout."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_carousel_fixture_wraps_page_view_in_repaint_boundary() -> None:
    root = json.loads(Path("tests/fixtures/figma_carousel_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    layout = render_layout_file(tree, feature_name="hero", uses_svg=False)[
        "lib/generated/hero_layout.dart"
    ]

    assert (
        "RepaintBoundary(child: AspectRatio" in layout
        or "RepaintBoundary(child: PageView" in layout
    )


def test_vertical_scroll_list_uses_repaint_boundary() -> None:
    scroll = CleanDesignTreeNode(
        id="1",
        name="Feed",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=[
            CleanDesignTreeNode(id="2", name="Item", type=NodeType.TEXT, text="A"),
        ],
    )

    layout = render_layout_file(scroll, feature_name="feed", uses_svg=False)[
        "lib/generated/feed_layout.dart"
    ]

    assert "RepaintBoundary(child: ListView" in layout
