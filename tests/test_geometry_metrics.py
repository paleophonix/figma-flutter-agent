"""GIoU / DIoU geometry metrics."""

from __future__ import annotations

import math

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.validation.geometry_metrics import (
    GeometryTierThresholds,
    box_metrics,
    geometry_tier_for_node,
    passes_geometry_threshold,
)


def test_box_metrics_identical_boxes() -> None:
    box = (10.0, 20.0, 100.0, 50.0)
    m = box_metrics(box, box)
    assert m.iou == 1.0
    assert m.giou == 1.0
    assert abs(m.diou - 1.0) < 1e-9
    assert m.center_delta_x == 0.0
    assert m.center_delta_y == 0.0


def test_box_metrics_disjoint_boxes_negative_giou() -> None:
    a = (0.0, 0.0, 10.0, 10.0)
    b = (50.0, 50.0, 10.0, 10.0)
    m = box_metrics(a, b)
    assert m.iou == 0.0
    assert m.giou < 0.0
    assert m.diou < 0.0
    assert m.center_delta_x == 50.0
    assert m.center_delta_y == 50.0


def test_disjoint_center_distance() -> None:
    m = box_metrics((0.0, 0.0, 10.0, 10.0), (30.0, 40.0, 10.0, 10.0))
    assert math.isclose(m.center_distance, math.hypot(30.0, 40.0))


def test_geometry_tier_for_node() -> None:
    root = CleanDesignTreeNode(id="root", name="Screen", type=NodeType.STACK)
    text = CleanDesignTreeNode(id="t1", name="Label", type=NodeType.TEXT)
    button = CleanDesignTreeNode(id="b1", name="Btn", type=NodeType.BUTTON)
    assert geometry_tier_for_node(root, root_id="root", depth=0) == "canvas"
    assert geometry_tier_for_node(button, root_id="root", depth=3) == "component"
    assert geometry_tier_for_node(text, root_id="root", depth=5) == "leaf"


def test_passes_geometry_threshold() -> None:
    identical = box_metrics((0, 0, 10, 10), (0, 0, 10, 10))
    assert passes_geometry_threshold(identical, 0.99)
    disjoint = box_metrics((0, 0, 10, 10), (100, 100, 10, 10))
    assert not passes_geometry_threshold(disjoint, 0.82)


def test_tier_thresholds_defaults() -> None:
    tiers = GeometryTierThresholds()
    assert tiers.threshold_for_tier("leaf") == 0.82
    assert tiers.threshold_for_tier("canvas") == 0.99
