"""Extended layout style mapping tests."""

from figma_flutter_agent.generator.layout_style import (
    box_decoration_expr,
    gradient_fill_expr,
    text_style_expr,
)
from figma_flutter_agent.generator.variant_props import variant_size_label
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ComponentVariant,
    GradientFill,
    GradientStop,
    NodeStyle,
    NodeType,
    ShadowEffect,
)


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
    assert "Alignment" in expr
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
    assert "Border.all(color: Color(0xFFEBEAEC), width: 1.0)" in decoration
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
    from figma_flutter_agent.generator.layout_style import dart_color_expr

    style = NodeStyle(background_color="0xFFB6B8BF", opacity=0.3)
    assert dart_color_expr(style) == "Color(0xFFB6B8BF).withOpacity(0.3)"
