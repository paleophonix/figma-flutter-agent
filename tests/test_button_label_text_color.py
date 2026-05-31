"""Button label contrast on filled stacks."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_style import (
    filled_button_label_text_color,
    text_style_expr,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_filled_button_label_uses_white_on_purple_fill() -> None:
    button_row = CleanDesignTreeNode(
        id="1:3970",
        name="Button row",
        type=NodeType.STACK,
        sizing=Sizing(width=374.0, height=97.0),
        children=[
            CleanDesignTreeNode(
                id="1:3971",
                name="Fill",
                type=NodeType.CONTAINER,
                style=NodeStyle(background_color="#8E97FD"),
            ),
            CleanDesignTreeNode(
                id="1:3972",
                name="SIGN UP",
                type=NodeType.TEXT,
                text="SIGN UP",
                stack_placement=StackPlacement(left=156.0, top=0.0, width=62.0, height=14.0),
            ),
            CleanDesignTreeNode(
                id="1:3973",
                name="Footer",
                type=NodeType.TEXT,
                text="ALREADY HAVE AN ACCOUNT?",
                stack_placement=StackPlacement(left=46.0, top=39.0, width=282.0, height=14.0),
            ),
        ],
    )
    label = button_row.children[1]
    footer = button_row.children[2]
    assert filled_button_label_text_color(label, button_row) == "Color(0xFFFFFFFF)"
    assert filled_button_label_text_color(footer, button_row) is None
    expr = text_style_expr(label, parent_node=button_row)
    assert "Color(0xFFFFFFFF)" in expr
