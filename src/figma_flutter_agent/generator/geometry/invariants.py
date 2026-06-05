"""Geometry invariant validation for translation theory (T1–T5).

Soft-check epsilon budgets (single source of truth):
- ``geom_epsilon()`` — general sub-pixel tolerance (see ``affine.py``).
- ``_T2_OVERFLOW_TOLERANCE`` — flex rigid-child overflow before SOFT ``t2_flex_conservation``.
- ``_BASELINE_EPSILON`` — text baseline delta before SOFT ``t3_baseline_delta``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from loguru import logger

from figma_flutter_agent.generator.geometry.affine import (
    aabb_residual,
    affine_det,
    expand_aabb,
    geom_epsilon,
    is_axis_aligned,
    requires_raster_tier,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    LayerClass,
    LayoutBackend,
    NodeType,
    SizingMode,
    WrapKind,
)

_BASELINE_EPSILON = 0.5
_T2_OVERFLOW_TOLERANCE = 0.5

ViolationSeverity = Literal["hard", "soft"]

VIOLATION_SEVERITY: dict[str, ViolationSeverity] = {
    "constraint_normal": "hard",
    "inv_unit": "hard",
    "inv_emit_no_translate": "hard",
    "inv_affine_det": "hard",
    "inv_flex_axis": "hard",
    "missing_layout_slot": "hard",
    "inv_z": "hard",
    "t1_reproject": "soft",
    "inv_reproject": "soft",
    "t1_placement_origin": "soft",
    "t1_placement_aabb_width": "soft",
    "t2_flex_conservation": "soft",
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
    """Build a violation with severity from ``VIOLATION_SEVERITY`` (or context for ast coverage)."""
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


def partition_geometry_violations(
    violations: list[GeometryInvariantViolation],
) -> tuple[list[GeometryInvariantViolation], list[GeometryInvariantViolation]]:
    """Split violations into hard (fail-closed) and soft (log+degrade) lists."""
    hard = [item for item in violations if item.severity == "hard"]
    soft = [item for item in violations if item.severity == "soft"]
    return hard, soft


def count_violations_by_code(
    violations: list[GeometryInvariantViolation],
) -> dict[str, int]:
    """Count violations grouped by code (for telemetry)."""
    return dict(Counter(item.code for item in violations))


def raise_on_hard_geometry_violations(
    violations: list[GeometryInvariantViolation],
    *,
    context: str,
) -> list[GeometryInvariantViolation]:
    """Log soft violations; raise ``GenerationError`` only when hard violations exist."""
    hard, soft = partition_geometry_violations(violations)
    if soft:
        summary = "; ".join(f"{v.code}@{v.node_id}" for v in soft[:6])
        extra = len(soft) - 6
        suffix = f" (+{extra} more)" if extra > 0 else ""
        logger.warning(
            "Geometry soft invariant violations ({}){}: {}",
            context,
            suffix,
            summary,
        )
    if not hard:
        return soft
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in hard[:6])
    extra = len(hard) - 6
    suffix = f" (+{extra} more)" if extra > 0 else ""
    from figma_flutter_agent.errors import GenerationError

    raise GenerationError(
        f"Geometry invariant violations ({context}): {summary}{suffix}"
    )


def mark_degraded_nodes(
    root: CleanDesignTreeNode,
    soft_violations: list[GeometryInvariantViolation],
) -> CleanDesignTreeNode:
    """Mark ``layout_slot.degraded`` on nodes with soft invariant violations."""
    if not soft_violations:
        return root
    degraded_ids = {item.node_id for item in soft_violations}

    def visit(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        new_children: list[CleanDesignTreeNode] = []
        children_changed = False
        for child in node.children:
            updated_child = visit(child)
            new_children.append(updated_child)
            if updated_child is not child:
                children_changed = True
        slot = node.layout_slot
        if node.id in degraded_ids and slot is not None and not slot.degraded:
            slot = slot.model_copy(update={"degraded": True})
            return node.model_copy(update={"layout_slot": slot, "children": new_children})
        if children_changed:
            return node.model_copy(update={"children": new_children})
        return node

    return visit(root)


def _walk_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []

    def visit(node: CleanDesignTreeNode) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return nodes


def _check_t1_reproject(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    """Verify world cascade reprojection in tree space (not Figma document space)."""
    frame = node.geometry_frame
    if frame is None or frame.world_transform is None:
        return None
    intrinsic = frame.intrinsic_size
    if intrinsic.width <= geom_epsilon() and intrinsic.height <= geom_epsilon():
        return None
    derived = expand_aabb(frame.world_transform, intrinsic.width, intrinsic.height)
    # ``parsed_world_aabb`` is in Figma document coordinates; after ``plan_geometry_tree``
    # the authoritative box is ``world_aabb`` (root-relative cascade output).
    reference = frame.world_aabb if frame.world_aabb is not None else derived
    if reference.width <= geom_epsilon() and reference.height <= geom_epsilon():
        return None
    residual = aabb_residual(reference, derived)
    if residual <= geom_epsilon():
        return None
    return geometry_violation(
        code="t1_reproject",
        node_id=node.id,
        detail=f"world AABB residual {residual:.3f}px > {geom_epsilon()}",
    )


def _check_t1_placement(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    frame = node.geometry_frame
    slot = node.layout_slot
    if frame is None or slot is None or slot.positioned_pins is None:
        return None
    local = frame.local_transform
    if is_axis_aligned(local):
        return None
    origin = frame.placement_origin
    pins = slot.positioned_pins
    if origin is None or pins.left is None or pins.top is None:
        return None
    if abs(origin.x - pins.left) > geom_epsilon() or abs(origin.y - pins.top) > geom_epsilon():
        return geometry_violation(
            code="t1_placement_origin",
            node_id=node.id,
            detail="Positioned origin must match placement_origin for rotated nodes",
        )
    return None


def _flex_rigid_main_axis_spans(
    node: CleanDesignTreeNode,
) -> tuple[float | None, list[float], int]:
    """Return padded parent span, non-Expanded child spans, and flex child count."""
    flex_child_count = sum(1 for child in node.children if child.layout_slot is not None)
    if node.type == NodeType.ROW:
        parent_span = (
            node.sizing.width or node.geometry_frame.intrinsic_size.width
            if node.geometry_frame
            else None
        )
        if parent_span is not None:
            parent_span -= (node.padding.left or 0.0) + (node.padding.right or 0.0)
        rigid_spans: list[float] = []
        for child in node.children:
            slot = child.layout_slot
            if slot is None or WrapKind.EXPANDED in slot.wraps:
                continue
            rigid_spans.append(slot.slot_rect.width)
        return parent_span, rigid_spans, flex_child_count
    if node.type == NodeType.COLUMN:
        parent_span = (
            node.sizing.height or node.geometry_frame.intrinsic_size.height
            if node.geometry_frame
            else None
        )
        if parent_span is not None:
            parent_span -= (node.padding.top or 0.0) + (node.padding.bottom or 0.0)
        rigid_spans = []
        for child in node.children:
            slot = child.layout_slot
            if slot is None or WrapKind.EXPANDED in slot.wraps:
                continue
            rigid_spans.append(slot.slot_rect.height)
        return parent_span, rigid_spans, flex_child_count
    return None, [], 0


def _check_t2_flex_conservation(
    node: CleanDesignTreeNode,
) -> GeometryInvariantViolation | None:
    """Fail only when rigid flex children overflow the parent main-axis span."""
    slot = node.layout_slot
    if slot is None or slot.backend != LayoutBackend.FLEX:
        return None
    if node.stack_placement is not None:
        return None
    if node.type not in {NodeType.ROW, NodeType.COLUMN} or not node.children:
        return None
    if node.type == NodeType.COLUMN and node.sizing.height_mode == SizingMode.HUG:
        return None
    if node.type == NodeType.ROW and node.sizing.width_mode == SizingMode.HUG:
        return None
    parent_span, rigid_spans, flex_child_count = _flex_rigid_main_axis_spans(node)
    if parent_span is None or parent_span <= 0 or not rigid_spans:
        return None
    if all(span <= geom_epsilon() for span in rigid_spans):
        return None
    gap_total = node.spacing * max(0, flex_child_count - 1)
    overflow = sum(rigid_spans) + gap_total - parent_span
    if overflow <= _T2_OVERFLOW_TOLERANCE:
        return None
    return geometry_violation(
        code="t2_flex_conservation",
        node_id=node.id,
        detail=f"flex overflow {overflow:.3f}px > {_T2_OVERFLOW_TOLERANCE}",
    )


def _check_t3_baseline(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    metrics = node.text_metrics_frame
    if metrics is None or metrics.delta_top is None:
        return None
    if abs(metrics.delta_top) <= _BASELINE_EPSILON:
        return None
    slot = node.layout_slot
    if node.type == NodeType.INPUT and metrics.input_padding_top is not None:
        return None
    if slot is not None and WrapKind.DELTA_TOP_PADDING in slot.wraps:
        return None
    return geometry_violation(
        code="t3_baseline_delta",
        node_id=node.id,
        detail=f"delta_top={metrics.delta_top:.3f} without padding channel",
    )


def _check_inv_flex_axis(
    node: CleanDesignTreeNode,
    parent: CleanDesignTreeNode | None,
) -> GeometryInvariantViolation | None:
    if parent is None or parent.type not in {NodeType.ROW, NodeType.COLUMN}:
        return None
    slot = node.layout_slot
    if slot is None or WrapKind.EXPANDED not in slot.wraps:
        return None
    if (
        parent.type == NodeType.COLUMN
        and node.sizing.width_mode == SizingMode.FILL
        and node.sizing.height_mode != SizingMode.FILL
    ):
        return geometry_violation(
            code="inv_flex_axis",
            node_id=node.id,
            detail="Column width FILL requires cross-stretch, not Expanded",
        )
    if (
        parent.type == NodeType.ROW
        and node.sizing.height_mode == SizingMode.FILL
        and node.sizing.width_mode != SizingMode.FILL
    ):
        return geometry_violation(
            code="inv_flex_axis",
            node_id=node.id,
            detail="Row height FILL requires cross-stretch, not Expanded",
        )
    return None


def _check_inv_affine_det(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    slot = node.layout_slot
    frame = node.geometry_frame
    if slot is None or frame is None:
        return None
    local = slot.residual_matrix or frame.local_transform
    if local is None:
        return None
    det = affine_det(local)
    if requires_raster_tier(local) and slot.residual_matrix is not None:
        return geometry_violation(
            code="inv_affine_det",
            node_id=node.id,
            detail=f"raster-tier transform det={det:.4f} must clear residual_matrix",
        )
    return None


def _check_t5_z_order(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    if node.type != NodeType.STACK or len(node.children) < 2:
        return None
    from figma_flutter_agent.parser.z_dag import ghost_occlusion_violations

    if ghost_occlusion_violations(node.children):
        return geometry_violation(
            code="inv_z",
            node_id=node.id,
            detail="presentational node paints above overlapping interactive",
        )
    return None


def _check_t5_repaint_z(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    if node.type != NodeType.STACK:
        return None
    static_runs: list[tuple[int, int, int, int]] = []
    run_start: int | None = None
    run_z_min = run_z_max = 0
    for index, child in enumerate(node.children):
        slot = child.layout_slot
        if slot is None:
            continue
        if slot.layer_class == LayerClass.STATIC:
            if run_start is None:
                run_start = index
                run_z_min = run_z_max = slot.z_index
            else:
                run_z_min = min(run_z_min, slot.z_index)
                run_z_max = max(run_z_max, slot.z_index)
            continue
        if run_start is not None:
            static_runs.append((run_start, index - 1, run_z_min, run_z_max))
            run_start = None
    if run_start is not None:
        static_runs.append((run_start, len(node.children) - 1, run_z_min, run_z_max))
    for start, end, z_min, z_max in static_runs:
        for child in node.children:
            slot = child.layout_slot
            if slot is None or slot.layer_class != LayerClass.INTERACTIVE:
                continue
            if z_min < slot.z_index < z_max:
                wrapped = any(
                    WrapKind.REPAINT_BOUNDARY
                    in (c.layout_slot.wraps if c.layout_slot else ())
                    for c in node.children[start : end + 1]
                )
                if not wrapped:
                    return geometry_violation(
                        code="t5_repaint_partition",
                        node_id=node.id,
                        detail="interactive z-index inside static run without RepaintBoundary",
                    )
    return None


def _check_constraint_normal(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    slot = node.layout_slot
    if slot is None:
        return None
    min_height = slot.min_height
    max_height = slot.max_height
    if (
        min_height is not None
        and max_height is not None
        and max_height < min_height
    ):
        return geometry_violation(
            code="constraint_normal",
            node_id=node.id,
            detail=(
                f"inverted height constraints min={min_height} max={max_height}"
            ),
        )
    return None


def validate_geometry_invariants(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
    layout_source: str | None = None,
    sidecar_skipped: bool = False,
    strict_invariants: bool = False,
) -> list[GeometryInvariantViolation]:
    """Validate translation-theory geometry invariants on a clean tree."""
    violations: list[GeometryInvariantViolation] = []
    has_layout_slots = False

    def visit(parent: CleanDesignTreeNode | None, node: CleanDesignTreeNode) -> None:
        nonlocal has_layout_slots
        if node.layout_slot is not None:
            has_layout_slots = True
        if require_layout_slots and node.layout_slot is None:
            violations.append(
                geometry_violation(
                    code="missing_layout_slot",
                    node_id=node.id,
                    detail="geometry planner did not attach layout_slot",
                )
            )
            return
        for check in (
            _check_t1_reproject,
            _check_t1_placement,
            _check_t2_flex_conservation,
            _check_t3_baseline,
            _check_t5_z_order,
            _check_t5_repaint_z,
            _check_inv_affine_det,
            _check_constraint_normal,
        ):
            item = check(node)
            if item is not None:
                violations.append(item)
        flex_axis = _check_inv_flex_axis(node, parent)
        if flex_axis is not None:
            violations.append(flex_axis)
        for child in node.children:
            visit(node, child)

    visit(None, root)
    if layout_source or has_layout_slots:
        from figma_flutter_agent.generator.geometry.emit_invariants import (
            validate_ast_coverage,
            validate_emit_geometry_invariants,
        )

        if layout_source:
            violations.extend(validate_emit_geometry_invariants(root, layout_source))
        violations.extend(
            validate_ast_coverage(
                root,
                layout_source or "",
                sidecar_skipped=sidecar_skipped,
                strict=strict_invariants,
            )
        )
    return violations


def assert_geometry_invariants_clean(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
    layout_source: str | None = None,
    strict_invariants: bool = False,
    hard_only: bool = True,
) -> None:
    """Raise when geometry invariant violations exist (hard-only by default)."""
    violations = validate_geometry_invariants(
        root,
        require_layout_slots=require_layout_slots,
        layout_source=layout_source,
        strict_invariants=strict_invariants,
    )
    if hard_only:
        hard, _ = partition_geometry_violations(violations)
        violations = hard
    if not violations:
        return
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in violations[:8])
    extra = len(violations) - 8
    suffix = f" (+{extra} more)" if extra > 0 else ""
    from figma_flutter_agent.errors import GenerationError

    raise GenerationError(f"Geometry invariant violations: {summary}{suffix}")
