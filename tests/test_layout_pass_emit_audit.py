"""Emit audit tests for de-stacked flex hosts."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    Sizing,
    StackPlacement,
)
from tests.support.layout_emit_audit import (
    assert_destacked_type,
    assert_no_positioned_in_flex_host,
    run_passes_and_find_node,
)


def _chip(node_id: str, *, left: float, top: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=NodeType.TEXT,
        text=node_id,
        sizing=Sizing(width=60.0, height=32.0),
        stack_placement=StackPlacement(left=left, top=top, width=60.0, height=32.0),
    )


def test_chip_row_emits_without_positioned() -> None:
    clean = CleanDesignTreeNode(
        id="host",
        name="chip-row",
        type=NodeType.STACK,
        sizing=Sizing(width=400.0, height=40.0),
        children=[
            _chip("a", left=0.0, top=0.0),
            _chip("b", left=68.0, top=0.0),
            _chip("c", left=136.0, top=0.0),
        ],
    )
    node = run_passes_and_find_node(clean, "host")
    assert_destacked_type(node)
    assert_no_positioned_in_flex_host(node)


def test_vertical_list_emits_without_positioned() -> None:
    clean = CleanDesignTreeNode(
        id="host",
        name="labels",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=120.0),
        children=[
            CleanDesignTreeNode(
                id="t1",
                name="t1",
                type=NodeType.TEXT,
                text="one",
                stack_placement=StackPlacement(left=0.0, top=0.0, width=180.0, height=24.0),
            ),
            CleanDesignTreeNode(
                id="t2",
                name="t2",
                type=NodeType.TEXT,
                text="two",
                stack_placement=StackPlacement(left=0.0, top=32.0, width=180.0, height=24.0),
            ),
        ],
    )
    node = run_passes_and_find_node(clean, "host")
    assert node.type == NodeType.COLUMN
    assert_no_positioned_in_flex_host(node)
