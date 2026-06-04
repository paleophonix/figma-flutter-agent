"""Tests for parse-time render boundary vector flattening."""

from __future__ import annotations

import pytest

from figma_flutter_agent.parser.interaction import looks_like_password_field_stack
from figma_flutter_agent.parser.render_boundary import (
    collapse_render_boundaries,
    collect_render_boundary_asset_plan,
    render_boundary_asset_path,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _vector(node_id: str, *, left: float = 0, top: float = 0) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=f"Vector {node_id}",
        type=NodeType.VECTOR,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=left, top=top, width=8, height=8),
        sizing=Sizing(width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED, width=8, height=8),
    )


def _stack(
    node_id: str,
    children: list[CleanDesignTreeNode],
    *,
    width: float = 320,
    height: float = 240,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=f"Group {node_id}",
        type=NodeType.STACK,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=0, top=0, width=width, height=height),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=width,
            height=height,
        ),
        children=children,
    )


def _count_nodes(node: CleanDesignTreeNode) -> int:
    return 1 + sum(_count_nodes(child) for child in node.children)


def test_collapses_vector_only_group() -> None:
    vectors = [_vector(f"v{i}", left=float(i * 10)) for i in range(20)]
    deco = _stack("deco:1", vectors, width=360, height=280)
    root = CleanDesignTreeNode(
        id="screen:1",
        name="Screen",
        type=NodeType.STACK,
        children=[deco],
    )
    before = _count_nodes(root)
    result = collapse_render_boundaries(root)
    assert result.collapsed_count == 1
    assert deco.children == []
    assert deco.render_boundary is True
    assert deco.vector_asset_key == render_boundary_asset_path("deco:1")
    assert len(deco.flatten_figma_node_ids or ()) == 20
    assert before >= 20
    assert _count_nodes(root) == 2


def test_does_not_collapse_button_group() -> None:
    button = CleanDesignTreeNode(
        id="btn:1",
        name="Continue",
        type=NodeType.BUTTON,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=0, top=0, width=200, height=48),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=200,
            height=48,
        ),
        children=[_vector("btn:v1")],
    )
    group = _stack("grp:1", [button, _vector("grp:v1")], width=360, height=120)
    root = CleanDesignTreeNode(id="screen:2", name="Screen", type=NodeType.STACK, children=[group])
    result = collapse_render_boundaries(root)
    assert result.collapsed_count == 0
    assert group.children


def test_password_stack_not_collapsed() -> None:
    surface = CleanDesignTreeNode(
        id="field:bg",
        name="Field surface",
        type=NodeType.CONTAINER,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=0, top=0, width=320, height=56),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=320,
            height=56,
        ),
        style=NodeStyle(background_color="0xFFE5E5E5", border_radius=12),
        children=[],
    )
    field = CleanDesignTreeNode(
        id="field:1",
        name="Password",
        type=NodeType.STACK,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(left=0, top=0, width=320, height=56),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=320,
            height=56,
        ),
        children=[
            surface,
            CleanDesignTreeNode(
                id="field:text",
                name="Dots",
                type=NodeType.TEXT,
                text="••••••••",
                layout_positioning="ABSOLUTE",
                stack_placement=StackPlacement(left=16, top=16, width=200, height=24),
                sizing=Sizing(
                    width_mode=SizingMode.FIXED,
                    height_mode=SizingMode.FIXED,
                    width=200,
                    height=24,
                ),
            ),
            _vector("field:eye"),
        ],
    )
    assert looks_like_password_field_stack(field)
    root = CleanDesignTreeNode(id="screen:3", name="Screen", type=NodeType.STACK, children=[field])
    result = collapse_render_boundaries(root)
    assert result.collapsed_count == 0
    assert field.children


def test_collapses_decorative_group_without_vector_leaves() -> None:
    leaves = [
        CleanDesignTreeNode(
            id=f"c:{i}",
            name=f"Ellipse {i}",
            type=NodeType.CONTAINER,
            layout_positioning="ABSOLUTE",
            stack_placement=StackPlacement(left=float(i * 40), top=0, width=40, height=40),
            sizing=Sizing(
                width_mode=SizingMode.FIXED,
                height_mode=SizingMode.FIXED,
                width=40,
                height=40,
            ),
            style=NodeStyle(background_color="0xFF8BC34A"),
        )
        for i in range(8)
    ]
    group = _stack("grp:union", leaves, width=360, height=140)
    root = CleanDesignTreeNode(id="screen:5", name="Screen", type=NodeType.STACK, children=[group])
    result = collapse_render_boundaries(root)
    assert result.collapsed_count == 1
    assert group.render_boundary is True
    assert group.children == []


def test_pin_render_boundary_preserves_negative_stack_top() -> None:
    """Ambient groups above the frame origin must keep negative ``stackPlacement.top``."""
    group = CleanDesignTreeNode(
        id="1:3610",
        name="Group 6800",
        type=NodeType.STACK,
        offset_y=-77.8,
        layout_positioning="ABSOLUTE",
        stack_placement=StackPlacement(
            left=-41.7,
            top=-77.8,
            right=-91.5,
            bottom=545.6,
            width=547.2,
            height=428.2,
        ),
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=547.2,
            height=428.2,
        ),
        render_boundary=True,
        children=[],
    )
    from figma_flutter_agent.parser.render_boundary import _pin_render_boundary_placement

    _pin_render_boundary_placement(group, parent_height=896.0)
    assert group.stack_placement is not None
    assert group.stack_placement.top == pytest.approx(-77.8, abs=0.1)


def test_collect_render_boundary_asset_plan() -> None:
    boundary = CleanDesignTreeNode(
        id="b:1",
        name="Art",
        type=NodeType.STACK,
        render_boundary=True,
        flatten_figma_node_ids=["c:1", "c:2"],
        vector_asset_key=render_boundary_asset_path("b:1"),
        children=[],
    )
    root = CleanDesignTreeNode(id="screen:4", name="Screen", type=NodeType.STACK, children=[boundary])
    exports, excludes = collect_render_boundary_asset_plan(root)
    assert exports == frozenset({"b:1"})
    assert excludes == frozenset({"c:1", "c:2"})
