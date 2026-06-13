"""SVG dimension and fit regressions."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.svg import (
    _effective_svg_dimensions,
    _render_svg_picture,
    _svg_fit_mode,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_hairline_svg_keeps_one_pixel_height() -> None:
    line = CleanDesignTreeNode(
        id="line",
        name="Line",
        type=NodeType.VECTOR,
        sizing=Sizing(width=140.5, height=0.0),
        style=NodeStyle(has_stroke=True, border_width=1.0),
        vector_asset_key="assets/icons/line.svg",
    )
    width, height = _effective_svg_dimensions(line, 140.5, 0.0)
    assert width == 140.5
    assert height == 1.0


def test_hairline_svg_emits_fit_width() -> None:
    line = CleanDesignTreeNode(
        id="line",
        name="Line",
        type=NodeType.VECTOR,
        sizing=Sizing(width=140.5, height=1.0),
        style=NodeStyle(has_stroke=True, border_width=1.0),
        vector_asset_key="assets/icons/line.svg",
    )
    body = _render_svg_picture(line, "assets/icons/line.svg")
    assert "height: 1.0" in body
    assert "height: 3.0" not in body
    assert "fit: BoxFit.fitWidth" in body


def test_compact_icon_svg_uses_contain_not_fill() -> None:
    icon = CleanDesignTreeNode(
        id="icon",
        name="Icon",
        type=NodeType.VECTOR,
        sizing=Sizing(width=18.0, height=18.0),
        vector_asset_key="assets/icons/google.svg",
    )
    assert _svg_fit_mode(icon, 18.0, 18.0) == "BoxFit.contain"
    body = _render_svg_picture(icon, "assets/icons/google.svg")
    assert "fit: BoxFit.contain" in body
    assert "fit: BoxFit.fill" not in body
