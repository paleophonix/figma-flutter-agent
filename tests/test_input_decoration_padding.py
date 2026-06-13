"""InputDecoration padding regressions for single-line fields."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.input.decoration import (
    _optical_single_line_input_content_padding,
    _stack_input_decoration,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
)


def test_optical_padding_centers_single_line_with_horizontal_inset() -> None:
    host = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=46.0),
        style=NodeStyle(),
    )
    padding = _optical_single_line_input_content_padding(host, None, 46.0)
    assert padding is not None
    assert "fromLTRB(16.0" in padding


def test_stack_input_decoration_ignores_outer_frame_padding_for_vertical_center() -> None:
    host = CleanDesignTreeNode(
        id="input",
        name="Input Area",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=46.0),
        padding=Padding(top=27.0, bottom=27.0, left=14.0, right=14.0),
        style=NodeStyle(),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=46.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    decoration = _stack_input_decoration(
        host.children[0],
        None,
        "",
        host_node=host,
        field_height=46.0,
        surface_on_container=True,
        vertical_center=True,
    )
    assert "fromLTRB(14.0, 27.0" not in decoration
    assert "fromLTRB(16.0" in decoration


def test_stack_input_decoration_centers_single_line_text() -> None:
    host = CleanDesignTreeNode(
        id="input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=327.0, height=46.0),
        style=NodeStyle(),
        children=[
            CleanDesignTreeNode(
                id="surface",
                name="Surface",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=46.0),
                style=NodeStyle(background_color="0xFFFFFFFF"),
            )
        ],
    )
    decoration = _stack_input_decoration(
        host.children[0],
        None,
        "",
        host_node=host,
        field_height=69.0,
        surface_on_container=True,
        vertical_center=True,
    )
    assert "fromLTRB(0.0, 27.0" not in decoration
    assert "fromLTRB(16.0" in decoration
