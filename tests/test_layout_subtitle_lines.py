"""Centered multi-line subtitle codegen."""

from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_centered_subtitle_with_newline_renders_column() -> None:
    node = CleanDesignTreeNode(
        id="1:3976",
        name="subtitle",
        type=NodeType.TEXT,
        text="Thousand of people are usign silent moon\nfor smalls meditation",
        style=NodeStyle(
            font_size=16.0,
            font_weight="w300",
            text_align="CENTER",
            text_color="0xFFA1A4B2",
        ),
        sizing=Sizing(width=298.0, height=40.0),
        stack_placement=StackPlacement(left=0.0, top=57.0, width=298.0, height=40.0),
    )
    parent = CleanDesignTreeNode(
        id="1:3974",
        name="text block",
        type=NodeType.STACK,
        children=[node],
    )

    body = render_node_body(node, uses_svg=False, parent_type=NodeType.STACK, parent_node=parent)

    assert "Column(" in body
    assert "CrossAxisAlignment.stretch" in body
    assert "silent moon" in body
    assert "for smalls meditation" in body
    assert body.count("Text(") >= 2
