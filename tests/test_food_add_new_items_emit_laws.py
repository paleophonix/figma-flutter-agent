"""Regression tests for chip stack, nav header, checkbox, and stroke emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout.flex_policy import stack_should_flow_as_column
from figma_flutter_agent.generator.layout.flex_policy.row import (
    layout_fact_stack_tab_switcher_host,
)
from figma_flutter_agent.generator.layout.navigation.items import (
    layout_fact_stack_bottom_nav_tab_glyph_column,
)
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.position import _render_leaf_surface
from figma_flutter_agent.generator.layout.widgets.svg import (
    stack_should_emit_flattened_vector_group,
)
from figma_flutter_agent.parser.interaction import (
    stack_hosts_checkbox_label_pair,
    stack_interaction_kind,
)
from figma_flutter_agent.parser.interaction.forms import (
    checkbox_option_stack_is_checked,
    layout_fact_checkbox_control,
)
from figma_flutter_agent.parser.interaction.icons import (
    layout_fact_stack_vertical_icon_label_chip_tile,
    layout_fact_upload_placeholder_tile,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)

_FOOD_DEBUG = Path(".debug/screen/limbo/food_add_new_items")


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _load_food_root() -> CleanDesignTreeNode:
    path = _FOOD_DEBUG / "processed.json"
    if not path.is_file():
        pytest.skip("food_add_new_items debug bundle unavailable")
    processed = json.loads(path.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


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


def test_ingredient_chip_stack_not_classified_as_input() -> None:
    """Law: vertical_icon_label_chip_not_form_field."""
    chip = _ingredient_chip_stack()
    assert layout_fact_stack_vertical_icon_label_chip_tile(chip)
    assert stack_interaction_kind(chip) == "button"
    emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "TextField(" not in compact
    assert "keyboard_arrow_down" not in compact


def test_food_replay_ingredient_chips_not_text_fields() -> None:
    """Replay corpus chips must not compile as dropdown text fields."""
    root = _load_food_root()
    for node_id in ("602:1142", "602:1169", "602:1153", "602:1098"):
        chip = _find_node(root, node_id)
        assert chip is not None, node_id
        assert stack_interaction_kind(chip) == "button", node_id
        emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
        compact = emitted.replace("\n", "")
        assert "TextField(" not in compact, node_id
        assert "keyboard_arrow_down" not in compact, node_id


def test_food_replay_upload_tile_not_text_field() -> None:
    """Law: upload_placeholder_not_text_field."""
    root = _load_food_root()
    tile = _find_node(root, "602:1184")
    assert tile is not None
    assert layout_fact_upload_placeholder_tile(tile)
    assert stack_interaction_kind(tile) == "button"
    emitted = render_node_body(tile, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "TextField(" not in compact


def test_compact_icon_glyph_group_not_flattened() -> None:
    """Law: icon_chip_glyph_children_not_parent_flatten."""
    group = CleanDesignTreeNode(
        id="1:glyph",
        name="Icon group",
        type=NodeType.STACK,
        sizing=Sizing(width=24.0, height=24.0),
        vector_svg_path_count=3,
        children=[
            CleanDesignTreeNode(
                id="1:v1",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=10.0, height=10.0),
            ),
            CleanDesignTreeNode(
                id="1:v2",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=12.0, height=8.0),
            ),
        ],
    )
    assert not stack_should_emit_flattened_vector_group(group)


def test_checkbox_checked_from_inline_checkmark_vector() -> None:
    """Law: checkbox_reflects_figma_state_and_style."""
    stack = CleanDesignTreeNode(
        id="1:option",
        name="Pick up",
        type=NodeType.STACK,
        sizing=Sizing(width=75.0, height=19.0),
        children=[
            CleanDesignTreeNode(
                id="1:box",
                name="Rectangle",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=18.0, height=18.0),
                style=NodeStyle(
                    border_color="0xFFFB6D3A",
                    border_width=1.0,
                    border_radius=3.0,
                    has_stroke=True,
                ),
                stack_placement=StackPlacement(top=1.0, right=57.0, width=18.0, height=18.0),
            ),
            CleanDesignTreeNode(
                id="1:label",
                name="Pick up",
                type=NodeType.TEXT,
                text="Pick up",
                sizing=Sizing(width=47.0, height=16.0),
                stack_placement=StackPlacement(left=28.0, bottom=3.0, width=47.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="1:mark",
                name="Vector",
                type=NodeType.VECTOR,
                sizing=Sizing(width=8.0, height=6.0),
                style=NodeStyle(border_color="0xFFFB6D3A", border_width=1.5, has_stroke=True),
                stack_placement=StackPlacement(left=5.0, top=7.0, width=8.0, height=6.0),
            ),
        ],
    )
    assert stack_hosts_checkbox_label_pair(stack)
    assert checkbox_option_stack_is_checked(stack)
    emitted = render_node_body(stack, uses_svg=True, parent_type=NodeType.COLUMN)
    compact = emitted.replace("\n", "")
    assert "initialValue: true" in compact
    assert "checkboxTheme: CheckboxThemeData" in compact
    assert "spacing:" in compact


def test_food_replay_pick_up_checkbox_checked_and_spaced() -> None:
    root = _load_food_root()
    stack = _find_node(root, "602:1210")
    assert stack is not None
    assert checkbox_option_stack_is_checked(stack)
    emitted = render_node_body(stack, uses_svg=True, parent_type=NodeType.STACK)
    compact = emitted.replace("\n", "")
    assert "initialValue: true" in compact
    assert "TextField(" not in compact


def test_catalog_chip_label_uses_scale_down_not_ellipsis() -> None:
    chip = _ingredient_chip_stack()
    emitted = render_node_body(chip, uses_svg=True, parent_type=NodeType.STACK)
    assert "FittedBox(fit: BoxFit.scaleDown" in emitted.replace("\n", "")
    assert "TextOverflow.ellipsis" not in emitted
