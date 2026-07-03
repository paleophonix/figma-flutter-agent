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
    """Symbolic planner slot (op + parameters, no target parent extent)."""

    model_config = IMMUTABLE_TREE_CONFIG

    op: ConstraintOp
    fixed_start: float | None = None
    fixed_end: float | None = None
    stretch: bool = False
    center_delta: float = 0.0
    scale_offset_ratio: float = 0.0
    scale_size_ratio: float = 1.0


class ResolvedAxisGeometry(BaseModel):
    """Concrete axis geometry for a target parent extent."""

    model_config = IMMUTABLE_TREE_CONFIG

    start: float
    end: float
    extent: float
    center: float
    residual: float


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
    source_parent_extent: float = 0.0,
    parent_extent: float | None = None,
) -> AxisConstraint:
    """Build symbolic ``AxisConstraint`` using source parent extent for ratios."""
    extent = source_parent_extent if parent_extent is None else parent_extent
    op = raw_axis_to_constraint_op(raw, axis=axis)
    if axis == "horizontal":
        start, end, size = left, right, width
    else:
        start, end, size = top, bottom, height
    center_delta = 0.0
    scale_offset_ratio = 0.0
    scale_size_ratio = 1.0
    if op == ConstraintOp.CENTER and extent > 0 and size is not None:
        center_delta = start + size / 2.0 - extent / 2.0
    if op == ConstraintOp.SCALE and extent > 0:
        scale_offset_ratio = start / extent
        if size is not None:
            scale_size_ratio = size / extent
    return AxisConstraint(
        op=op,
        start_offset=start,
        end_offset=end,
        size=size,
        center_delta=center_delta,
        scale_offset_ratio=scale_offset_ratio,
        scale_size_ratio=scale_size_ratio,
    )


def resolve_constraint_axis(
    constraint: AxisConstraint,
    *,
    target_parent_extent: float,
    child_extent: float | None = None,
) -> ResolvedAxisGeometry:
    """Resolve symbolic constraint to concrete geometry for a target parent extent."""
    size = child_extent if child_extent is not None else (constraint.size or 0.0)
    if constraint.op == ConstraintOp.PIN_START:
        start = constraint.start_offset
        extent = size
        end = start + extent
    elif constraint.op == ConstraintOp.PIN_END:
        end = target_parent_extent - constraint.end_offset
        extent = size
        start = end - extent
    elif constraint.op == ConstraintOp.PIN_BOTH:
        start = constraint.start_offset
        end = target_parent_extent - constraint.end_offset
        extent = max(0.0, end - start)
    elif constraint.op == ConstraintOp.CENTER:
        center = target_parent_extent / 2.0 + constraint.center_delta
        extent = size
        start = center - extent / 2.0
        end = center + extent / 2.0
    elif constraint.op == ConstraintOp.SCALE:
        start = target_parent_extent * constraint.scale_offset_ratio
        extent = target_parent_extent * constraint.scale_size_ratio
        end = start + extent
    else:
        start = constraint.start_offset
        extent = size
        end = start + extent
    center = start + extent / 2.0
    residual = target_parent_extent - end - start
    return ResolvedAxisGeometry(
        start=start,
        end=end,
        extent=extent,
        center=center,
        residual=residual,
    )


def resolve_constraint_symbolic(constraint: AxisConstraint) -> ResolvedAxisSlot:
    """Map constraint parameters to symbolic slot without target extent."""
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


def raw_to_resolved_geometry(
    raw: str,
    *,
    axis: Literal["horizontal", "vertical"],
    left: float = 0.0,
    top: float = 0.0,
    right: float = 0.0,
    bottom: float = 0.0,
    width: float | None = None,
    height: float | None = None,
    source_parent_extent: float,
    target_parent_extent: float,
) -> ResolvedAxisGeometry:
    """Parse at source extent, resolve at target extent."""
    typed = axis_constraint_from_placement(
        raw=raw,
        axis=axis,
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        width=width,
        height=height,
        source_parent_extent=source_parent_extent,
    )
    child = width if axis == "horizontal" else height
    return resolve_constraint_axis(
        typed,
        target_parent_extent=target_parent_extent,
        child_extent=child,
    )
