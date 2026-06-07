"""Input field vertical padding derived from Figma glyph metrics."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.render import _input_content_padding
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_input_content_padding_centers_when_figma_top_is_too_high() -> None:
    surface = CleanDesignTreeNode(
        id="surface",
        name="Field",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=295.0, height=46.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
    )
    hint = CleanDesignTreeNode(
        id="value",
        name="Value",
        type=NodeType.TEXT,
        text="Lois Becket",
        sizing=Sizing(width=207.0, height=21.0),
        style=NodeStyle(glyph_top_offset=4.4, glyph_height=10.7, font_size=14.0),
        stack_placement=StackPlacement(left=14.0, top=4.0, width=207.0, height=21.0),
    )
    padding = _input_content_padding(surface, hint, 46.0)
    assert padding is not None
    assert "contentPadding: EdgeInsets.fromLTRB" in padding
    assert "4.0" not in padding.split("fromLTRB(")[1].split(",")[1]
