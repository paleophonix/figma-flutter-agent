"""Emit regressions for rendering-engine reconciliation (FID-39..47)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.layout_style import (
    box_foreground_decoration_expr,
    strut_style_expr,
)
from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "spikes"


def test_text_emits_strut_style_from_spike_fixture() -> None:
    payload = json.loads((_FIXTURES / "text_strut_linebox.json").read_text(encoding="utf-8"))
    node = CleanDesignTreeNode.model_validate(payload)
    strut = strut_style_expr(node.style)
    assert strut is not None
    assert "StrutStyle" in strut
    assert "forceStrutHeight: true" in strut
    assert "leading: 5" in strut
    emit = render_node_body(node)
    assert "StrutStyle" in emit
    assert "leadingDistribution" not in emit


def test_frosted_column_emits_backdrop_filter_with_calibrated_sigma() -> None:
    payload = json.loads((_FIXTURES / "layer_blur_24.json").read_text(encoding="utf-8"))
    node = CleanDesignTreeNode.model_validate(payload)
    emit = render_node_body(node)
    assert "BackdropFilter" in emit
    assert "ImageFilter.blur(sigmaX: 12" in emit


def test_blurred_vector_emits_image_filtered_not_box_shadow_glow() -> None:
    node = CleanDesignTreeNode(
        id="1:10",
        name="BlurVector",
        type=NodeType.VECTOR,
        sizing=Sizing(
            width=48.0,
            height=48.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
        style=NodeStyle(layer_blur=24.0, background_color="0xFF6750A4"),
    )
    emit = render_node_body(node, uses_svg=False)
    assert "ImageFiltered" in emit
    assert "boxShadow: [BoxShadow" not in emit


def test_outside_stroke_uses_foreground_decoration() -> None:
    style = NodeStyle(
        stroke_align="OUTSIDE",
        border_color="0xFF000000",
        border_width=2.0,
        border_radius=8.0,
    )
    foreground = box_foreground_decoration_expr(style)
    assert foreground is not None
    assert "Border.all" in foreground


def test_drop_shadow_fixture_uses_calibrated_blur() -> None:
    payload = json.loads((_FIXTURES / "drop_shadow_blur_24.json").read_text(encoding="utf-8"))
    node = CleanDesignTreeNode.model_validate(payload)
    emit = render_node_body(node)
    assert "blurRadius: 24" not in emit
    assert "boxShadow" in emit
