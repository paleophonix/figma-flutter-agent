"""Delta-top vertical correction: single channel and StrutStyle.leading units (T1)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.text_metrics import (
    strut_leading_ratio,
    text_uses_delta_top_layout_wrap,
)
from figma_flutter_agent.generator.layout.style import strut_style_expr
from figma_flutter_agent.generator.layout.widgets import _apply_layout_slot_wraps
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    LayoutSlotIr,
    NodeStyle,
    NodeType,
    TextMetricsFrame,
    WrapKind,
)


def test_strut_leading_emits_unitless_font_multiplier() -> None:
    style = NodeStyle(
        font_size=24.0,
        line_height=1.5,
        glyph_top_offset=10.2,
        text_color="0xFF2E7D32",
    )
    ratio = strut_leading_ratio(24.0, 10.2, 1.5)
    assert ratio is not None
    assert abs(ratio - (10.2 - 9.36) / 24.0) < 0.001
    strut = strut_style_expr(style)
    assert strut is not None
    assert "leading: 10.2" not in strut
    assert "leading: 0.03" in strut


def test_delta_top_padding_suppresses_strut_leading() -> None:
    node = CleanDesignTreeNode(
        id="1:1",
        name="Label",
        type=NodeType.TEXT,
        text="Title",
        style=NodeStyle(
            font_size=16.0,
            line_height=1.4,
            glyph_top_offset=6.0,
        ),
        text_metrics_frame=TextMetricsFrame(font_size=16.0, delta_top=2.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.DELTA_TOP_PADDING,)),
    )
    assert text_uses_delta_top_layout_wrap(node)
    strut = strut_style_expr(node.style, node=node)
    assert strut is not None
    assert "leading:" not in strut


def test_emit_applies_single_vertical_correction_channel() -> None:
    node = CleanDesignTreeNode(
        id="1:1",
        name="Label",
        type=NodeType.TEXT,
        text="Body copy line",
        style=NodeStyle(
            font_size=16.0,
            line_height=1.4,
            glyph_top_offset=6.0,
        ),
        text_metrics_frame=TextMetricsFrame(font_size=16.0, delta_top=4.0),
        layout_slot=LayoutSlotIr(wraps=(WrapKind.DELTA_TOP_PADDING,)),
    )
    wrapped = _apply_layout_slot_wraps(node, "Text('Body copy line')", parent_type=NodeType.ROW)
    assert "EdgeInsets.only(top:" in wrapped
    strut = strut_style_expr(node.style, node=node)
    assert strut is None or "leading:" not in strut
