"""Tests for Figma ``textCase`` capture and deterministic text emit."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.parser.text_case import apply_figma_text_case
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_apply_figma_text_case_upper() -> None:
    assert apply_figma_text_case("Easy to use", "UPPER") == "EASY TO USE"


def test_apply_figma_text_case_lower() -> None:
    assert apply_figma_text_case("EASY TO USE", "LOWER") == "easy to use"


def test_apply_figma_text_case_title() -> None:
    assert apply_figma_text_case("easy to use", "TITLE") == "Easy To Use"


def test_apply_figma_text_case_original_is_noop() -> None:
    assert apply_figma_text_case("Easy to use", "ORIGINAL") == "Easy to use"
    assert apply_figma_text_case("Easy to use", None) == "Easy to use"


def test_enrich_text_style_captures_upper_text_case() -> None:
    style = enrich_node_style(
        {
            "type": "TEXT",
            "characters": "Easy to use",
            "style": {"fontSize": 12.0, "textCase": "UPPER"},
            "fills": [
                {
                    "type": "SOLID",
                    "visible": True,
                    "color": {"r": 0, "g": 0.4, "b": 1, "a": 1},
                }
            ],
        },
        NodeStyle(),
    )
    assert style.text_case == "UPPER"


def test_chip_text_emits_upper_from_figma_text_case() -> None:
    pill = CleanDesignTreeNode(
        id="1:pill",
        name="Chip",
        type=NodeType.ROW,
        padding={"left": 8.0, "right": 8.0, "top": 6.0, "bottom": 6.0},
        sizing=Sizing(width=95.0, height=24.0),
        style=NodeStyle(background_color="0xFFEAF2FF", border_radius=12.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Easy to use",
                accessibility_label="Easy to use",
                style=NodeStyle(
                    text_color="0xFF006FFD",
                    font_size=12.0,
                    font_weight="w600",
                    text_case="UPPER",
                ),
            )
        ],
    )
    body = render_node_body(pill, uses_svg=False, parent_type=NodeType.COLUMN)
    compact = body.replace("\n", "")
    assert "Text('EASY TO USE'" in compact
    assert "Text('Easy to use'" not in compact
    assert "Semantics(label: 'EASY TO USE'" in compact
