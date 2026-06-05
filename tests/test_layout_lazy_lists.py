"""Tests for lazy ListView.builder / GridView.builder when child count is high."""

from figma_flutter_agent.generator.layout.renderer import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode


def _text_children(count: int) -> list[CleanDesignTreeNode]:
    return [
        CleanDesignTreeNode(
            id=str(index), name=f"Item {index}", type=NodeType.TEXT, text=f"T{index}"
        )
        for index in range(count)
    ]


def test_large_vertical_scroll_uses_list_view_builder() -> None:
    scroll = CleanDesignTreeNode(
        id="1",
        name="Feed",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=_text_children(8),
    )

    layout = render_layout_file(scroll, feature_name="feed_lazy", uses_svg=False)[
        "lib/generated/feed_lazy_layout.dart"
    ]

    assert "ListView.builder(" in layout
    assert "itemCount: 8" in layout
    assert "if (index == 0)" in layout
    assert "if (index == 7)" in layout
    assert "ListView(children:" not in layout


def test_small_vertical_scroll_keeps_eager_list_view() -> None:
    scroll = CleanDesignTreeNode(
        id="1",
        name="Feed",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        children=_text_children(7),
    )

    layout = render_layout_file(scroll, feature_name="feed_eager", uses_svg=False)[
        "lib/generated/feed_eager_layout.dart"
    ]

    assert "ListView(" in layout
    assert "ListView.builder(" not in layout
    assert "Text('T0'" in layout


def test_large_grid_uses_grid_view_builder() -> None:
    grid = CleanDesignTreeNode(
        id="1",
        name="Products",
        type=NodeType.GRID,
        grid_column_count=2,
        grid_row_gap=8,
        grid_column_gap=8,
        children=_text_children(8),
    )

    layout = render_layout_file(grid, feature_name="grid_lazy", uses_svg=False)[
        "lib/generated/grid_lazy_layout.dart"
    ]

    assert "GridView.builder(" in layout
    assert "itemCount: 8" in layout
    assert "GridView.count(" not in layout


def test_nested_large_grid_builder_uses_shrink_wrap() -> None:
    grid = CleanDesignTreeNode(
        id="2",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        children=_text_children(8),
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid],
    )

    layout = render_layout_file(parent, feature_name="nested_lazy_grid", uses_svg=False)[
        "lib/generated/nested_lazy_grid_layout.dart"
    ]

    assert "GridView.builder(shrinkWrap: true" in layout
    assert "ClampingScrollPhysics" in layout


def test_fill_height_large_grid_uses_expanded_builder() -> None:
    grid = CleanDesignTreeNode(
        id="2",
        name="Grid",
        type=NodeType.GRID,
        grid_column_count=2,
        sizing=Sizing(height_mode=SizingMode.FILL),
        children=_text_children(8),
    )
    parent = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[grid],
    )

    layout = render_layout_file(parent, feature_name="grid_fill_lazy", uses_svg=False)[
        "lib/generated/grid_fill_lazy_layout.dart"
    ]

    assert "Expanded(child: RepaintBoundary(child: GridView.builder(" in layout
