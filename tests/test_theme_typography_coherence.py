"""Theme bundle coherence between app_theme.dart and app_typography.dart."""

from __future__ import annotations

from figma_flutter_agent.generator.renderer_theme import (
    ensure_theme_typography_coherence,
    expand_theme_bundle_writes,
    missing_app_typography_style_refs,
    render_theme_files,
)
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.schemas import DesignTokens, TypographyStyle
def test_missing_app_typography_style_refs_detects_drift() -> None:
    planned = {
        "lib/theme/app_theme.dart": "displayLarge: AppTypography.tToken,",
        "lib/theme/app_typography.dart": "static const TextStyle logIn = TextStyle(fontSize: 14),",
    }
    assert missing_app_typography_style_refs(planned) == ("tToken",)


def test_ensure_theme_typography_coherence_rerenders_bundle() -> None:
    tokens = DesignTokens(
        colors={"primary": "0xFF000000"},
        typography={
            "tToken": TypographyStyle(font_size=24.0, font_weight="w700"),
            "heading1": TypographyStyle(font_size=17.0, font_weight="w800"),
        },
    )
    planned = {
        "lib/theme/app_theme.dart": "bodyLarge: AppTypography.tToken,",
        "lib/theme/app_typography.dart": "static const TextStyle stale = TextStyle(fontSize: 12),",
        "lib/theme/app_colors.dart": "class AppColors {}",
    }
    renderer = DartRenderer()
    changed = ensure_theme_typography_coherence(
        planned,
        tokens,
        renderer._env,
    )
    assert changed is True
    assert "static const TextStyle tToken" in planned["lib/theme/app_typography.dart"]
    assert missing_app_typography_style_refs(planned) == ()


def test_expand_theme_bundle_writes_includes_all_theme_files() -> None:
    planned = {
        "lib/theme/app_theme.dart": "theme-v2",
        "lib/theme/app_typography.dart": "typography-v2",
        "lib/theme/app_colors.dart": "colors-v2",
        "lib/features/foo/foo_screen.dart": "screen",
    }
    selected = {"lib/theme/app_theme.dart": "theme-v2"}
    expanded = expand_theme_bundle_writes(selected, planned)
    assert expanded["lib/theme/app_typography.dart"] == "typography-v2"
    assert expanded["lib/theme/app_colors.dart"] == "colors-v2"
    assert "lib/features/foo/foo_screen.dart" not in expanded


def test_render_theme_files_emits_primary_font_family_when_single_bundle() -> None:
    tokens = DesignTokens(
        colors={"primary": "0xFF6750A4"},
        typography={
            "heading1": TypographyStyle(font_size=17.0, font_weight="w800"),
        },
    )
    renderer = DartRenderer()
    files = render_theme_files(
        renderer._env,
        tokens,
        primary_font_family="Golos Text",
    )
    assert "fontFamily: 'Golos Text'" in files["lib/theme/app_theme.dart"]
    assert "fontFamily: 'Golos Text'" in files["lib/theme/app_typography.dart"]


def test_render_theme_files_keeps_theme_and_typography_aligned() -> None:
    tokens = DesignTokens(
        colors={"primary": "0xFF6750A4"},
        typography={
            "heading1": TypographyStyle(font_size=20.0, font_weight="w700"),
            "bodyLarge": TypographyStyle(font_size=14.0, font_weight="w400"),
        },
    )
    renderer = DartRenderer()
    files = render_theme_files(renderer._env, tokens)
    assert missing_app_typography_style_refs(files) == ()
