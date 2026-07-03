"""Typed constraint axis model and pure resolver (Program 06 P0-1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from figma_flutter_agent.schemas.types import IMMUTABLE_TREE_CONFIG


class ConstraintOp(StrEnum):
    """Parameterized constraint operation on one axis."""

    PIN_START = "pin_start"
    PIN_END = "pin_end"
    PIN_BOTH = "pin_both"
    CENTER = "center"
    SCALE = "scale"


class AxisConstraint(BaseModel):
    """Typed single-axis constraint derived from raw Figma placement."""

    model_config = IMMUTABLE_TREE_CONFIG

    op: ConstraintOp
    start_offset: float = 0.0
    end_offset: float = 0.0
    size: float | None = None
    center_delta: float = 0.0
    scale_offset_ratio: float = 0.0
    scale_size_ratio: float = 1.0


class ResolvedAxisSlot(BaseModel):
    """Planner-facing resolved slot for one axis."""

    model_config = IMMUTABLE_TREE_CONFIG

    op: ConstraintOp
    fixed_start: float | None = None
    fixed_end: float | None = None
    stretch: bool = False
    center_delta: float = 0.0
    scale_offset_ratio: float = 0.0
    scale_size_ratio: float = 1.0


_H_TO_OP: dict[str, ConstraintOp] = {
    "LEFT": ConstraintOp.PIN_START,
    "RIGHT": ConstraintOp.PIN_END,
    "LEFT_RIGHT": ConstraintOp.PIN_BOTH,
    "CENTER": ConstraintOp.CENTER,
    "SCALE": ConstraintOp.SCALE,
}

_V_TO_OP: dict[str, ConstraintOp] = {
    "TOP": ConstraintOp.PIN_START,
    "BOTTOM": ConstraintOp.PIN_END,
    "TOP_BOTTOM": ConstraintOp.PIN_BOTH,
    "CENTER": ConstraintOp.CENTER,
    "SCALE": ConstraintOp.SCALE,
}


def raw_axis_to_constraint_op(
    value: str,
    *,
    axis: Literal["horizontal", "vertical"],
) -> ConstraintOp:
    """Map raw Figma axis string to ``ConstraintOp``."""
    table = _H_TO_OP if axis == "horizontal" else _V_TO_OP
    key = (value or "").upper()
    if key not in table:
        msg = f"Unknown {axis} constraint: {value!r}"
        raise ValueError(msg)
    return table[key]


def axis_constraint_from_placement(
    *,
    raw: str,
    axis: Literal["horizontal", "vertical"],
    left: float = 0.0,
    top: float = 0.0,
    right: float = 0.0,
    bottom: float = 0.0,
    width: float | None = None,
    height: float | None = None,
    parent_extent: float = 0.0,
) -> AxisConstraint:
    """Build ``AxisConstraint`` from raw placement fields (additive, no side effects)."""
    op = raw_axis_to_constraint_op(raw, axis=axis)
    if axis == "horizontal":
        start, end, size = left, right, width
    else:
        start, end, size = top, bottom, height
    center_delta = 0.0
    scale_offset_ratio = 0.0
    scale_size_ratio = 1.0
    if op == ConstraintOp.CENTER and parent_extent > 0 and size is not None:
        center_delta = start + size / 2.0 - parent_extent / 2.0
    if op == ConstraintOp.SCALE and parent_extent > 0:
        scale_offset_ratio = start / parent_extent
        if size is not None:
            scale_size_ratio = size / parent_extent
    return AxisConstraint(
        op=op,
        start_offset=start,
        end_offset=end,
        size=size,
        center_delta=center_delta,
        scale_offset_ratio=scale_offset_ratio,
        scale_size_ratio=scale_size_ratio,
    )


def resolve_constraint_axis(constraint: AxisConstraint) -> ResolvedAxisSlot:
    """Pure authoritative resolver for one axis constraint."""
    stretch = constraint.op == ConstraintOp.PIN_BOTH
    fixed_start = constraint.start_offset if constraint.op == ConstraintOp.PIN_START else None
    fixed_end = constraint.end_offset if constraint.op == ConstraintOp.PIN_END else None
    if constraint.op == ConstraintOp.PIN_BOTH:
        fixed_start = constraint.start_offset
        fixed_end = constraint.end_offset
    return ResolvedAxisSlot(
        op=constraint.op,
        fixed_start=fixed_start,
        fixed_end=fixed_end,
        stretch=stretch,
        center_delta=constraint.center_delta,
        scale_offset_ratio=constraint.scale_offset_ratio,
        scale_size_ratio=constraint.scale_size_ratio,
    )


def raw_to_resolved_slot(
    raw: str,
    *,
    axis: Literal["horizontal", "vertical"],
    left: float = 0.0,
    top: float = 0.0,
    right: float = 0.0,
    bottom: float = 0.0,
    width: float | None = None,
    height: float | None = None,
    parent_extent: float = 0.0,
) -> ResolvedAxisSlot:
    """Round-trip helper: raw placement → resolved slot."""
    typed = axis_constraint_from_placement(
        raw=raw,
        axis=axis,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        width=width,
        height=height,
        parent_extent=parent_extent,
    )
    return resolve_constraint_axis(typed)
