"""Geometry invariant violation models."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

ViolationSeverity = Literal["hard", "soft"]

_promote_soft_pixel_ctx: ContextVar[bool] = ContextVar("promote_soft_pixel", default=False)

_SOFT_PIXEL_CODES = frozenset(
    {
        "t1_reproject",
        "inv_reproject",
        "t1_placement_origin",
        "t1_placement_aabb_width",
        "t2_flex_conservation",
        "t2_bounded_slot_conservation",
        "t2_artboard_extent_drift",
        "t3_baseline_delta",
        "inv_text_metrics",
    }
)

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
    "inv_type_truth": "hard",
    "inv_classification_scope": "hard",
    "t1_reproject": "soft",
    "inv_reproject": "soft",
    "t1_placement_origin": "soft",
    "t1_placement_aabb_width": "soft",
    "t2_flex_conservation": "soft",
    "t2_bounded_slot_conservation": "soft",
    "t2_artboard_extent_drift": "soft",
    "t3_baseline_delta": "soft",
    "inv_text_metrics": "soft",
    "t5_repaint_partition": "soft",
}


@contextmanager
def promote_soft_pixel_invariants_scope(enabled: bool) -> Iterator[None]:
    """Temporarily promote soft pixel invariant codes to hard severity."""
    token = _promote_soft_pixel_ctx.set(enabled)
    try:
        yield
    finally:
        _promote_soft_pixel_ctx.reset(token)


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
        if _promote_soft_pixel_ctx.get() and code in _SOFT_PIXEL_CODES:
            severity = "hard"
    return GeometryInvariantViolation(
        code=code,
        node_id=node_id,
        detail=detail,
        severity=severity,
    )
