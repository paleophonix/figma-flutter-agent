"""Tests for Figma-fact style helpers."""

from figma_flutter_agent.generator.layout.style.colors import is_greenish_fill
from figma_flutter_agent.generator.layout.style.facts import (
    chip_row_palette_exprs,
    is_near_black_fill,
    label_color_on_surface_expr,
    selected_from_variant_or_luminance,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    NodeStyle,
    NodeType,
    Sizing,
)


def test_is_near_black_fill_detects_black() -> None:
    assert is_near_black_fill("0xFF000000") is True
    assert is_near_black_fill("0xFF006FFD") is False


def test_is_greenish_fill_detects_selection_green() -> None:
    assert is_greenish_fill("0xFF28A745") is True
    assert is_greenish_fill("0xFF006FFD") is False


def test_selected_from_variant_axis() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Tag",
        type=NodeType.ROW,
        variant=ComponentVariant(
            variant_properties={"Style": "Focus"},
        ),
    )
    assert selected_from_variant_or_luminance(node) is True


def test_selected_from_dark_row_surface() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Chip",
        type=NodeType.ROW,
        style=NodeStyle(background_color="0xFF006FFD"),
    )
    assert selected_from_variant_or_luminance(node) is True


def test_label_color_on_dark_surface_uses_on_primary() -> None:
    expr = label_color_on_surface_expr(
        NodeStyle(text_color="0xFF000000"),
        surface_color="0xFF006FFD",
    )
    assert expr == "Theme.of(context).colorScheme.onPrimary"


def test_label_color_preserves_explicit_text_fact() -> None:
    expr = label_color_on_surface_expr(
        NodeStyle(text_color="0xFF8B84FC"),
        surface_color="0xFFEAF2FF",
    )
    assert expr == "Color(0xFF8B84FC)"


def test_chip_row_palette_from_node_facts() -> None:
    row = CleanDesignTreeNode(
        id="chip",
        name="Tag",
        type=NodeType.ROW,
        sizing=Sizing(height=24.0),
        style=NodeStyle(background_color="0xFFEAF2FF", border_radius=12.0),
        children=[
            CleanDesignTreeNode(
                id="text",
                name="Text",
                type=NodeType.TEXT,
                text="helpful",
                style=NodeStyle(text_color="0xFF006FFD", font_size=10.0),
            ),
        ],
    )
    background, foreground = chip_row_palette_exprs(row)
    assert background == "Color(0xFFEAF2FF)"
    assert foreground == "Color(0xFF006FFD)"
