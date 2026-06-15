"""T2 extent conservation and prefix rounding."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.checks import _check_t2_flex_conservation
from figma_flutter_agent.generator.geometry.planner import extent_conservation_error
from figma_flutter_agent.parser.numeric_rounding import round_axis_prefix
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    LayoutBackend,
    LayoutSlotIr,
    NodeType,
    Sizing,
    SizingMode,
    WrapKind,
)


def test_round_axis_prefix_conserves_parent_span() -> None:
    parent = 100.0
    children = [33.333, 33.333, 33.334]
    boundaries = [0.0]
    cursor = 0.0
    for span in children:
        cursor += span
        boundaries.append(cursor)
    boundaries[-1] = parent
    rounded = round_axis_prefix(boundaries)
    segments = [rounded[i + 1] - rounded[i] for i in range(len(rounded) - 1)]
    assert abs(sum(segments) - rounded[-1]) < 1e-9


def test_extent_conservation_error_within_tolerance() -> None:
    parent = 100.0
    children = [50.0, 50.0]
    assert extent_conservation_error(parent, children) <= 0.5


def test_extent_conservation_error_detects_drift() -> None:
    parent = 100.0
    children = [40.0, 40.0]
    assert extent_conservation_error(parent, children) > 0.5


def _flex_row_with_rigid_child(
    *,
    row_id: str,
    parent_width: float,
    child_width: float,
    wraps: tuple[WrapKind, ...],
) -> CleanDesignTreeNode:
    child = CleanDesignTreeNode(
        id=f"{row_id}:child",
        name="Child",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=child_width, height=48.0),
        geometry_frame=GeometryFrame(
            local_transform=Affine2(),
            layout_rect=GeomRect(width=child_width, height=48.0),
            intrinsic_size=GeomRect(width=child_width, height=48.0),
        ),
        layout_slot=LayoutSlotIr(
            backend=LayoutBackend.FLEX,
            slot_rect=GeomRect(width=child_width, height=48.0),
            wraps=wraps,
        ),
    )
    return CleanDesignTreeNode(
        id=row_id,
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=parent_width, height=48.0),
        geometry_frame=GeometryFrame(
            local_transform=Affine2(),
            layout_rect=GeomRect(width=parent_width, height=48.0),
            intrinsic_size=GeomRect(width=parent_width, height=48.0),
        ),
        layout_slot=LayoutSlotIr(
            backend=LayoutBackend.FLEX,
            slot_rect=GeomRect(width=parent_width, height=48.0),
        ),
        children=[child],
    )


def test_t2_allows_loose_slack_under_fill_row() -> None:
    row = _flex_row_with_rigid_child(
        row_id="1:row",
        parent_width=357.0,
        child_width=191.0,
        wraps=(WrapKind.FLEXIBLE_LOOSE,),
    )
    assert _check_t2_flex_conservation(row) is None


def test_t2_detects_rigid_overflow() -> None:
    left = CleanDesignTreeNode(
        id="1:left",
        name="Left",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=200.0, height=48.0),
        geometry_frame=GeometryFrame(
            intrinsic_size=GeomRect(width=200.0, height=48.0),
        ),
        layout_slot=LayoutSlotIr(
            backend=LayoutBackend.FLEX,
            slot_rect=GeomRect(width=200.0, height=48.0),
            wraps=(WrapKind.FLEXIBLE_LOOSE,),
        ),
    )
    right = CleanDesignTreeNode(
        id="1:right",
        name="Right",
        type=NodeType.CONTAINER,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=200.0, height=48.0),
        geometry_frame=GeometryFrame(
            intrinsic_size=GeomRect(width=200.0, height=48.0),
        ),
        layout_slot=LayoutSlotIr(
            backend=LayoutBackend.FLEX,
            slot_rect=GeomRect(width=200.0, height=48.0),
            wraps=(WrapKind.FLEXIBLE_LOOSE,),
        ),
    )
    row = CleanDesignTreeNode(
        id="1:row",
        name="Row",
        type=NodeType.ROW,
        sizing=Sizing(width_mode=SizingMode.FILL, width=357.0, height=48.0),
        geometry_frame=GeometryFrame(
            intrinsic_size=GeomRect(width=357.0, height=48.0),
        ),
        layout_slot=LayoutSlotIr(
            backend=LayoutBackend.FLEX,
            slot_rect=GeomRect(width=357.0, height=48.0),
        ),
        children=[left, right],
    )
    violation = _check_t2_flex_conservation(row)
    assert violation is not None
    assert violation.code == "t2_flex_conservation"
