"""Partial stackChildOrder merge for IR-first screens."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.tree import (
    merge_partial_stack_child_order,
    merge_screen_ir,
    resolve_stack_child_order,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def test_resolve_stack_child_order_keeps_clean_tree_authority() -> None:
    clean = ["1:3662", "1:3665", "1:3677", "1:3970", "1:3974", "1:3977"]
    partial = ["1:3662", "1:3974", "1:3970", "1:3977"]
    order, discrepancies = resolve_stack_child_order(clean, partial)
    assert order == clean
    assert discrepancies == ["1:3662", "1:3974", "1:3970", "1:3977"]


def test_resolve_stack_child_order_inserts_ir_only_nodes() -> None:
    clean = ["a", "b", "c"]
    partial = ["a", "ir_only", "b", "c"]
    order, discrepancies = resolve_stack_child_order(clean, partial)
    assert order == ["a", "ir_only", "b", "c"]
    assert discrepancies == []


def test_merge_partial_stack_child_order_matches_resolve() -> None:
    clean = ["1:3662", "1:3665", "1:3677", "1:3970", "1:3974", "1:3977"]
    partial = ["1:3662", "1:3974", "1:3970", "1:3977"]
    assert merge_partial_stack_child_order(clean, partial) == clean


def test_merge_screen_ir_keeps_logo_and_illustration_stubs() -> None:
    backdrop = CleanDesignTreeNode(
        id="1:3662",
        name="Frame",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=0.0, top=0.0, width=400.0, height=500.0),
    )
    logo = CleanDesignTreeNode(
        id="1:3665",
        name="Group 17",
        type=NodeType.STACK,
        extracted_widget_ref="Group17Widget",
        stack_placement=StackPlacement(left=123.0, top=6.0, width=168.0, height=30.0),
    )
    illustration = CleanDesignTreeNode(
        id="1:3677",
        name="Group",
        type=NodeType.STACK,
        extracted_widget_ref="GroupWidget",
        stack_placement=StackPlacement(left=40.0, top=160.0, width=332.0, height=243.0),
    )
    button = CleanDesignTreeNode(
        id="1:3970",
        name="Group 6778",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=20.0, top=661.0, width=374.0, height=97.0),
    )
    copy = CleanDesignTreeNode(
        id="1:3974",
        name="Group 6791",
        type=NodeType.STACK,
        stack_placement=StackPlacement(left=58.0, top=534.0, width=298.0, height=109.0),
    )
    line = CleanDesignTreeNode(
        id="1:3977",
        name="Line",
        type=NodeType.CONTAINER,
        stack_placement=StackPlacement(left=134.0, top=869.0, width=134.0, height=5.0),
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[backdrop, logo, illustration, button, copy, line],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:3661",
            kind=WidgetIrKind.AUTO,
            children=[
                WidgetIrNode(figma_id="1:3662", kind=WidgetIrKind.STACK, children=[]),
                WidgetIrNode(figma_id="1:3970", kind=WidgetIrKind.STACK, children=[]),
                WidgetIrNode(figma_id="1:3974", kind=WidgetIrKind.STACK, children=[]),
                WidgetIrNode(figma_id="1:3977", kind=WidgetIrKind.AUTO, children=[]),
            ],
        ),
        stack_child_order=["1:3662", "1:3974", "1:3970", "1:3977"],
    )
    merged = merge_screen_ir(
        root,
        screen_ir,
        extracted_class_by_widget_name={
            "Group17Widget": "Group17Widget",
            "GroupWidget": "GroupWidget",
        },
    )
    assert [child.id for child in merged.children] == [
        "1:3662",
        "1:3665",
        "1:3677",
        "1:3970",
        "1:3974",
        "1:3977",
    ]
    logo_node = next(child for child in merged.children if child.id == "1:3665")
    assert logo_node.extracted_widget_ref == "Group17Widget"
