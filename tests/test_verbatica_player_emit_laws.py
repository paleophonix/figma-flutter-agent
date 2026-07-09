"""Verbatica player emit-law regressions (flex bounds, nav title font, CTA opacity)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.flex_policy.wrap import (
    repair_constrainedbox_unbounded_row_flex_in_source,
)
from figma_flutter_agent.generator.layout.style.text_emit import text_style_expr
from figma_flutter_agent.generator.layout.widgets.finalize import _wrap_group_opacity
from figma_flutter_agent.generator.subtree.render import _render_subtree_widget_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
)
from figma_flutter_agent.schemas.style import ComponentVariant


def test_repair_constrainedbox_pins_width_before_expanded_row() -> None:
    source = (
        "SizedBox(width: 393.0, child: Row(children: ["
        "ConstrainedBox(constraints: BoxConstraints(minHeight: 167.0), "
        "child: Padding(padding: const EdgeInsets.all(16.0), child: Row(children: ["
        "Expanded(child: Text('player'))])))]))"
    )
    repaired = repair_constrainedbox_unbounded_row_flex_in_source(source)
    assert "minWidth: 393.0" in repaired
    assert "maxWidth: 393.0" in repaired


def test_subtree_nav_title_preserves_bundled_font_family() -> None:
    title = CleanDesignTreeNode(
        id="title",
        name="Lesson title",
        type=NodeType.TEXT,
        text="Урок 1",
        style=NodeStyle(
            font_family="Nekst",
            font_size=16.0,
            font_weight="w600",
            text_color="0xFF19191A",
        ),
        sizing=Sizing(width=69.2, height=19.0),
    )
    bar = CleanDesignTreeNode(
        id="bar",
        name="Top bar",
        type=NodeType.STACK,
        sizing=Sizing(width=393.0, height=44.0),
        children=[title],
    )
    body = _render_subtree_widget_body(
        bar,
        class_name="PlayerTopBarWidget",
        uses_svg=False,
        bundled_font_families=frozenset({"Nekst", "SF Pro Text"}),
    )
    assert "fontFamily: 'Nekst'" in body


def test_nav_title_text_style_emits_bundled_font_family() -> None:
    node = CleanDesignTreeNode(
        id="title",
        name="Lesson title",
        type=NodeType.TEXT,
        text="Урок 1",
        style=NodeStyle(
            font_family="Nekst",
            font_size=16.0,
            font_weight="w600",
            text_color="0xFF19191A",
        ),
    )
    expr = text_style_expr(
        node,
        bundled_font_families=frozenset({"Nekst"}),
    )
    assert "fontFamily: 'Nekst'" in expr


def test_painted_primary_button_skips_group_opacity_wrap() -> None:
    button = CleanDesignTreeNode(
        id="cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=361.0, height=56.0),
        style=NodeStyle(
            background_color="0xFF8459C9",
            border_radius=20.0,
            opacity=0.5,
        ),
        variant=ComponentVariant(
            component_id="111:16846",
            component_name="Button",
            variant_properties={"Type": "Primary"},
        ),
        children=[],
    )
    wrapped = _wrap_group_opacity(button, "const SizedBox.shrink()")
    assert "Opacity(" not in wrapped


def test_disabled_button_keeps_group_opacity_wrap() -> None:
    button = CleanDesignTreeNode(
        id="cta",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=361.0, height=56.0),
        style=NodeStyle(
            background_color="0xFF8459C9",
            border_radius=20.0,
            opacity=0.5,
        ),
        variant=ComponentVariant(
            component_id="111:16846",
            component_name="Button",
            variant_properties={"Type": "Primary", "State": "Disabled"},
        ),
        children=[],
    )
    wrapped = _wrap_group_opacity(button, "const SizedBox.shrink()")
    assert "Opacity(opacity: 0.5" in wrapped
