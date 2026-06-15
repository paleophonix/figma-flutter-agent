"""Textarea field recognition and emit tests."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.interaction import layout_fact_textarea_field
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_text_area_name_matches_textarea_predicate() -> None:
    field = CleanDesignTreeNode(
        id="281:7418",
        name="Text Area",
        type=NodeType.COLUMN,
        sizing=Sizing(width=320.0, height=94.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=8.0),
        children=[
            CleanDesignTreeNode(
                id="281:7419",
                name="Hint",
                type=NodeType.TEXT,
                text="Tell us everything.",
                style=NodeStyle(text_color="0xFF9E9E9E", font_size=14.0),
            ),
        ],
    )

    assert layout_fact_textarea_field(field) is True


def test_textarea_emits_text_align_vertical_top() -> None:
    field = CleanDesignTreeNode(
        id="281:7418",
        name="Text Area",
        type=NodeType.COLUMN,
        sizing=Sizing(width=320.0, height=94.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=8.0),
        children=[
            CleanDesignTreeNode(
                id="281:7419",
                name="Hint",
                type=NodeType.TEXT,
                text="Tell us everything.",
                accessibility_label="Tell us everything.",
                style=NodeStyle(text_color="0xFF9E9E9E", font_size=14.0),
            ),
        ],
    )
    body = render_node_body(field, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")

    assert "TextField(" in compact
    assert "textAlignVertical: TextAlignVertical.top" in compact
    assert "hintText: 'Tell us everything.'" in compact
    assert "Text('Tell us everything.')" not in compact


def test_textarea_emits_border_from_child_field_surface() -> None:
    field = CleanDesignTreeNode(
        id="281:7418",
        name="Text Area",
        type=NodeType.COLUMN,
        sizing=Sizing(width=320.0, height=94.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=8.0),
        children=[
            CleanDesignTreeNode(
                id="281:7419",
                name="Hint",
                type=NodeType.TEXT,
                text="Tell us everything.",
                accessibility_label="Tell us everything.",
                style=NodeStyle(text_color="0xFF9E9E9E", font_size=14.0),
            ),
            CleanDesignTreeNode(
                id="281:7420",
                name="Field",
                type=NodeType.ROW,
                sizing=Sizing(width=320.0, height=94.0),
                style=NodeStyle(
                    background_color="0xFFFFFFFF",
                    border_radius=8.0,
                    border_width=1.0,
                    border_color="0xFFC5C6CC",
                ),
                children=[],
            ),
        ],
    )
    body = render_node_body(field, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")

    assert "textAlignVertical: TextAlignVertical.top" in compact
    assert "border: Border.all" in compact
    assert "hintStyle:" in compact or "TextField(" in compact


def test_textarea_hint_style_uses_placeholder_text_color() -> None:
    field = CleanDesignTreeNode(
        id="281:7418",
        name="Text Area",
        type=NodeType.COLUMN,
        sizing=Sizing(width=320.0, height=94.0),
        style=NodeStyle(background_color="0xFFFFFFFF", border_radius=8.0),
        children=[
            CleanDesignTreeNode(
                id="281:7419",
                name="Hint",
                type=NodeType.TEXT,
                text="Tell us everything.",
                accessibility_label="Tell us everything.",
                style=NodeStyle(text_color="0xFF8F9098", font_size=14.0),
            ),
        ],
    )
    body = render_node_body(field, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")

    assert "hintStyle:" in compact
    assert "style: Theme.of(context).textTheme.bodyMedium" in compact
