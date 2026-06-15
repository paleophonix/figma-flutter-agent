"""Unit tests for layout pass activation criteria."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.layout_criteria import (
    evaluate_scroll_host,
    evaluate_stack_flex_candidate,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _chip(
    node_id: str,
    *,
    left: float,
    top: float,
    width: float = 60.0,
    height: float = 32.0,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=NodeType.BUTTON,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=width,
            height=height,
        ),
        stack_placement=StackPlacement(left=left, top=top, width=width, height=height),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=left, y=top, width=width, height=height),
        ),
    )


def test_horizontal_row_candidate_activates() -> None:
    stack = CleanDesignTreeNode(
        id="row-stack",
        name="chips",
        type=NodeType.STACK,
        sizing=Sizing(width=400.0, height=40.0),
        children=[
            _chip("a", left=0.0, top=0.0),
            _chip("b", left=68.0, top=0.0),
            _chip("c", left=136.0, top=0.0),
        ],
    )
    decision = evaluate_stack_flex_candidate(stack)
    assert decision.activated is True
    assert decision.target_type == NodeType.ROW
    assert decision.gap_mode == "uniform"
    assert decision.spacing == 8.0


def test_reversed_paint_order_rejects_horizontal_unstack() -> None:
    stack = CleanDesignTreeNode(
        id="reversed-row",
        name="reversed",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=40.0),
        children=[
            _chip("b", left=68.0, top=0.0),
            _chip("a", left=0.0, top=0.0),
        ],
    )
    decision = evaluate_stack_flex_candidate(stack)
    assert decision.activated is False
    assert decision.reject_reason == "no_axis_candidate"


def test_overlap_rejects_candidate() -> None:
    stack = CleanDesignTreeNode(
        id="overlap",
        name="bad",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=40.0),
        children=[
            _chip("a", left=0.0, top=0.0, width=80.0),
            _chip("b", left=40.0, top=0.0, width=80.0),
        ],
    )
    decision = evaluate_stack_flex_candidate(stack)
    assert decision.activated is False


def test_two_row_wrap_cluster_activates() -> None:
    children = [
        _chip("r0c0", left=0.0, top=0.0),
        _chip("r0c1", left=68.0, top=0.0),
        _chip("r0c2", left=136.0, top=0.0),
        _chip("r1c0", left=0.0, top=40.0),
        _chip("r1c1", left=68.0, top=40.0),
        _chip("r1c2", left=136.0, top=40.0),
    ]
    stack = CleanDesignTreeNode(
        id="wrap-stack",
        name="chips-wrap",
        type=NodeType.STACK,
        sizing=Sizing(width=390.0, height=80.0),
        children=children,
    )
    decision = evaluate_stack_flex_candidate(stack)
    assert decision.activated is True
    assert decision.target_type == NodeType.WRAP


def test_vertical_column_candidate_activates() -> None:
    stack = CleanDesignTreeNode(
        id="col-stack",
        name="labels",
        type=NodeType.STACK,
        sizing=Sizing(width=200.0, height=200.0),
        children=[
            CleanDesignTreeNode(
                id="t1",
                name="t1",
                type=NodeType.TEXT,
                text="one",
                stack_placement=StackPlacement(left=0.0, top=0.0, width=180.0, height=24.0),
                geometry_frame=GeometryFrame(
                    layout_rect=GeomRect(x=0.0, y=0.0, width=180.0, height=24.0),
                ),
            ),
            CleanDesignTreeNode(
                id="t2",
                name="t2",
                type=NodeType.TEXT,
                text="two",
                stack_placement=StackPlacement(left=0.0, top=32.0, width=180.0, height=24.0),
                geometry_frame=GeometryFrame(
                    layout_rect=GeomRect(x=0.0, y=32.0, width=180.0, height=24.0),
                ),
            ),
        ],
    )
    decision = evaluate_stack_flex_candidate(stack)
    assert decision.activated is True
    assert decision.target_type == NodeType.COLUMN
    assert decision.axis == "vertical"


def test_scroll_host_uses_artboard_height() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=896.0),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=390.0, height=896.0),
        ),
        children=[
            CleanDesignTreeNode(
                id="body",
                name="body",
                type=NodeType.TEXT,
                text="x",
                stack_placement=StackPlacement(left=0.0, top=900.0, width=100.0, height=400.0),
            ),
        ],
    )
    above = evaluate_scroll_host(root, artboard_height=896.0, fallback_threshold_px=900)
    assert above.activated is True
    short_root = root.model_copy(update={"children": []})
    below = evaluate_scroll_host(short_root, artboard_height=896.0, fallback_threshold_px=900)
    assert below.activated is False


def test_generated_horizontal_rows_activate_uniformly() -> None:
    for count in range(2, 6):
        children = [_chip(f"n{index}", left=float(index * 68), top=0.0) for index in range(count)]
        stack = CleanDesignTreeNode(
            id="generated-row",
            name="row",
            type=NodeType.STACK,
            sizing=Sizing(width=500.0, height=40.0),
            children=children,
        )
        first = evaluate_stack_flex_candidate(stack)
        second = evaluate_stack_flex_candidate(stack)
        assert first == second
        assert first.activated is True
        assert first.target_type == NodeType.ROW
        assert first.gap_mode == "uniform"


def test_scroll_host_fallback_threshold() -> None:
    root = CleanDesignTreeNode(
        id="root",
        name="screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=1200.0),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=390.0, height=1200.0),
        ),
        children=[],
    )
    decision = evaluate_scroll_host(root, artboard_height=None, fallback_threshold_px=900)
    assert decision.activated is True
