"""Tests for scrollable frames mapped to ListView in deterministic layout."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.parser.layout import extract_scroll_axis
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def test_extract_scroll_axis_maps_figma_overflow() -> None:
    assert extract_scroll_axis({"overflowDirection": "VERTICAL_SCROLLING"}) == "vertical"
    assert extract_scroll_axis({"overflowDirection": "HORIZONTAL_SCROLLING"}) == "horizontal"
    assert extract_scroll_axis({"overflowDirection": "BOTH"}) == "both"
    assert extract_scroll_axis({}) == "none"


def test_vertical_scroll_frame_renders_list_view() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_scroll_vertical_sample.json").read_text(encoding="utf-8")
    )
    tree, _, _, _ = build_clean_tree(root)

    assert tree.scroll_axis == "vertical"
    layout = render_layout_file(tree, feature_name="feed", uses_svg=False)[
        "lib/generated/feed_layout.dart"
    ]

    assert "ListView(" in layout
    assert "padding: const EdgeInsets.fromLTRB(12.0, 8.0, 12.0, 8.0)" in layout
    assert "Text('Item A'" in layout
    assert "Text('Item B'" in layout
    assert "Column(" not in layout.split("ListView(")[0][-20:]


def test_horizontal_scroll_row_renders_horizontal_list_view() -> None:
    row_tree = CleanDesignTreeNode(
        id="1",
        name="Carousel",
        type=NodeType.ROW,
        scroll_axis="horizontal",
        children=[
            CleanDesignTreeNode(id="2", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="3", name="B", type=NodeType.TEXT, text="B"),
        ],
    )

    layout = render_layout_file(row_tree, feature_name="carousel", uses_svg=False)[
        "lib/generated/carousel_layout.dart"
    ]

    assert "ListView(scrollDirection: Axis.horizontal" in layout
    assert "Row(" not in layout


def test_nested_vertical_scroll_in_column_uses_shrink_wrap() -> None:
    scroll_child = CleanDesignTreeNode(
        id="2",
        name="List",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=[CleanDesignTreeNode(id="3", name="Row", type=NodeType.TEXT, text="X")],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[scroll_child],
    )

    layout = render_layout_file(parent, feature_name="screen", uses_svg=False)[
        "lib/generated/screen_layout.dart"
    ]

    assert "shrinkWrap: true" in layout
    assert "ClampingScrollPhysics" in layout


def test_fill_height_scroll_in_column_uses_expanded() -> None:
    scroll_child = CleanDesignTreeNode(
        id="2",
        name="List",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        sizing=Sizing(height_mode=SizingMode.FILL),
        children=[CleanDesignTreeNode(id="3", name="Row", type=NodeType.TEXT, text="X")],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[scroll_child],
    )

    layout = render_layout_file(parent, feature_name="screen_fill", uses_svg=False)[
        "lib/generated/screen_fill_layout.dart"
    ]

    assert "Expanded(child: RepaintBoundary(child: ListView(" in layout


def test_horizontal_scroll_stack_with_overflow_row_renders_list_view() -> None:
    cards = [
        CleanDesignTreeNode(id=f"c{i}", name="Card", type=NodeType.TEXT, text=f"C{i}")
        for i in range(3)
    ]
    row = CleanDesignTreeNode(
        id="row",
        name="scroll_frame",
        type=NodeType.ROW,
        sizing=Sizing(width=1024.0, height=296.0),
        children=cards,
    )
    stack = CleanDesignTreeNode(
        id="slider",
        name="Content row slider",
        type=NodeType.STACK,
        scroll_axis="horizontal",
        sizing=Sizing(width=390.0, height=296.0),
        children=[row],
    )

    layout = render_layout_file(stack, feature_name="slider", uses_svg=False)[
        "lib/generated/slider_layout.dart"
    ]

    assert "ListView(scrollDirection: Axis.horizontal" in layout
    assert "OverflowBox(" not in layout


def test_both_axis_scroll_renders_nested_single_child_scroll_view() -> None:
    scroll_child = CleanDesignTreeNode(
        id="2",
        name="Panel",
        type=NodeType.COLUMN,
        scroll_axis="both",
        children=[
            CleanDesignTreeNode(id="3", name="Wide", type=NodeType.TEXT, text="Content"),
        ],
    )

    layout = render_layout_file(scroll_child, feature_name="panel", uses_svg=False)[
        "lib/generated/panel_layout.dart"
    ]

    assert layout.count("SingleChildScrollView(") >= 2
    assert "scrollDirection: Axis.horizontal" in layout
