"""Tests for deterministic layout style helpers."""

from figma_flutter_agent.generator.layout.style import (
    card_elevation_expr,
    dart_color_expr,
    fill_luminance,
    is_dark_fill_color,
)
from figma_flutter_agent.generator.variant_props import button_on_pressed_expr, variant_is_disabled
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeStyle, NodeType


def test_variant_is_disabled_reads_state_property() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Button",
        type=NodeType.BUTTON,
        variant=ComponentVariant(
            component_id="c1",
            state="Disabled",
            variant_properties={"State": "Disabled"},
        ),
    )

    assert variant_is_disabled(node) is True
    assert button_on_pressed_expr(node) == "null"


def test_dart_color_expr_maps_hex_background() -> None:
    style = NodeStyle(background_color="#664FA3")
    assert dart_color_expr(style) == "Color(0xFF664FA3)"


def test_dart_color_expr_wraps_hex_literal_fallback() -> None:
    style = NodeStyle()
    assert (
        dart_color_expr(style, css_key="border-color", fallback="0xFF52525C")
        == "Color(0xFF52525C)"
    )


def test_dart_color_expr_prefers_css_rgba_over_black_text_color() -> None:
    style = NodeStyle(
        text_color="0xFF000000",
        css_properties={"color": "rgba(246, 241, 251, 1.000)"},
    )
    assert dart_color_expr(style, css_key="color") == "Color(0xFFF6F1FB)"


def test_card_elevation_uses_theme_token_by_default() -> None:
    assert card_elevation_expr(NodeStyle()) == "AppElevation.md"


def test_fill_luminance_classifies_dark_and_light_fills() -> None:
    assert is_dark_fill_color("0xFF3F414E") is True
    assert is_dark_fill_color("0xFFFBFBFB") is False
    assert fill_luminance("rgba(63, 65, 78, 1)") is not None
    assert fill_luminance("0xFF3F414E") is not None
    assert fill_luminance("0xFF3F414E") < fill_luminance("0xFFFBFBFB")  # type: ignore[operator]
