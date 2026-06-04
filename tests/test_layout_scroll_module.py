"""Unit tests for layout_scroll helpers."""

from figma_flutter_agent.generator.layout_scroll import (
    padding_edge_insets,
    render_scroll_list,
    scroll_axis_for_list,
    wrap_flex_auto_layout_padding,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Padding, Sizing, SizingMode


def test_padding_edge_insets_none_when_zero() -> None:
    node = CleanDesignTreeNode(id="1", name="Box", type=NodeType.COLUMN)

    assert padding_edge_insets(node) is None


def test_wrap_flex_auto_layout_padding() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Box",
        type=NodeType.COLUMN,
        padding=Padding(left=12.0, top=8.0),
    )
    wrapped = wrap_flex_auto_layout_padding(node, "Column()")
    assert "Padding(padding: const EdgeInsets.fromLTRB(12.0, 8.0, 0.0, 0.0)" in wrapped


def test_scroll_axis_for_list_horizontal() -> None:
    node = CleanDesignTreeNode(id="1", name="Row", type=NodeType.ROW, scroll_axis="horizontal")

    assert scroll_axis_for_list(node) == "horizontal"


def test_render_scroll_list_uses_listview_builder_for_many_children() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="List",
        type=NodeType.COLUMN,
        scroll_axis="vertical",
        sizing=Sizing(height_mode=SizingMode.FILL),
        children=[
            CleanDesignTreeNode(id=f"c{i}", name=f"Item {i}", type=NodeType.TEXT, text=str(i))
            for i in range(8)
        ],
    )
    children = [f"Text('{i}')" for i in range(8)]

    widget = render_scroll_list(node, children, axis="vertical", parent_type=NodeType.COLUMN)

    assert "ListView.builder(" in widget
    assert "itemCount: 8" in widget
