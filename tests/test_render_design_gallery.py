"""Tests for design gallery rendering."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, select_autoescape

from figma_flutter_agent.generator.renderer_theme import render_design_gallery
from figma_flutter_agent.schemas import DesignTokens, TypographyStyle


def test_render_design_gallery_includes_colors() -> None:
    env = Environment(
        loader=FileSystemLoader("src/figma_flutter_agent/generator/templates"),
        autoescape=select_autoescape(enabled_extensions=()),
    )
    tokens = DesignTokens(
        colors={"primary": "0xFF112233"},
        typography={"body": TypographyStyle(fontSize=14, fontWeight="w400")},
        spacing={"md": 16.0},
    )
    files = render_design_gallery(env, tokens, package_name="demo_app")
    source = files["lib/dev/design_gallery_screen.dart"]
    assert "DesignGalleryScreen" in source
    assert "AppColors.primary" in source
