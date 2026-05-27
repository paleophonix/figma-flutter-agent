"""Tests for Figma GRID auto-layout mapped to GridView.count."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.parser.layout import (
    extract_grid_column_count,
    extract_grid_gaps,
    infer_container_type,
)
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def test_infer_container_type_maps_grid_layout_mode() -> None:
    node = {"layoutMode": "GRID", "gridColumnCount": 3}

    assert infer_container_type(node) == NodeType.GRID


def test_extract_grid_metrics() -> None:
    node = {
        "gridColumnCount": 3,
        "gridRowGap": 10,
        "gridColumnGap": 14,
        "itemSpacing": 4,
    }

    assert extract_grid_column_count(node, child_count=6) == 3
    assert extract_grid_gaps(node) == (10.0, 14.0)


def test_grid_frame_renders_grid_view_count() -> None:
    root = json.loads(Path("tests/fixtures/figma_grid_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    assert tree.type == NodeType.GRID
    assert tree.grid_column_count == 2
    assert tree.grid_row_gap == 12.0
    assert tree.grid_column_gap == 16.0

    layout = render_layout_file(tree, feature_name="products", uses_svg=False)[
        "lib/generated/products_layout.dart"
    ]

    assert "GridView.count(" in layout
    assert "final crossAxisCount" in layout
    assert "LayoutBuilder(" in layout
    assert "AppBreakpoints.isMobileLarge(width)" in layout
    assert "AppBreakpoints.isDesktop(width)" in layout
    assert "mainAxisSpacing: 12.0" in layout
    assert "crossAxisSpacing: 16.0" in layout
    assert "padding: const EdgeInsets.all(8.0)" in layout or "fromLTRB(8.0" in layout
    assert "Text('A'" in layout
    assert "Text('D'" in layout


def test_nested_grid_in_column_uses_shrink_wrap() -> None:
    grid_child = CleanDesignTreeNode(
        id="2",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        grid_row_gap=8,
        grid_column_gap=8,
        children=[
            CleanDesignTreeNode(id="3", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="4", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid_child],
    )

    layout = render_layout_file(parent, feature_name="nested_grid", uses_svg=False)[
        "lib/generated/nested_grid_layout.dart"
    ]

    assert "shrinkWrap: true" in layout
    assert "GridView.count(" in layout


def test_fill_height_grid_in_column_uses_expanded() -> None:
    grid_child = CleanDesignTreeNode(
        id="2",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        sizing=Sizing(height_mode=SizingMode.FILL),
        children=[CleanDesignTreeNode(id="3", name="A", type=NodeType.TEXT, text="A")],
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid_child],
    )

    layout = render_layout_file(parent, feature_name="grid_fill", uses_svg=False)[
        "lib/generated/grid_fill_layout.dart"
    ]

    assert "Expanded(child: RepaintBoundary(child: GridView.count(" in layout


def test_root_grid_responsive_disabled_skips_layout_builder() -> None:
    root = json.loads(Path("tests/fixtures/figma_grid_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    layout = render_layout_file(
        tree,
        feature_name="products",
        uses_svg=False,
        responsive_enabled=False,
    )["lib/generated/products_layout.dart"]

    assert "LayoutBuilder(" not in layout
    assert "crossAxisCount: 2" in layout
