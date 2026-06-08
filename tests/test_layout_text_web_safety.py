"""Text layout guards for Flutter Web (tight line height, responsive artboard)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.dart.llm_codegen import (
    strip_tight_proportional_leading_in_text_styles,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_strip_tight_proportional_leading_from_generated_copy_with() -> None:
    source = """
Text('LOG IN', style: Theme.of(context).textTheme.titleMedium?.copyWith(
  color: Color(0xFFF6F1FB),
  fontSize: 14.0,
  height: 1.08,
  leadingDistribution: TextLeadingDistribution.proportional,
),)
"""
    sanitized = strip_tight_proportional_leading_in_text_styles(source)
    assert "height: 1.08" in sanitized
    assert "leadingDistribution" not in sanitized


def test_responsive_layout_scales_artboard_without_positioned_under_material() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        style=NodeStyle(background_color="0xFFFFFFFF"),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Title",
                type=NodeType.TEXT,
                text="Welcome Back!",
                style=NodeStyle(font_size=28.0, text_color="0xFF3F414E"),
                stack_placement=StackPlacement(
                    left=100.0, top=120.0, width=200.0, height=40.0
                ),
            ),
        ],
    )
    layout = render_layout_file(
        root,
        feature_name="sign_in",
        uses_svg=False,
        responsive_enabled=True,
    )["lib/generated/sign_in_layout.dart"]
    assert "Material(color:" in layout
    assert "child: Positioned.fill" not in layout.replace(" ", "")
    assert "Align(" in layout
    assert "FittedBox(" in layout
    assert "alignment: Alignment.topCenter" in layout
    assert "Welcome Back!" in layout
