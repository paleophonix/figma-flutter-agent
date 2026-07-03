"""Resolver shadow comparison: legacy branches vs pure resolver (06-P0-1c)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.generator.geometry.constraint_algebra import (
    ConstraintOp,
    ResolvedAxisSlot,
    axis_constraint_from_placement,
    resolve_constraint_axis,
)
from figma_flutter_agent.schemas.geometry import StackPlacement

_DEFAULT_PARENT_EXTENTS = (320.0, 390.0, 430.0)
_GEOMETRY_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class AxisGeometry:
    """Materialized axis geometry for shadow parity."""

    start: float
    end: float
    extent: float
    center: float
    residual: float


@dataclass(frozen=True, slots=True)
class ResolverShadowMismatch:
    """One axis/parent extent where resolver geometry disagrees with reference."""

    axis: str
    parent_extent: float
    field: str
    reference: float
    resolved: float
    raw: str


@dataclass(frozen=True, slots=True)
class ResolverShadowReport:
    """Aggregate shadow comparison for one placement."""

    ok: bool
    mismatches: tuple[ResolverShadowMismatch, ...]


def materialize_axis_geometry(
    slot: ResolvedAxisSlot,
    *,
    parent_extent: float,
    child_size: float | None,
) -> AxisGeometry:
    """Compute start/end/extent/center/residual from a resolved slot."""
    size = child_size or 0.0
    if slot.op == ConstraintOp.PIN_START:
        start = slot.fixed_start or 0.0
        extent = size
        end = start + extent
    elif slot.op == ConstraintOp.PIN_END:
        end = parent_extent - (slot.fixed_end or 0.0)
        extent = size
        start = end - extent
    elif slot.op == ConstraintOp.PIN_BOTH:
        start = slot.fixed_start or 0.0
        end = parent_extent - (slot.fixed_end or 0.0)
        extent = max(0.0, end - start)
    elif slot.op == ConstraintOp.CENTER:
        center = parent_extent / 2.0 + slot.center_delta
        extent = size
        start = center - extent / 2.0
        end = center + extent / 2.0
    elif slot.op == ConstraintOp.SCALE:
        start = parent_extent * slot.scale_offset_ratio
        extent = parent_extent * slot.scale_size_ratio
        end = start + extent
    else:
        start = 0.0
        extent = size
        end = start + extent
    center = start + extent / 2.0
    residual = parent_extent - end - start
    return AxisGeometry(
        start=start,
        end=end,
        extent=extent,
        center=center,
        residual=residual,
    )


def _resolved_slot_from_placement(
    placement: StackPlacement,
    *,
    axis: Literal["horizontal", "vertical"],
    parent_extent: float,
) -> ResolvedAxisSlot:
    """Typed resolver pipeline under test."""
    if axis == "horizontal":
        typed = axis_constraint_from_placement(
            raw=str(placement.horizontal),
            axis="horizontal",
            left=placement.left,
            right=placement.right,
            width=placement.width,
            parent_extent=parent_extent,
        )
    else:
        typed = axis_constraint_from_placement(
            raw=str(placement.vertical),
            axis="vertical",
            top=placement.top,
            bottom=placement.bottom,
            height=placement.height,
            parent_extent=parent_extent,
        )
    return resolve_constraint_axis(typed)


def _legacy_expected_geometry(
    placement: StackPlacement,
    *,
    axis: Literal["horizontal", "vertical"],
    parent_extent: float,
) -> AxisGeometry:
    """Reference geometry from placement fields (independent of resolver pipeline)."""
    if axis == "horizontal":
        raw = (placement.horizontal or "LEFT").upper()
        start_offset = placement.left
        end_offset = placement.right
        size = placement.width
    else:
        raw = (placement.vertical or "TOP").upper()
        start_offset = placement.top
        end_offset = placement.bottom
        size = placement.height
    child_size = size or 0.0

    if raw in {"LEFT", "TOP"}:
        start = start_offset
        extent = child_size
        end = start + extent
    elif raw in {"RIGHT", "BOTTOM"}:
        end = parent_extent - end_offset
        extent = child_size
        start = end - extent
    elif raw in {"LEFT_RIGHT", "TOP_BOTTOM"}:
        start = start_offset
        end = parent_extent - end_offset
        extent = max(0.0, end - start)
    elif raw == "CENTER":
        center = parent_extent / 2.0 + (start_offset + child_size / 2.0 - parent_extent / 2.0)
        extent = child_size
        start = center - extent / 2.0
        end = center + extent / 2.0
    elif raw == "SCALE" and parent_extent > 0:
        start = parent_extent * (start_offset / parent_extent)
        extent = parent_extent * (child_size / parent_extent)
        end = start + extent
    else:
        start = start_offset
        extent = child_size
        end = start + extent
    center = start + extent / 2.0
    residual = parent_extent - end - start
    return AxisGeometry(
        start=start,
        end=end,
        extent=extent,
        center=center,
        residual=residual,
    )


def _compare_geometry_fields(
    *,
    axis: str,
    parent_extent: float,
    raw: str,
    reference: AxisGeometry,
    resolved: AxisGeometry,
) -> list[ResolverShadowMismatch]:
    mismatches: list[ResolverShadowMismatch] = []
    for field in ("start", "end", "extent", "center", "residual"):
        ref_val = getattr(reference, field)
        res_val = getattr(resolved, field)
        if abs(ref_val - res_val) > _GEOMETRY_TOLERANCE:
            mismatches.append(
                ResolverShadowMismatch(
                    axis=axis,
                    parent_extent=parent_extent,
                    field=field,
                    reference=ref_val,
                    resolved=res_val,
                    raw=raw,
                ),
            )
    return mismatches


def compare_placement_resolver_shadow(
    placement: StackPlacement,
    *,
    parent_width: float = 0.0,
    parent_height: float = 0.0,
    parent_extents: tuple[float, ...] | None = None,
) -> ResolverShadowReport:
    """Compare resolver materialized geometry against legacy placement formulas."""
    mismatches: list[ResolverShadowMismatch] = []
    for axis, raw, size, parent_values in (
        (
            "horizontal",
            str(placement.horizontal),
            placement.width,
            parent_extents or ((parent_width,) if parent_width > 0 else _DEFAULT_PARENT_EXTENTS),
        ),
        (
            "vertical",
            str(placement.vertical),
            placement.height,
            parent_extents or ((parent_height,) if parent_height > 0 else _DEFAULT_PARENT_EXTENTS),
        ),
    ):
        for parent_extent in parent_values:
            if parent_extent <= 0:
                continue
            resolved_slot = _resolved_slot_from_placement(
                placement,
                axis=axis,  # type: ignore[arg-type]
                parent_extent=parent_extent,
            )
            reference_geom = _legacy_expected_geometry(
                placement,
                axis=axis,  # type: ignore[arg-type]
                parent_extent=parent_extent,
            )
            resolved_geom = materialize_axis_geometry(
                resolved_slot,
                parent_extent=parent_extent,
                child_size=size,
            )
            mismatches.extend(
                _compare_geometry_fields(
                    axis=axis,
                    parent_extent=parent_extent,
                    raw=raw,
                    reference=reference_geom,
                    resolved=resolved_geom,
                ),
            )
    return ResolverShadowReport(ok=not mismatches, mismatches=tuple(mismatches))
