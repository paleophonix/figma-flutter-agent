"""Emit-contract regressions (FID-06, FID-15, FID-19, flex INPUT chrome)."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_widget import render_node_body
from figma_flutter_agent.parser.interaction import (
    input_children_are_presentational,
    looks_like_input_trailing_icon_button,
)
from figma_flutter_agent.parser.layout import (
    clamp_stack_child_placement_to_parent,
    reconcile_stack_placements_in_tree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_clamp_stack_child_placement_to_parent_artboard() -> None:
    placement = StackPlacement(
        horizontal="LEFT_RIGHT",
        left=-20.0,
        right=-20.0,
        width=397.0,
        height=84.0,
        top=0.0,
    )
    clamped = clamp_stack_child_placement_to_parent(placement, 390.0)
    assert clamped.left == 0.0
    assert clamped.width == 390.0
    assert clamped.horizontal == "LEFT"


def test_reconcile_clamps_bleeding_header_in_tree() -> None:
    header = CleanDesignTreeNode(
        id="1:324",
        name="Header",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=397.0, height=84.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            left=-20.0,
            width=397.0,
            height=84.0,
        ),
        style=NodeStyle(background_color="0xFFFCFBF8", layer_blur=24.0),
    )
    root = CleanDesignTreeNode(
        id="1:319",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[header],
    )
    reconciled = reconcile_stack_placements_in_tree(root)
    child = reconciled.children[0]
    assert child.stack_placement is not None
    assert child.stack_placement.left == 0.0
    assert child.stack_placement.width == 390.0


def test_frosted_layer_blur_emits_backdrop_filter() -> None:
    bar = CleanDesignTreeNode(
        id="1:324",
        name="Header",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=84.0),
        style=NodeStyle(
            background_color="0xFFFCFBF8",
            layer_blur=24.0,
            border_radius=28.0,
        ),
        children=[
            CleanDesignTreeNode(
                id="1:325",
                name="Title",
                type=NodeType.TEXT,
                text="Title",
            ),
        ],
    )
    body = render_node_body(bar, uses_svg=False)
    assert "BackdropFilter" in body
    assert "ImageFilter.blur" in body


def test_trailing_icon_detects_deep_vector_nesting() -> None:
    calendar = CleanDesignTreeNode(
        id="1:365",
        name="Button menu",
        type=NodeType.BUTTON,
        sizing=Sizing(width=18.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:366",
                name="image fill",
                type=NodeType.COLUMN,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:367",
                        name="image",
                        type=NodeType.STACK,
                        sizing=Sizing(width=14.0, height=13.0),
                        children=[
                            CleanDesignTreeNode(
                                id="1:368",
                                name="Vector",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=11.0, height=12.0),
                                style=NodeStyle(has_stroke=True),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    assert looks_like_input_trailing_icon_button(calendar)


def test_flex_date_input_emits_text_field_with_fill() -> None:
    calendar = CleanDesignTreeNode(
        id="1:365",
        name="Button menu",
        type=NodeType.BUTTON,
        sizing=Sizing(width=18.0, height=18.0),
        children=[
            CleanDesignTreeNode(
                id="1:366",
                name="image fill",
                type=NodeType.COLUMN,
                sizing=Sizing(width=18.0, height=18.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:367",
                        name="image",
                        type=NodeType.STACK,
                        sizing=Sizing(width=14.0, height=13.0),
                        children=[
                            CleanDesignTreeNode(
                                id="1:368",
                                name="Vector",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=11.0, height=12.0),
                                style=NodeStyle(has_stroke=True),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    field = CleanDesignTreeNode(
        id="1:356",
        name="Input",
        type=NodeType.INPUT,
        sizing=Sizing(width=317.0, height=52.0),
        style=NodeStyle(background_color="0xFFF6F6F2", border_radius=20.0),
        children=[
            CleanDesignTreeNode(
                id="1:357",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width=285.0, height=21.0),
                children=[
                    CleanDesignTreeNode(
                        id="1:360",
                        name="value",
                        type=NodeType.TEXT,
                        text="14.06.1995",
                        sizing=Sizing(width=82.0, height=21.0),
                        style=NodeStyle(text_color="0xFF18181B", font_size=14.0),
                    ),
                    calendar,
                ],
            )
        ],
    )
    assert input_children_are_presentational(field)
    body = render_node_body(field, uses_svg=False)
    assert "TextField" in body
    assert "0xFFF6F6F2" in body


def test_chevron_fallback_uses_readable_size() -> None:
    back = CleanDesignTreeNode(
        id="1:327",
        name="Button",
        type=NodeType.BUTTON,
        sizing=Sizing(width=48.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="1:329",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=5.0, height=10.0),
                style=NodeStyle(has_stroke=True, border_color="0xFF52525C"),
            )
        ],
    )
    body = render_node_body(back, uses_svg=False)
    assert "chevron_left" in body
    assert "size: 24.0" in body or "size: 24," in body
