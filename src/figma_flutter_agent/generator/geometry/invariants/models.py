"""Geometry invariant violation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ViolationSeverity = Literal["hard", "soft"]

VIOLATION_SEVERITY: dict[str, ViolationSeverity] = {
    "constraint_normal": "hard",
    "inv_unit": "hard",
    "inv_emit_no_translate": "hard",
    "inv_affine_det": "hard",
    "inv_flex_axis": "hard",
    "missing_layout_slot": "hard",
    "inv_z": "hard",
    "inv_node_multiset": "hard",
    "inv_stack_paint_order": "hard",
    "inv_style_truth": "hard",
    "inv_graph_sync": "hard",
    "t1_reproject": "soft",
    "inv_reproject": "soft",
    "t1_placement_origin": "soft",
    "t1_placement_aabb_width": "soft",
    "t2_flex_conservation": "soft",
    "t2_bounded_slot_conservation": "soft",
    "t2_artboard_extent_drift": "soft",
    "t3_baseline_delta": "soft",
    "t5_repaint_partition": "soft",
}


@dataclass(frozen=True)
class GeometryInvariantViolation:
    """One failed geometry theorem check."""

    code: str
    node_id: str
    detail: str
    severity: ViolationSeverity


def geometry_violation(
    code: str,
    node_id: str,
    detail: str,
    *,
    strict: bool = False,
) -> GeometryInvariantViolation:
    """Build a violation with severity from ``VIOLATION_SEVERITY``."""
    if code == "inv_ast_coverage":
        severity: ViolationSeverity = "hard" if strict else "soft"
    else:
        severity = VIOLATION_SEVERITY.get(code, "hard")
    return GeometryInvariantViolation(
        code=code,
        node_id=node_id,
        detail=detail,
        severity=severity,
    )
