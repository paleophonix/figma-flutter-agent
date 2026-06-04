"""Combinatorial layout fixtures (WP-L / CORE-20 starter set)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.stack_paint import _is_bottom_nav_background_shell
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _stack_screen(
    width: float,
    height: float,
    *,
    children: list[CleanDesignTreeNode],
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=width, height=height),
        children=children,
    )


def test_viewport_relative_bottom_nav_shell_on_tablet() -> None:
    width, height = 768.0, 1024.0
    bar = CleanDesignTreeNode(
        id="bar",
        name="Bar",
        type=NodeType.CONTAINER,
        style=NodeStyle(background_color="#FF0000"),
        sizing=Sizing(width=width, height=100.0),
        stack_placement=StackPlacement(
            left=0.0,
            top=height * 0.76,
            width=width,
            height=100.0,
        ),
    )
    assert _is_bottom_nav_background_shell(
        bar,
        viewport_width=width,
        viewport_height=height,
    )


def test_normalize_then_deterministic_emit_compiles_stack() -> None:
    button = CleanDesignTreeNode(
        id="cta",
        name="CTA",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(
            left=20.0,
            top=400.0,
            width=200.0,
            height=48.0,
        ),
    )
    root = _stack_screen(390.0, 844.0, children=[button])
    normalized = normalize_clean_tree(root)
    files = render_layout_file(
        normalized,
        feature_name="combinatorics_cta",
        uses_svg=False,
        skip_layout_reconcile=True,
    )
    layout = files["lib/generated/combinatorics_cta_layout.dart"]
    assert "Stack(" in layout
    assert "Positioned(" in layout


def test_flex_input_column_emits_material_field_when_normalized() -> None:
    label = CleanDesignTreeNode(
        id="label",
        name="Label",
        type=NodeType.TEXT,
        text="Email",
    )
    field = CleanDesignTreeNode(
        id="field",
        name="Field",
        type=NodeType.INPUT,
        children=[label],
        sizing=Sizing(width_mode="HUG", height_mode="HUG"),
    )
    row = CleanDesignTreeNode(
        id="row",
        name="Row",
        type=NodeType.ROW,
        children=[field],
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Form",
        type=NodeType.COLUMN,
        sizing=Sizing(width=360.0, height=600.0),
        children=[row],
    )
    normalized = normalize_clean_tree(root)
    files = render_layout_file(
        normalized,
        feature_name="combinatorics_input",
        uses_svg=False,
        skip_layout_reconcile=True,
    )
    layout = files["lib/generated/combinatorics_input_layout.dart"]
    assert "TextField" in layout or "TextFormField" in layout
