"""Runtime geometry: Figma placement vs golden figma_keys bounds."""

from __future__ import annotations

import json

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, StackPlacement, Sizing
from figma_flutter_agent.validation.runtime_geometry import (
    compare_runtime_to_figma,
    format_geometry_feedback,
    geometry_feedback_from_mapper_payload,
    load_runtime_bounds_json,
    placement_iou,
    RuntimeBounds,
)


def test_placement_iou_identical_boxes() -> None:
    a = RuntimeBounds(left=10.0, top=20.0, width=100.0, height=50.0)
    b = RuntimeBounds(left=10.0, top=20.0, width=100.0, height=50.0)
    assert placement_iou(a, b) == 1.0


def test_compare_runtime_flags_missing_widget() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Button",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=0.0, top=100.0, width=200.0, height=60.0),
            ),
        ],
    )
    mismatches = compare_runtime_to_figma(root, {}, node_ids=["1:2"], min_iou=0.95)
    assert len(mismatches) == 1
    assert mismatches[0].missing
    assert "GIoU = 0" in mismatches[0].format_feedback_line()


def test_geometry_feedback_from_mapper_payload() -> None:
    tree = load_layout_tree("sign_up_and_sign_in")
    payload = {
        "1_3972": {"left": 156.0, "top": 0.0, "width": 74.0, "height": 17.0},
    }
    feedback = geometry_feedback_from_mapper_payload(tree, payload, min_iou=0.99)
    assert feedback == "" or "figma_id" in feedback


def test_load_runtime_bounds_json() -> None:
    raw = json.dumps(
        {"1_3665": {"left": 1.0, "top": 2.0, "width": 10.0, "height": 20.0}},
    )
    bounds = load_runtime_bounds_json(raw)
    assert "1:3665" in bounds
    assert bounds["1:3665"].width == 10.0


def test_compare_runtime_uses_giou_gate() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Label",
                type=NodeType.TEXT,
                stack_placement=StackPlacement(left=0.0, top=0.0, width=100.0, height=20.0),
            ),
        ],
    )
    runtime = RuntimeBounds(left=0.0, top=0.0, width=100.0, height=20.0)
    mismatches = compare_runtime_to_figma(
        root,
        {"1:2": runtime},
        node_ids=["1:2"],
        use_tier_thresholds=True,
    )
    assert mismatches == []


def test_format_geometry_feedback_limits_lines() -> None:
    from figma_flutter_agent.validation.runtime_geometry import GeometryMismatch

    items = [
        GeometryMismatch(
            figma_id=f"1:{index}",
            iou=0.0,
            giou=0.0,
            diou=-1.0,
            expected=RuntimeBounds(0, 0, 10, 10),
            runtime=None,
            delta_left=0,
            delta_top=0,
            missing=True,
        )
        for index in range(5)
    ]
    text = format_geometry_feedback(items, max_lines=2)
    assert "and 3 more" in text
