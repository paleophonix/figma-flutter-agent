"""Tests for carousel semantic layout rendering."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.parser.components import match_semantic_type_from_name
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def test_match_semantic_type_carousel() -> None:
    assert match_semantic_type_from_name("Hero Carousel") is NodeType.CAROUSEL
    assert match_semantic_type_from_name("Image Slideshow") is NodeType.CAROUSEL


def test_carousel_fixture_renders_page_view() -> None:
    root = json.loads(Path("tests/fixtures/figma_carousel_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    assert tree.type == NodeType.CAROUSEL
    layout = render_layout_file(tree, feature_name="hero", uses_svg=False)[
        "lib/generated/hero_layout.dart"
    ]

    assert "PageView(children:" in layout
    assert "AspectRatio(aspectRatio:" in layout
    assert "SizedBox(height:" not in layout
    assert "Text('Welcome'" in layout
    assert "Text('Explore'" in layout


def test_carousel_fill_height_uses_expanded() -> None:
    carousel = CleanDesignTreeNode(
        id="2",
        name="Banner Carousel",
        type=NodeType.CAROUSEL,
        sizing=Sizing(width=360, height=200, height_mode=SizingMode.FILL),
        children=[CleanDesignTreeNode(id="3", name="Slide", type=NodeType.TEXT, text="Hi")],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[carousel],
    )

    layout = render_layout_file(parent, feature_name="home", uses_svg=False)[
        "lib/generated/home_layout.dart"
    ]

    assert "Expanded(child: RepaintBoundary(child: PageView(" in layout
