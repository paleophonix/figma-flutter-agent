"""Tests for geometry constraint algebra and resolver (06-P0-1)."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.geometry.constraint_algebra import (
    ConstraintOp,
    axis_constraint_from_placement,
    raw_to_resolved_geometry,
    resolve_constraint_axis,
    resolve_constraint_symbolic,
)
from figma_flutter_agent.generator.geometry.resolver_shadow import compare_placement_resolver_shadow
from figma_flutter_agent.parser.tree_walk import CleanTreeCycleError, walk_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.schemas.geometry import StackPlacement

SOURCE_EXTENT = 320.0


def test_resolve_pin_both_horizontal() -> None:
    typed = axis_constraint_from_placement(
        raw="LEFT_RIGHT",
        axis="horizontal",
        left=8,
        right=8,
        width=100,
        source_parent_extent=SOURCE_EXTENT,
    )
    resolved = resolve_constraint_symbolic(typed)
    assert resolved.op == ConstraintOp.PIN_BOTH
    assert resolved.stretch is True


def test_raw_round_trip_center() -> None:
    geom = raw_to_resolved_geometry(
        "CENTER",
        axis="vertical",
        top=10,
        height=20,
        source_parent_extent=100,
        target_parent_extent=100,
    )
    assert geom.center == pytest.approx(20.0)


def test_resolver_shadow_placement_ok() -> None:
    placement = StackPlacement(horizontal="LEFT", vertical="TOP", left=4, top=6, width=40, height=20)
    report = compare_placement_resolver_shadow(placement, source_parent_extent=SOURCE_EXTENT)
    assert report.ok is True


@pytest.mark.parametrize(
    ("target", "expected_center"),
    [
        (320.0, 160.0),
        (390.0, 195.0),
        (430.0, 215.0),
    ],
)
def test_center_metamorphic_geometry(target: float, expected_center: float) -> None:
    constraint = axis_constraint_from_placement(
        raw="CENTER",
        axis="horizontal",
        left=110,
        width=100,
        source_parent_extent=SOURCE_EXTENT,
    )
    geom = resolve_constraint_axis(
        constraint,
        target_parent_extent=target,
        child_extent=100,
    )
    assert geom.center == pytest.approx(expected_center)


def test_scale_metamorphic_geometry() -> None:
    constraint = axis_constraint_from_placement(
        raw="SCALE",
        axis="horizontal",
        left=32,
        width=160,
        source_parent_extent=SOURCE_EXTENT,
    )
    g320 = resolve_constraint_axis(constraint, target_parent_extent=320, child_extent=160)
    g390 = resolve_constraint_axis(constraint, target_parent_extent=390, child_extent=160)
    assert g320.start == pytest.approx(32.0)
    assert g320.extent == pytest.approx(160.0)
    assert g390.start == pytest.approx(39.0)
    assert g390.extent == pytest.approx(195.0)


def test_pin_end_geometry_invariant() -> None:
    placement = StackPlacement(horizontal="RIGHT", vertical="TOP", right=12, width=50)
    report = compare_placement_resolver_shadow(
        placement,
        source_parent_extent=SOURCE_EXTENT,
        parent_extents=(320.0,),
    )
    assert report.ok is True


def test_pin_both_geometry_invariant() -> None:
    placement = StackPlacement(
        horizontal="LEFT_RIGHT",
        vertical="TOP",
        left=8,
        right=16,
        width=100,
    )
    report = compare_placement_resolver_shadow(
        placement,
        source_parent_extent=SOURCE_EXTENT,
        parent_extents=(320.0,),
    )
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
    typed = axis_constraint_from_placement(raw=raw, axis=axis, source_parent_extent=SOURCE_EXTENT)  # type: ignore[arg-type]
    slot = resolve_constraint_symbolic(typed)
    assert slot.op == expected
