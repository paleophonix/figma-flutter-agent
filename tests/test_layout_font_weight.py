"""Flutter font weight codegen tests."""

from figma_flutter_agent.generator.layout_style import text_style_expr
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


def test_bundled_medium_renders_as_font_weight_w700() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH GOOGLE",
        style=NodeStyle(
            font_family="Helvetica Neue",
            font_weight="w500",
            font_size=14.0,
            text_color="0xFF3F414E",
        ),
        sizing=Sizing(width=100.0, height=20.0),
    )
    expr = text_style_expr(node, bundled_font_families=frozenset({"Helvetica Neue"}))
    assert "FontWeight.w700" in expr
    assert "FontWeight.w500" not in expr


def test_non_bundled_medium_keeps_w500() -> None:
    node = CleanDesignTreeNode(
        id="1",
        name="Label",
        type=NodeType.TEXT,
        text="Label",
        style=NodeStyle(font_family="Inter", font_weight="w500", font_size=14.0),
        sizing=Sizing(width=100.0, height=20.0),
    )
    expr = text_style_expr(node, bundled_font_families=frozenset({"Helvetica Neue"}))
    assert "FontWeight.w500" in expr
