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


def test_compute_style_outward_expand_fallback_outside_stroke() -> None:
    from figma_flutter_agent.parser.render_bounds import compute_style_outward_expand_fallback

    style = NodeStyle(
        has_stroke=True,
        stroke_align="OUTSIDE",
        border_width=4.0,
    )
    expand = compute_style_outward_expand_fallback(style)
    assert expand is not None
    assert expand.left == 4.0
    assert expand.top == 4.0


def test_compute_style_outward_expand_fallback_drop_shadow() -> None:
    from figma_flutter_agent.parser.render_bounds import compute_style_outward_expand_fallback
    from figma_flutter_agent.schemas import ShadowEffect

    style = NodeStyle(
        effects=[
            ShadowEffect(
                kind="drop", blur=24.0, spread=0.0, offset_x=0.0, offset_y=8.0, color="0xFF000000"
            ),
        ],
    )
    expand = compute_style_outward_expand_fallback(style)
    assert expand is not None
    assert expand.bottom >= 12.0


def test_stack_needs_soft_clip_when_child_has_outward_shadow() -> None:
    from figma_flutter_agent.parser.render_bounds import stack_needs_soft_clip
    from figma_flutter_agent.schemas import ShadowEffect

    child = CleanDesignTreeNode(
        id="1:2",
        name="Card",
        type=NodeType.CONTAINER,
        style=NodeStyle(
            effects=[ShadowEffect(kind="drop", blur=24.0, color="0xFF000000")],
        ),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Stack",
        type=NodeType.STACK,
        children=[child],
    )
    assert stack_needs_soft_clip(root) is True


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
    assert updated.width == 100.0
    assert updated.left == 10.0


def test_reconcile_preserves_render_bounds_expand_field() -> None:
    child = CleanDesignTreeNode(
        id="1:2",
        name="Card",
        type=NodeType.CONTAINER,
        stack_placement=StackPlacement(
            horizontal="LEFT_RIGHT",
            vertical="TOP",
            left=22.0,
            right=22.0,
            top=40.0,
            width=331.0,
            height=94.0,
        ),
        style=NodeStyle(
            render_bounds_expand=Padding(top=28.0, bottom=36.0, left=22.0, right=22.0),
        ),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Stack",
        type=NodeType.STACK,
        children=[child],
    )
    reconciled = reconcile_render_bounds_expansion_in_tree(root)
    updated = reconciled.children[0]
    assert updated.stack_placement is not None
    assert updated.stack_placement.left == 22.0
    assert updated.stack_placement.right == 22.0
    assert updated.stack_placement.height == 94.0
    assert updated.style.render_bounds_expand is not None
    assert updated.style.render_bounds_expand.top == 28.0


def test_figma_positioned_dimensions_ignore_render_bounds_expand() -> None:
    from figma_flutter_agent.generator.layout.widgets import figma_positioned_dimensions

    node = CleanDesignTreeNode(
        id="1:2",
        name="Tile",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=140.0,
            top=407.0,
            width=100.0,
            height=100.0,
        ),
        style=NodeStyle(
            render_bounds_expand=Padding(top=25.0, bottom=35.0, left=30.0, right=30.0),
        ),
    )
    width, height = figma_positioned_dimensions(node)
    assert width == 100.0
    assert height == 100.0


def test_wrap_paint_overflow_export_keeps_layout_box() -> None:
    from figma_flutter_agent.generator.layout.widgets.svg import (
        _render_exported_vector,
    )

    node = CleanDesignTreeNode(
        id="1:2",
        name="Tile",
        type=NodeType.STACK,
        sizing=Sizing(width=100.0, height=100.0),
        stack_placement=StackPlacement(
            horizontal="LEFT",
            vertical="TOP",
            left=0.0,
            top=0.0,
            width=100.0,
            height=100.0,
        ),
        style=NodeStyle(
            render_bounds_expand=Padding(top=25.0, bottom=35.0, left=30.0, right=30.0),
        ),
        vector_asset_key="assets/icons/tile.svg",
    )
    body = _render_exported_vector(node, uses_svg=True)
    assert body is not None
    assert "SizedBox(width: 100.0, height: 100.0" in body
    assert "left: -30.0" in body
    assert "top: -25.0" in body
    assert "width: 160.0" in body
    assert "height: 160.0" in body
