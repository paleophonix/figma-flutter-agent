"""Logo wordmark layout codegen."""

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def test_logo_wordmark_stack_renders_bounded_absolute_stack() -> None:
    logo = CleanDesignTreeNode(
        id="1:3666",
        name="logo",
        type=NodeType.STACK,
        sizing=Sizing(width=30.0, height=30.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED),
        stack_placement=StackPlacement(left=73.0, top=0.0, width=30.0, height=30.0),
        children=[],
    )
    moon = CleanDesignTreeNode(
        id="1:3675",
        name="Moon",
        type=NodeType.TEXT,
        text="Moon",
        style=NodeStyle(font_size=16.0, font_weight="w700"),
        sizing=Sizing(width=55.0, height=21.0),
        stack_placement=StackPlacement(left=113.0, top=5.0, width=55.0, height=21.0),
    )
    silent = CleanDesignTreeNode(
        id="1:3676",
        name="Silent",
        type=NodeType.TEXT,
        text="Silent",
        style=NodeStyle(font_size=16.0, font_weight="w700"),
        sizing=Sizing(width=63.0, height=21.0),
        stack_placement=StackPlacement(left=0.0, top=5.0, width=63.0, height=21.0),
    )
    root = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        sizing=Sizing(width=168.0, height=30.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED),
        children=[logo, moon, silent],
    )

    body = render_node_body(root, uses_svg=False)

    assert "SizedBox(width: 168.0, height: 30.0" in body
    assert "Row(" not in body
    assert "Stack(clipBehavior: Clip.none" in body
    assert "Text('Silent'" in body
    assert "Text('Moon'" in body
