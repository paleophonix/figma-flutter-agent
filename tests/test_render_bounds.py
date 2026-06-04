"""Tests for render-bounds expansion reconciliation (FID-39)."""

from __future__ import annotations

from figma_flutter_agent.parser.render_bounds import (
    compute_render_bounds_expand,
    expand_stack_placement,
    reconcile_render_bounds_expansion_in_tree,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Padding,
    Sizing,
    StackPlacement,
)


def test_compute_render_bounds_expand_outside_stroke() -> None:
    bbox = {"x": 10.0, "y": 20.0, "width": 100.0, "height": 50.0}
    render = {"x": 8.0, "y": 18.0, "width": 104.0, "height": 54.0}
    expand = compute_render_bounds_expand(bbox, render)
    assert expand is not None
    assert expand.left == 2.0
    assert expand.top == 2.0
    assert expand.right == 2.0
    assert expand.bottom == 2.0


def test_expand_stack_placement_widens_child() -> None:
    placement = StackPlacement(
        horizontal="LEFT",
        vertical="TOP",
        left=10.0,
        top=20.0,
        width=100.0,
        height=50.0,
    )
    expand = Padding(top=2.0, bottom=2.0, left=2.0, right=2.0)
    expanded = expand_stack_placement(placement, expand)
    assert expanded.left == 8.0
    assert expanded.top == 18.0
    assert expanded.width == 104.0
    assert expanded.height == 54.0


def test_reconcile_render_bounds_expansion_in_tree() -> None:
    child = CleanDesignTreeNode(
        id="1:2",
        name="StrokeChild",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=100.0, height=50.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=10.0,
            top=20.0,
            width=100.0,
            height=50.0,
        ),
        style=NodeStyle(
            render_bounds_expand=Padding(top=2.0, bottom=2.0, left=2.0, right=2.0),
        ),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Stack",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=844.0),
        children=[child],
    )
    reconciled = reconcile_render_bounds_expansion_in_tree(root)
    updated = reconciled.children[0].stack_placement
    assert updated is not None
    assert updated.width == 104.0
    assert updated.left == 8.0
