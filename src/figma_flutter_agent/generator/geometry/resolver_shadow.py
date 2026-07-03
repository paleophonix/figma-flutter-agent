"""Resolver shadow comparison: legacy branches vs pure resolver (06-P0-1c)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from figma_flutter_agent.generator.geometry.constraint_algebra import (
    ResolvedAxisGeometry,
    axis_constraint_from_placement,
    raw_to_resolved_geometry,
    resolve_constraint_axis,
)
from figma_flutter_agent.schemas.geometry import StackPlacement

_DEFAULT_PARENT_EXTENTS = (320.0, 390.0, 430.0)
_GEOMETRY_TOLERANCE = 1e-6
_DEFAULT_SOURCE_EXTENT = 320.0


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


def _legacy_expected_geometry(
    placement: StackPlacement,
    *,
    axis: Literal["horizontal", "vertical"],
    source_parent_extent: float,
    target_parent_extent: float,
) -> ResolvedAxisGeometry:
    """Reference geometry: parse at source extent, apply ratios at target extent."""
    if axis == "horizontal":
        return raw_to_resolved_geometry(
            str(placement.horizontal),
            axis="horizontal",
            left=placement.left,
            right=placement.right,
            width=placement.width,
            source_parent_extent=source_parent_extent,
            target_parent_extent=target_parent_extent,
        )
    return raw_to_resolved_geometry(
        str(placement.vertical),
        axis="vertical",
        top=placement.top,
        bottom=placement.bottom,
        height=placement.height,
        source_parent_extent=source_parent_extent,
        target_parent_extent=target_parent_extent,
    )


def _resolved_geometry(
    placement: StackPlacement,
    *,
    axis: Literal["horizontal", "vertical"],
    source_parent_extent: float,
    target_parent_extent: float,
) -> ResolvedAxisGeometry:
    """Resolver path under test."""
    if axis == "horizontal":
        typed = axis_constraint_from_placement(
            raw=str(placement.horizontal),
            axis="horizontal",
            left=placement.left,
            right=placement.right,
            width=placement.width,
            source_parent_extent=source_parent_extent,
        )
        return resolve_constraint_axis(
            typed,
            target_parent_extent=target_parent_extent,
            child_extent=placement.width,
        )
    typed = axis_constraint_from_placement(
        raw=str(placement.vertical),
        axis="vertical",
        top=placement.top,
        bottom=placement.bottom,
        height=placement.height,
        source_parent_extent=source_parent_extent,
    )
    return resolve_constraint_axis(
        typed,
        target_parent_extent=target_parent_extent,
        child_extent=placement.height,
    )


def _compare_geometry_fields(
    *,
    axis: str,
    parent_extent: float,
    raw: str,
    reference: ResolvedAxisGeometry,
    resolved: ResolvedAxisGeometry,
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
    source_parent_extent: float = _DEFAULT_SOURCE_EXTENT,
    parent_extents: tuple[float, ...] | None = None,
) -> ResolverShadowReport:
    """Compare resolver geometry: constraint frozen at source, resolved at targets."""
    mismatches: list[ResolverShadowMismatch] = []
    targets = parent_extents or _DEFAULT_PARENT_EXTENTS
    for axis, raw in (
        ("horizontal", str(placement.horizontal)),
        ("vertical", str(placement.vertical)),
    ):
        for target_extent in targets:
            if target_extent <= 0 or source_parent_extent <= 0:
                continue
            reference = _legacy_expected_geometry(
                placement,
                axis=axis,  # type: ignore[arg-type]
                source_parent_extent=source_parent_extent,
                target_parent_extent=target_extent,
            )
            resolved = _resolved_geometry(
                placement,
                axis=axis,  # type: ignore[arg-type]
                source_parent_extent=source_parent_extent,
                target_parent_extent=target_extent,
            )
            mismatches.extend(
                _compare_geometry_fields(
                    axis=axis,
                    parent_extent=target_extent,
                    raw=raw,
                    reference=reference,
                    resolved=resolved,
                ),
            )
    return ResolverShadowReport(ok=not mismatches, mismatches=tuple(mismatches))
