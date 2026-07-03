"""Resolver shadow comparison: legacy branches vs pure resolver (06-P0-1c)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.geometry.constraint_algebra import (
    ConstraintOp,
    axis_constraint_from_placement,
    resolve_constraint_axis,
)
from figma_flutter_agent.schemas.geometry import StackPlacement


@dataclass(frozen=True, slots=True)
class ResolverShadowMismatch:
    """One axis where legacy classification disagrees with typed resolver."""

    axis: str
    raw: str
    legacy_op: str
    resolver_op: ConstraintOp


@dataclass(frozen=True, slots=True)
class ResolverShadowReport:
    """Aggregate shadow comparison for one placement."""

    ok: bool
    mismatches: tuple[ResolverShadowMismatch, ...]


def _legacy_op_label(raw: str) -> str:
    return (raw or "LEFT").upper()


def compare_placement_resolver_shadow(
    placement: StackPlacement,
    *,
    parent_width: float = 0.0,
    parent_height: float = 0.0,
) -> ResolverShadowReport:
    """Compare raw placement strings against typed resolver ops (shadow only)."""
    mismatches: list[ResolverShadowMismatch] = []
    for axis, raw, parent_extent in (
        ("horizontal", placement.horizontal, parent_width),
        ("vertical", placement.vertical, parent_height),
    ):
        legacy = _legacy_op_label(str(raw))
        typed = axis_constraint_from_placement(
            raw=str(raw),
            axis="horizontal" if axis == "horizontal" else "vertical",
            left=placement.left,
            top=placement.top,
            right=placement.right,
            bottom=placement.bottom,
            width=placement.width,
            height=placement.height,
            parent_extent=parent_extent,
        )
        resolved = resolve_constraint_axis(typed)
        legacy_to_op = {
            "LEFT": ConstraintOp.PIN_START,
            "TOP": ConstraintOp.PIN_START,
            "RIGHT": ConstraintOp.PIN_END,
            "BOTTOM": ConstraintOp.PIN_END,
            "LEFT_RIGHT": ConstraintOp.PIN_BOTH,
            "TOP_BOTTOM": ConstraintOp.PIN_BOTH,
            "CENTER": ConstraintOp.CENTER,
            "SCALE": ConstraintOp.SCALE,
        }
        expected = legacy_to_op.get(legacy, ConstraintOp.PIN_START)
        if resolved.op != expected:
            mismatches.append(
                ResolverShadowMismatch(
                    axis=axis,
                    raw=legacy,
                    legacy_op=legacy,
                    resolver_op=resolved.op,
                ),
            )
    return ResolverShadowReport(ok=not mismatches, mismatches=tuple(mismatches))
