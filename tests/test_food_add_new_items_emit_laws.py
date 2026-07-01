"""Regression tests for chip stack, nav header, checkbox, and stroke emit laws."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.flex_policy import stack_should_flow_as_column
from figma_flutter_agent.generator.layout.flex_policy.row import (
    layout_fact_stack_tab_switcher_host,
)
from figma_flutter_agent.generator.layout.navigation.items import (
    layout_fact_stack_bottom_nav_tab_glyph_column,
)
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.position import _render_leaf_surface
from figma_flutter_agent.parser.interaction import stack_hosts_checkbox_label_pair
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def _ingredient_chip_stack() -> CleanDesignTreeNode:
    """Absolute icon + plate + label chip; must not flow as bottom-nav column."""
    return CleanDesignTreeNode(
        id="1:chip",
        name="Ingredient",
        type=NodeType.STACK,
        sizing=Sizing(width=50.0, height=70.0),
        children=[
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Tomato",
                sizing=Sizing(width=36.0, height=13.0),
                stack_placement=StackPlacement(
                    horizontal="SCALE",
                    left=7.0,
                    top=57.0,
                    width=36.0,
                    height=13.0,
                ),
            ),
            CleanDesignTreeNode(
                id="1:plate",
                name="Circle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=50.0, height=50.0),
                style=NodeStyle(
                    background_color="0xFFFDFDFD",
                    border_color="0xFFE8EAED",
                    border_width=1.0,
                    stroke_align="OUTSIDE",
                    border_radius=25.0,
                ),
                stack_placement=StackPlacement(
                    horizontal="LEFT",
                    left=0.0,
                    top=0.0,
                    width=50.0,
                    height=50.0,
                ),
            ),
            CleanDesignTreeNode(
                id="1:icon",
                name="Icon",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                stack_placement=StackPlacement(
                    horizontal="LEFT",
                    left=13.0,
                    top=13.0,
                    width=24.0,
                    height=24.0,
                ),
            ),
        ],
    )


def _app_bar_header_stack() -> CleanDesignTreeNode:
    """Three-slot nav header: trailing action, back, centered title."""
    return CleanDesignTreeNode(
        id="1:header",
        name="Header",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=45.0),
        children=[
            CleanDesignTreeNode(
                id="1:reset",
                name="Reset",
                type=NodeType.TEXT,
                text="Reset",
                sizing=Sizing(width=40.0, height=17.0),
            ),
            CleanDesignTreeNode(
                id="1:back",
                name="Back",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="1:title",
                name="Title",
                type=NodeType.TEXT,
                text="Add New Items",
                sizing=Sizing(width=120.0, height=22.0),
            ),
        ],
    )


def _checkbox_option_stack() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:option",
        name="Delivery option",
        type=NodeType.STACK,
        sizing=Sizing(width=120.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:box",
                name="Checkbox",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=20.0, height=20.0),
                style=NodeStyle(border_color="0xFFE8EAED", border_width=1.0),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Label",
                type=NodeType.TEXT,
                text="Delivery",
                sizing=Sizing(width=60.0, height=17.0),
            ),
        ],
    )


def test_absolute_chip_stack_not_bottom_nav_glyph_column() -> None:
    """Law: positioned_child_requires_stack_parent — no column lowering for overlay chips."""
    chip = _ingredient_chip_stack()
    assert not layout_fact_stack_bottom_nav_tab_glyph_column(chip)
    assert not stack_should_flow_as_column(chip)


def test_app_bar_header_not_tab_switcher_host() -> None:
    """Law: app_bar_slots_leading_center_title_trailing_action."""
    header = _app_bar_header_stack()
    assert not layout_fact_stack_tab_switcher_host(header)


def test_stack_checkbox_label_pair_detected() -> None:
    """Law: compound_input_may_contain_option_controls_without_retyping_options_as_text_fields."""
    stack = _checkbox_option_stack()
    assert stack_hosts_checkbox_label_pair(stack)


def test_stack_checkbox_emits_row_not_text_field() -> None:
    """Checkbox option stacks must not compile as TextField hosts."""
    emitted = render_node_body(
        _checkbox_option_stack(),
        uses_svg=True,
        parent_type=NodeType.COLUMN,
    )
    compact = emitted.replace("\n", "")
    assert "Checkbox" in compact or "checkbox" in compact.lower()
    assert "TextField(" not in compact
    assert "TextFormField(" not in compact


def test_outside_stroke_leaf_surface_emits_foreground_decoration() -> None:
    """Law: container_stroke_preserved — OUTSIDE strokes use foregroundDecoration."""
    plate = CleanDesignTreeNode(
        id="1:plate",
        name="Circle",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=50.0, height=50.0),
        style=NodeStyle(
            background_color="0xFFFDFDFD",
            border_color="0xFFE8EAED",
            border_width=1.0,
            stroke_align="OUTSIDE",
            border_radius=25.0,
        ),
    )
    emitted = _render_leaf_surface(plate)
    assert emitted is not None
    assert "foregroundDecoration" in emitted
    assert "0xFFE8EAED" in emitted


def test_upload_strip_overflow_wraps_horizontal_scroll() -> None:
    """Law: overflowing_horizontal_content_strip_must_scroll."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_stack_overflowing_horizontal_content_strip,
    )

    parent = CleanDesignTreeNode(
        id="1:parent",
        name="Body",
        type=NodeType.STACK,
        sizing=Sizing(width=375.0, height=200.0),
    )
    strip = CleanDesignTreeNode(
        id="1:strip",
        name="Upload strip",
        type=NodeType.STACK,
        sizing=Sizing(width=381.0, height=111.0),
        children=[
            CleanDesignTreeNode(
                id="1:a",
                name="Tile",
                type=NodeType.STACK,
                sizing=Sizing(width=111.0, height=111.0),
            ),
            CleanDesignTreeNode(
                id="1:b",
                name="Tile",
                type=NodeType.STACK,
                sizing=Sizing(width=111.0, height=111.0),
            ),
        ],
    )
    assert layout_fact_stack_overflowing_horizontal_content_strip(
        strip,
        parent_node=parent,
    )
    emitted = render_node_body(
        strip,
        uses_svg=True,
        parent_type=NodeType.STACK,
        parent_node=parent,
    )
    assert "SingleChildScrollView(scrollDirection: Axis.horizontal" in emitted.replace("\n", "")


def test_single_line_input_vertical_center_uses_center_align() -> None:
    """Law: single_line_input_vertical_center."""
    from figma_flutter_agent.generator.layout.widgets.input.fields import (
        _prefilled_input_field_expr,
    )

    field = _prefilled_input_field_expr(
        escaped_value="Item",
        obscure="false",
        input_style="Theme.of(context).textTheme.bodyMedium",
        decoration="const InputDecoration(border: InputBorder.none)",
        vertical_center=True,
    )
    assert "TextAlignVertical.center" in field
    assert "TextAlignVertical.top" not in field
