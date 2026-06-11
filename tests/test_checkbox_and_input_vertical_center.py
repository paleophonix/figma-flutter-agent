"""Compact checkbox detection and fixed-height input vertical centering."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.interaction import (
    looks_like_checkbox_control,
    row_hosts_checkbox_label_pair,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    SizingMode,
)


def _compact_thirteen_px_checkbox() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:cb",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=13.0, height=13.0),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFF767676",
            border_width=1.0,
            border_radius=2.5,
        ),
        accessibility_label="Input",
    )


def _consent_row_with_stack_label() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:row",
        name="Label",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=80.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        padding=Padding(top=16.0, bottom=16.0, left=16.0, right=16.0),
        spacing=12.0,
        children=[
            CleanDesignTreeNode(
                id="1:margin",
                name="Input:margin",
                type=NodeType.COLUMN,
                sizing=Sizing(width=13.0, height=24.0),
                padding=Padding(top=4.0),
                children=[_compact_thirteen_px_checkbox()],
            ),
            CleanDesignTreeNode(
                id="1:wrap",
                name="Container",
                type=NodeType.STACK,
                sizing=Sizing(width=254.0, height=48.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:copy",
                        name="Consent",
                        type=NodeType.TEXT,
                        text="Use this card by default for online payments and tips.",
                        sizing=Sizing(width=250.0, height=48.0),
                        style=NodeStyle(
                            text_color="0xFF3F3F46",
                            font_size=13.0,
                            line_height=1.85,
                        ),
                    )
                ],
            ),
        ],
    )


def _prefilled_flex_input() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:input",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width_mode=SizingMode.FILL, width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        padding=Padding(top=17.5, bottom=17.5, left=16.0, right=16.0),
        children=[
            CleanDesignTreeNode(
                id="1:value-wrap",
                name="Container",
                type=NodeType.COLUMN,
                sizing=Sizing(width=285.0, height=17.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:value",
                        name="Value",
                        type=NodeType.TEXT,
                        text="New card",
                        sizing=Sizing(width=285.0, height=17.0),
                        style=NodeStyle(
                            text_color="0xFF18181B",
                            font_size=14.0,
                            line_height=1.2,
                            glyph_top_offset=4.2,
                            glyph_height=12.6,
                        ),
                    )
                ],
            )
        ],
    )


def test_thirteen_px_bordered_square_is_checkbox_control() -> None:
    assert looks_like_checkbox_control(_compact_thirteen_px_checkbox()) is True


def test_consent_row_with_stack_label_host_pairs_checkbox_and_copy() -> None:
    row = _consent_row_with_stack_label()
    assert row_hosts_checkbox_label_pair(row) is True
    body = render_node_body(row, uses_svg=False)
    assert "Checkbox(" in body or "_GeneratedToggleCheckbox(" in body
    assert "TextField(" not in body
    assert "Use this card by default" in body


def test_prefilled_flex_input_omits_line_height_and_centers_with_line_box() -> None:
    body = render_node_body(_prefilled_flex_input(), uses_svg=False).replace("\n", "")
    assert "TextFormField(" in body
    assert "initialValue: 'New card'" in body
    assert "TextEditingController" not in body
    field_expr = body.split("decoration:", maxsplit=1)[0]
    assert "height: 1.2" not in field_expr
    assert "contentPadding: EdgeInsets.fromLTRB(16.0, 19.7, 16.0, 19.7)" in body
