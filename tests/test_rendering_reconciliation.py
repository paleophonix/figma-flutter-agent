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
    emit = render_node_body(node, uses_svg=False)
    assert "StrutStyle" in emit
    assert "leadingDistribution" not in emit


def test_frosted_column_emits_backdrop_filter_with_calibrated_sigma() -> None:
    payload = json.loads((_FIXTURES / "layer_blur_24.json").read_text(encoding="utf-8"))
    node = CleanDesignTreeNode.model_validate(payload)
    emit = render_node_body(node, uses_svg=False)
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


def test_root_stack_uses_soft_clip_when_child_has_outward_paint() -> None:
    from figma_flutter_agent.schemas import ShadowEffect

    child = CleanDesignTreeNode(
        id="1:2",
        name="ShadowCard",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=100.0, height=50.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=10.0,
            top=20.0,
            width=100.0,
            height=50.0,
        ),
        style=NodeStyle(
            effects=[ShadowEffect(kind="drop", blur=24.0, color="0xFF000000")],
        ),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[child],
    )
    emit = render_node_body(root, uses_svg=False, is_layout_root=True)
    assert "clipBehavior: Clip.none" in emit


def test_min_max_sizing_emits_constrained_box() -> None:
    node = CleanDesignTreeNode(
        id="1:20",
        name="Card",
        type=NodeType.CONTAINER,
        sizing=Sizing(
            width=200.0,
            height=100.0,
            min_width=120.0,
            max_width=320.0,
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
        ),
        style=NodeStyle(background_color="0xFFFFFFFF"),
    )
    emit = render_node_body(node, uses_svg=False)
    assert "ConstrainedBox" in emit
    assert "minWidth:" in emit
    assert "maxWidth:" in emit


def test_background_blur_prefers_backdrop_over_layer_on_host() -> None:
    node = CleanDesignTreeNode(
        id="1:30",
        name="Glass",
        type=NodeType.COLUMN,
        sizing=Sizing(width=200.0, height=64.0),
        style=NodeStyle(
            background_color="0xCCFCFBF8",
            layer_blur=12.0,
            background_blur=24.0,
        ),
    )
    emit = render_node_body(node, uses_svg=False)
    assert "BackdropFilter" in emit
    assert "ImageFilter.blur(sigmaX: 12" in emit


def test_drop_shadow_fixture_uses_calibrated_blur() -> None:
    payload = json.loads((_FIXTURES / "drop_shadow_blur_24.json").read_text(encoding="utf-8"))
    node = CleanDesignTreeNode.model_validate(payload)
    emit = render_node_body(node, uses_svg=False)
    assert "blurRadius: 24" not in emit
    assert "boxShadow" in emit
