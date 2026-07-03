"""Tests for geometry constraint algebra and resolver (06-P0-1)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.geometry.constraint_algebra import (
    ConstraintOp,
    axis_constraint_from_placement,
    raw_to_resolved_slot,
    resolve_constraint_axis,
)
from figma_flutter_agent.generator.geometry.resolver_shadow import (
    compare_placement_resolver_shadow,
    materialize_axis_geometry,
)
from figma_flutter_agent.parser.tree_walk import CleanTreeCycleError, walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.schemas.geometry import StackPlacement


def test_resolve_pin_both_horizontal() -> None:
    typed = axis_constraint_from_placement(
        raw="LEFT_RIGHT",
        axis="horizontal",
        left=8,
        right=8,
        width=100,
    )
    resolved = resolve_constraint_axis(typed)
    assert resolved.op == ConstraintOp.PIN_BOTH
    assert resolved.stretch is True


def test_raw_round_trip_center() -> None:
    slot = raw_to_resolved_slot(
        "CENTER",
        axis="vertical",
        top=10,
        height=20,
        parent_extent=100,
    )
    assert slot.op == ConstraintOp.CENTER
    geom = materialize_axis_geometry(slot, parent_extent=100, child_size=20)
    assert geom.center == pytest.approx(20.0)


def test_resolver_shadow_placement_ok() -> None:
    placement = StackPlacement(horizontal="LEFT", vertical="TOP", left=4, top=6, width=40, height=20)
    report = compare_placement_resolver_shadow(placement)
    assert report.ok is True


@pytest.mark.parametrize("parent_extent", [320.0, 390.0, 430.0])
def test_center_metamorphic_geometry(parent_extent: float) -> None:
    placement = StackPlacement(
        horizontal="CENTER",
        vertical="TOP",
        left=10,
        width=80,
    )
    report = compare_placement_resolver_shadow(
        placement,
        parent_extents=(parent_extent,),
    )
    assert report.ok is True
    slot = raw_to_resolved_slot(
        "CENTER",
        axis="horizontal",
        left=10,
        width=80,
        parent_extent=parent_extent,
    )
    geom = materialize_axis_geometry(slot, parent_extent=parent_extent, child_size=80)
    expected_center = parent_extent / 2.0 + (10 + 80 / 2.0 - parent_extent / 2.0)
    assert geom.center == pytest.approx(expected_center)


def test_pin_end_geometry_invariant() -> None:
    placement = StackPlacement(horizontal="RIGHT", vertical="TOP", right=12, width=50)
    report = compare_placement_resolver_shadow(placement, parent_extents=(320.0,))
    assert report.ok is True


def test_pin_both_geometry_invariant() -> None:
    placement = StackPlacement(
        horizontal="LEFT_RIGHT",
        vertical="TOP",
        left=8,
        right=16,
        width=100,
    )
    report = compare_placement_resolver_shadow(placement, parent_extents=(320.0,))
    assert report.ok is True


def test_scale_geometry_invariant() -> None:
    placement = StackPlacement(
        horizontal="SCALE",
        vertical="TOP",
        left=32,
        width=160,
    )
    report = compare_placement_resolver_shadow(placement, parent_extents=(320.0,))
    assert report.ok is True


def test_clean_tree_cycle_error_fields() -> None:
    a = CleanDesignTreeNode(id="a", name="a", type=NodeType.CONTAINER, children=[])
    b = CleanDesignTreeNode(id="b", name="b", type=NodeType.CONTAINER, children=[])
    a.children = [b]
    b.children = [a]
    with pytest.raises(CleanTreeCycleError) as exc_info:
        walk_clean_tree(a, lambda _n: None, phase="test_cycle")
    err = exc_info.value
    assert err.node_id in {"a", "b"}
    assert err.phase == "test_cycle"
    assert err.path


@pytest.mark.parametrize(
    ("raw", "axis", "expected"),
    [
        ("LEFT", "horizontal", ConstraintOp.PIN_START),
        ("RIGHT", "horizontal", ConstraintOp.PIN_END),
        ("TOP_BOTTOM", "vertical", ConstraintOp.PIN_BOTH),
        ("SCALE", "horizontal", ConstraintOp.SCALE),
    ],
)
def test_metamorphic_raw_to_op(raw: str, axis: str, expected: ConstraintOp) -> None:
    slot = raw_to_resolved_slot(raw, axis=axis)  # type: ignore[arg-type]
    assert slot.op == expected
