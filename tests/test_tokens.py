import json
from collections import Counter
from pathlib import Path

from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.parser.tokens import (
    build_color_tokens,
    build_design_tokens,
    is_neutral_rgba,
    rgba_to_argb_hex,
    select_primary_color_hex,
)
from figma_flutter_agent.schemas import DesignTokens, TypographyToken


def test_build_design_tokens_fallback() -> None:
    fixture = Path("tests/fixtures/figma_node_sample.json")
    root = json.loads(fixture.read_text(encoding="utf-8"))
    tokens = build_design_tokens(root, variables_payload=None)

    assert tokens.colors
    assert tokens.colors[0].name == "primary"
    assert tokens.typography
    assert tokens.spacing
    assert tokens.radii
    assert tokens.elevations


def test_extract_spacing_from_nested_frames() -> None:
    root = {
        "type": "FRAME",
        "itemSpacing": 8,
        "children": [
            {
                "type": "FRAME",
                "itemSpacing": 24,
                "children": [{"type": "FRAME", "itemSpacing": 16}],
            }
        ],
    }
    tokens = build_design_tokens(root, variables_payload=None)

    assert [token.value for token in tokens.spacing] == [8.0, 16.0, 24.0]


def test_select_primary_color_skips_neutral_fills() -> None:
    white = rgba_to_argb_hex({"r": 1, "g": 1, "b": 1, "a": 1})
    purple = rgba_to_argb_hex({"r": 0.4, "g": 0.31, "b": 0.64, "a": 1})
    counts = Counter({white: 5, purple: 1})
    neutral = {white}

    assert select_primary_color_hex(counts, neutral) == purple


def test_build_color_tokens_warns_when_only_neutral_colors() -> None:
    white = rgba_to_argb_hex({"r": 1, "g": 1, "b": 1, "a": 1})
    black = rgba_to_argb_hex({"r": 0, "g": 0, "b": 0, "a": 1})
    tokens = build_color_tokens(Counter({white: 3, black: 2}), {white, black})

    assert len(tokens) == 1
    assert tokens[0].name == "primary"
    assert tokens[0].value == "0xFF6750A4"


def test_is_neutral_rgba() -> None:
    assert is_neutral_rgba({"r": 1, "g": 1, "b": 1, "a": 1}) is True
    assert is_neutral_rgba({"r": 0, "g": 0, "b": 0, "a": 1}) is True
    assert is_neutral_rgba({"r": 0.4, "g": 0.31, "b": 0.64, "a": 1}) is False


def test_render_theme_files_includes_typography() -> None:
    renderer = DartRenderer()
    tokens = DesignTokens(
        typography=[
            TypographyToken(style_name="titleLarge", font_size=24, font_weight="w600"),
        ]
    )

    files = renderer.render_theme_files(tokens)

    assert "lib/theme/app_typography.dart" in files
    assert "static const TextStyle titleLarge" in files["lib/theme/app_typography.dart"]
    assert "fontWeight: FontWeight.w600" in files["lib/theme/app_typography.dart"]
    assert "lib/theme/app_radius.dart" in files
    assert "lib/theme/app_elevation.dart" in files


def test_render_theme_files_generates_dark_theme_when_enabled() -> None:
    renderer = DartRenderer()
    tokens = DesignTokens()

    files = renderer.render_theme_files(tokens, generate_dark_mode=True)
    theme = files["lib/theme/app_theme.dart"]

    assert "static ThemeData dark" in theme
    assert "Brightness.dark" in theme
    assert "static ThemeData light" in theme


def test_render_theme_files_generates_cupertino_theme() -> None:
    renderer = DartRenderer()
    tokens = DesignTokens()

    files = renderer.render_theme_files(tokens, theme_variant="cupertino")

    assert "lib/theme/app_cupertino_theme.dart" in files
    assert "CupertinoThemeData" in files["lib/theme/app_cupertino_theme.dart"]
    assert "lib/theme/app_theme.dart" in files
