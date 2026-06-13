"""Extended layout style mapping tests."""

from figma_flutter_agent.generator.layout.style import (
    box_decoration_expr,
    gradient_fill_expr,
    text_style_expr,
)
from figma_flutter_agent.generator.render_units import hairline_border_width
from figma_flutter_agent.generator.variant.state import variant_size_label
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    GradientFill,
    GradientStop,
    NodeStyle,
    NodeType,
    ShadowEffect,
)


def test_inner_shadow_emits_inset_overlay_expr() -> None:
    from figma_flutter_agent.generator.layout.style.decoration import (
        inner_shadow_overlay_exprs,
        wrap_with_inner_shadow_overlays,
    )

    style = NodeStyle(
        background_color="0xFFFFFFFF",
        border_radius=10.0,
        effects=[
            ShadowEffect(
                kind="inner",
                offset_x=0,
                offset_y=-3,
                blur=6,
                spread=0,
                color="0x99F4F5FA",
            ),
        ],
    )
    overlays = inner_shadow_overlay_exprs(style, frame_width=327.0, frame_height=48.0)
    assert len(overlays) == 1
    assert "Positioned(" in overlays[0]
    assert "LinearGradient" in overlays[0]
    assert "0x99F4F5FA" in overlays[0]
    assert "IgnorePointer" in overlays[0]
    wrapped = wrap_with_inner_shadow_overlays(
        "const SizedBox.shrink()",
        overlays,
        border_radius_expr="BorderRadius.circular(10.0)",
    )
    assert "ClipRRect" in wrapped
    assert "Stack(" in wrapped


def test_box_decoration_expr_includes_drop_shadow() -> None:
    style = NodeStyle(
        background_color="#FFFFFFFF",
        effects=[
            ShadowEffect(
                kind="drop",
                offset_x=0,
                offset_y=4,
                blur=8,
                spread=0,
                color="0x40000000",
            )
        ],
    )

    decoration = box_decoration_expr(style)

    assert decoration is not None
    assert "BoxDecoration" in decoration
    assert "boxShadow" in decoration
    assert "BoxShadow" in decoration


def test_gradient_fill_expr_linear() -> None:
    gradient = GradientFill(
        type="linear",
        angle=90.0,
        stops=[
            GradientStop(position=0.0, color="#FF0000"),
            GradientStop(position=1.0, color="#0000FF"),
        ],
    )

    expr = gradient_fill_expr(gradient)

    assert expr is not None
    assert "LinearGradient" in expr
    assert "Alignment(-0.0000, -1.0000)" in expr or "Alignment(0.0000, -1.0000)" in expr
    assert "Alignment(0.0000, 1.0000)" in expr
    assert "0xFFFF0000" in expr
    assert "0xFF0000FF" in expr


def test_box_decoration_expr_prefers_gradient_over_solid_color() -> None:
    style = NodeStyle(
        background_color="#FFFFFFFF",
        gradient=GradientFill(
            type="linear",
            angle=0.0,
            stops=[
                GradientStop(position=0.0, color="#111111"),
                GradientStop(position=1.0, color="#222222"),
            ],
        ),
    )

    decoration = box_decoration_expr(style)

    assert decoration is not None
    assert "gradient: LinearGradient" in decoration
    assert "color:" not in decoration


def test_box_decoration_expr_includes_stroke_only_border() -> None:
    style = NodeStyle(border_color="0xFFEBEAEC", border_width=1.0, border_radius=38.0)

    decoration = box_decoration_expr(style)

    assert decoration is not None
    assert (
        f"Border.all(color: Color(0xFFEBEAEC), width: {hairline_border_width()})"
        in decoration
    )
    assert "borderRadius: BorderRadius.circular(38.0)" in decoration


def test_text_style_expr_includes_figma_line_height() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Title",
        type=NodeType.TEXT,
        style=NodeStyle(
            text_color="0xFF3F414E",
            font_size=28.0,
            font_weight="w700",
            line_height=1.35,
        ),
    )

    expr = text_style_expr(node)

    assert "height: 1.35" in expr
    assert "leadingDistribution: TextLeadingDistribution.proportional" in expr


def test_text_style_expr_omits_proportional_on_tight_line_height() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Button label",
        type=NodeType.TEXT,
        style=NodeStyle(
            text_color="0xFFF6F1FB",
            font_size=14.0,
            font_weight="w700",
            line_height=1.08,
        ),
    )

    expr = text_style_expr(node)

    assert "height: 1.08" in expr
    assert "leadingDistribution" not in expr
    assert "fontSize: 14.0" in expr


def test_text_style_expr_uses_variant_size() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Label",
        type=NodeType.TEXT,
        variant=ComponentVariant(
            component_id="c1",
            variant_properties={"Size": "Large"},
        ),
    )

    assert variant_size_label(node) == "large"
    assert "fontSize: 18.0" in text_style_expr(node)


def test_box_decoration_uses_circle_shape_for_fully_round_containers() -> None:
    style = NodeStyle(background_color="0xFFFFFFFF", border_radius=27.5)
    decoration = box_decoration_expr(style, width=55.0, height=55.0)

    assert decoration is not None
    assert "BoxShape.circle" in decoration
    assert "borderRadius" not in decoration


def test_dart_color_expr_applies_node_opacity() -> None:
    from figma_flutter_agent.generator.layout.style import dart_color_expr

    style = NodeStyle(background_color="0xFFB6B8BF", opacity=0.3)
    assert dart_color_expr(style) == "Color(0xFFB6B8BF).withOpacity(0.3)"


def test_box_decoration_expr_emits_per_corner_radius_without_flat_radius() -> None:
    """FID-01: box_decoration_expr must emit borderRadius when only corners set."""
    from figma_flutter_agent.schemas import CornerRadii

    style = NodeStyle(
        background_color="0xFF6750A4",
        border_radius_corners=CornerRadii(
            topLeft=52.0, topRight=8.0, bottomRight=8.0, bottomLeft=52.0
        ),
    )
    decoration = box_decoration_expr(style)
    assert decoration is not None
    assert "borderRadius: BorderRadius.only(" in decoration
    assert "topLeft: Radius.circular(52)" in decoration
    assert "topRight: Radius.circular(8)" in decoration


def test_border_radius_expr_per_corner_values_exact() -> None:
    """FID-01: border_radius_expr must use each corner's own value, not the flat radius."""
    from figma_flutter_agent.generator.layout.style import border_radius_expr
    from figma_flutter_agent.schemas import CornerRadii

    style = NodeStyle(
        border_radius=28.0,
        border_radius_corners=CornerRadii(
            topLeft=52.0, topRight=52.0, bottomRight=28.0, bottomLeft=28.0
        ),
    )
    expr = border_radius_expr(style)
    assert "BorderRadius.only(" in expr
    assert "topLeft: Radius.circular(52)" in expr
    assert "topRight: Radius.circular(52)" in expr
    assert "bottomRight: Radius.circular(28)" in expr
    assert "bottomLeft: Radius.circular(28)" in expr
    assert "Radius.circular(28)" not in expr.replace(
        "bottomRight: Radius.circular(28)", ""
    ).replace("bottomLeft: Radius.circular(28)", "")
