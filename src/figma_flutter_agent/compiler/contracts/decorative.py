"""Decorative primitive contract (Program 07 P0-1, report-only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

DecorativeRole = Literal["plate", "glyph", "stroke", "substrate", "unknown"]
DecorativeTier = Literal[
    "native_verified",
    "native_unverified",
    "styled_primitive",
    "svg_baked",
    "png_baked",
    "unsupported",
]


class DecorativeVerdict(StrEnum):
    PRESERVED = "preserved"
    DOWNGRADED = "downgraded"
    COLLAPSED = "collapsed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DecorativePrimitiveRecord:
    """Report-only decorative routing observation."""

    node_id: str
    role: DecorativeRole
    tier: DecorativeTier
    route: str
    verdict: DecorativeVerdict
    detail: str = ""


def evaluate_decorative_node(
    *,
    node_id: str,
    route: str,
    render_boundary: bool = False,
    has_vector_asset: bool = False,
    record_downgrade: bool = True,
) -> DecorativePrimitiveRecord:
    """Classify decorative primitive handling without mutating emit."""
    if render_boundary and has_vector_asset:
        role: DecorativeRole = "glyph"
        tier: DecorativeTier = "svg_baked"
        verdict = DecorativeVerdict.COLLAPSED
    elif render_boundary:
        role = "plate"
        tier = "png_baked"
        verdict = DecorativeVerdict.COLLAPSED
    else:
        role = "unknown"
        tier = "native_unverified"
        verdict = DecorativeVerdict.UNKNOWN
    record = DecorativePrimitiveRecord(
        node_id=node_id,
        role=role,
        tier=tier,
        route=route,
        verdict=verdict,
    )
    if record_downgrade and verdict == DecorativeVerdict.COLLAPSED:
        from figma_flutter_agent.debug.provenance import (
            DeviationReason,
            DeviationSeverity,
            get_provenance_recorder,
        )

        recorder = get_provenance_recorder()
        if recorder is not None:
            recorder.record_deviation(
                node_id=node_id,
                field="decorative_tier",
                before="native_unverified",
                after=tier,
                reason=DeviationReason.FIDELITY_DOWNGRADE,
                source=route,
                severity=DeviationSeverity.DEGRADED,
                provenance={"role": role, "verdict": verdict.value},
            )
    return record
