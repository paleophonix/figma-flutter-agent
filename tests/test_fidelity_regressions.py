"""Compile-time fidelity regressions (refactor-checklist Tier 1–3)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.layout_style import border_radius_expr, box_decoration_expr
from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.parser.numeric_rounding import round_stack_placement
from figma_flutter_agent.parser.richtext import collapse_adjacent_text_spans
from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    CornerRadii,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
    TextSpanPart,
)


def test_per_corner_border_radius_emit() -> None:
    style = NodeStyle(
        border_radius_corners=CornerRadii(
            top_left=8.0,
            top_right=12.0,
            bottom_right=4.0,
            bottom_left=16.0,
        )
    )
    expr = border_radius_expr(style)
    assert "BorderRadius.only" in expr
    assert "topLeft" in expr and "bottomRight" in expr


def test_group_opacity_wraps_subtree() -> None:
    node = CleanDesignTreeNode(
        id="frame",
        name="Frame",
        type=NodeType.CONTAINER,
        style=NodeStyle(opacity=0.5),
        sizing=Sizing(width=100.0, height=100.0),
        children=[
            CleanDesignTreeNode(
                id="label",
                name="Label",
                type=NodeType.TEXT,
                text="Hi",
            ),
        ],
    )
    body = render_node_body(node, uses_svg=False, is_layout_root=True)
    assert "Opacity(opacity:" in body


def test_round_stack_placement_preserves_horizontal_invariant() -> None:
    placement = StackPlacement(left=10.3, right=20.2, width=300.0, height=40.0)
    rounded = round_stack_placement(placement, parent_width=330.5)
    assert rounded.left is not None
    assert rounded.right is not None
    assert rounded.width is not None
    total = rounded.left + rounded.width + rounded.right
    assert abs(total - 330.5) < 0.15


def test_parse_rectangle_corner_radii_from_figma_node() -> None:
    style = NodeStyle()
    enrich_node_style(
        {"rectangleCornerRadii": [4, 8, 12, 16], "fills": [], "strokes": []},
        style,
    )
    assert style.border_radius_corners is not None
    assert style.border_radius_corners.top_left == 4.0


def test_collapse_adjacent_text_spans() -> None:
    spans = [
        TextSpanPart(text="Hello ", text_color="0xFF000000"),
        TextSpanPart(text="world", text_color="0xFF000000"),
    ]
    merged = collapse_adjacent_text_spans(spans)
    assert len(merged) == 1
    assert merged[0].text == "Hello world"


def test_inner_shadow_included_in_box_decoration() -> None:
    from figma_flutter_agent.schemas import ShadowEffect

    style = NodeStyle(
        background_color="0xFFFFFFFF",
        effects=[
            ShadowEffect(
                kind="inner",
                offset_x=0,
                offset_y=2,
                blur=4,
                spread=0,
                color="0x33000000",
            ),
        ],
    )
    decoration = box_decoration_expr(style, width=100.0, height=50.0)
    assert decoration is not None
    assert "boxShadow" in decoration
