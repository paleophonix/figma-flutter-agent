"""Tests for parse-time stack paint ordering."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.generator.ir_validate import validate_screen_ir
from figma_flutter_agent.parser.stack_paint import (
    apply_stack_paint_order_to_clean_tree,
    sort_absolute_stack_children,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    StackPlacement,
)


def test_sort_absolute_stack_children_puts_large_backdrop_first_at_root() -> None:
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.IMAGE,
        image_asset_key="assets/bg.png",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    ordered = sort_absolute_stack_children(
        [button, backdrop],
        is_layout_root=True,
    )
    assert [child.id for child in ordered] == ["bg", "btn"]


def test_sort_absolute_stack_children_keeps_bottom_checkbox_at_layout_root() -> None:
    checkbox = CleanDesignTreeNode(
        id="cb",
        name="Rectangle 213",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=24.2, height=24.2),
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_color="0xFFA1A4B2",
            border_width=2.0,
            border_radius=4.0,
        ),
        stack_placement=StackPlacement(left=360.0, top=700.0, width=24.2, height=24.2),
    )
    ordered = sort_absolute_stack_children([checkbox], is_layout_root=True)
    assert [child.id for child in ordered] == ["cb"]


def test_apply_stack_paint_order_on_clean_tree_root() -> None:
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.VECTOR,
        vector_asset_key="assets/bg.svg",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    root = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[button, backdrop],
    )
    ordered_root = apply_stack_paint_order_to_clean_tree(root)
    assert [child.id for child in ordered_root.children] == ["bg", "btn"]


def test_validate_aligns_ir_stack_children_to_clean_tree_order() -> None:
    backdrop = CleanDesignTreeNode(
        id="bg",
        name="Bg",
        type=NodeType.VECTOR,
        vector_asset_key="assets/bg.svg",
        sizing=Sizing(width=400.0, height=800.0),
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=800.0),
    )
    button = CleanDesignTreeNode(
        id="btn",
        name="Btn",
        type=NodeType.BUTTON,
        sizing=Sizing(width=120.0, height=44.0),
        stack_placement=StackPlacement(left=20.0, top=100.0, width=120.0, height=44.0),
    )
    root = apply_stack_paint_order_to_clean_tree(
        CleanDesignTreeNode(
            id="root",
            name="Screen",
            type=NodeType.STACK,
            sizing=Sizing(width=414.0, height=896.0),
            children=[backdrop, button],
        ),
    )
    screen_ir = default_screen_ir(root)
    screen_ir.root.children = list(reversed(screen_ir.root.children))
    validate_screen_ir(screen_ir, root)
    assert [child.figma_id for child in screen_ir.root.children] == ["bg", "btn"]
