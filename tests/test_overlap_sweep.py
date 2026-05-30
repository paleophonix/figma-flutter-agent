"""Sweep-line sibling overlap detection."""

from __future__ import annotations

from figma_flutter_agent.parser.overlap_sweep import (
    OverlapPair,
    PlacementRect,
    cluster_overlapping_ids,
    demote_overlapping_occluders,
    intersection_area,
    placement_rect_from_node,
    sibling_overlap_pairs,
    sweep_overlapping_pairs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, StackPlacement


def test_intersection_area_disjoint() -> None:
    a = PlacementRect("a", 0, 0, 10, 10)
    b = PlacementRect("b", 20, 20, 30, 30)
    assert intersection_area(a, b) == 0.0


def test_sweep_finds_overlapping_pair() -> None:
    rects = [
        PlacementRect("a", 0, 0, 100, 100),
        PlacementRect("b", 50, 50, 150, 150),
        PlacementRect("c", 200, 200, 250, 250),
    ]
    pairs = sweep_overlapping_pairs(rects)
    ids = {pair.first_id for pair in pairs} | {pair.second_id for pair in pairs}
    assert ids == {"a", "b"}


def test_cluster_overlapping_ids_transitive() -> None:
    pairs = [
        OverlapPair("a", "b", 10.0),
        OverlapPair("b", "c", 10.0),
    ]
    groups = cluster_overlapping_ids(pairs)
    assert groups == [frozenset({"a", "b", "c"})]


def test_demote_occluder_below_button() -> None:
    button = CleanDesignTreeNode(
        id="btn",
        name="SignUp",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=0, top=0, width=100, height=40),
    )
    vector = CleanDesignTreeNode(
        id="vec",
        name="Overlay",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=10, top=10, width=80, height=20),
    )
    assert [child.id for child in demote_overlapping_occluders([vector, button])] == [
        "vec",
        "btn",
    ]
    assert [child.id for child in demote_overlapping_occluders([button, vector])] == [
        "vec",
        "btn",
    ]
    pairs = sibling_overlap_pairs([button, vector])
    assert pairs
    rect = placement_rect_from_node(button)
    assert rect is not None
    assert rect.area == 4000.0
