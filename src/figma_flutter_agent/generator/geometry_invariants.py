"""Geometry invariant validation for translation theory (T1–T5)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.geometry_affine import aabb_residual, expand_aabb, geom_epsilon
from figma_flutter_agent.generator.geometry_planner import extent_conservation_error
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    LayerClass,
    NodeType,
    TextMetricsFrame,
    WrapKind,
)

_BASELINE_EPSILON = 0.5


@dataclass(frozen=True)
class GeometryInvariantViolation:
    """One failed geometry theorem check."""

    code: str
    node_id: str
    detail: str


def _walk_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []

    def visit(node: CleanDesignTreeNode) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return nodes


def _check_t1_reproject(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    frame = node.geometry_frame
    if frame is None or frame.world_transform is None:
        return None
    derived = expand_aabb(
        frame.world_transform,
        frame.layout_rect.width,
        frame.layout_rect.height,
    )
    residual = aabb_residual(frame.world_aabb, derived)
    if residual <= geom_epsilon():
        return None
    return GeometryInvariantViolation(
        code="t1_reproject",
        node_id=node.id,
        detail=f"world AABB residual {residual:.3f}px > {geom_epsilon()}",
    )


def _check_t2_stack_conservation(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    if node.type != NodeType.STACK or not node.children:
        return None
    parent_width = node.sizing.width or node.geometry_frame.layout_rect.width if node.geometry_frame else None
    if parent_width is None or parent_width <= 0:
        return None
    spans: list[float] = []
    for child in node.children:
        slot = child.layout_slot
        if slot is None:
            continue
        spans.append(slot.slot_rect.width)
    if not spans:
        return None
    residual = extent_conservation_error(parent_width, spans, gap=node.spacing)
    if residual <= 0.5:
        return None
    return GeometryInvariantViolation(
        code="t2_extent_conservation",
        node_id=node.id,
        detail=f"horizontal extent residual {residual:.3f}px > 0.5",
    )


def _check_t3_baseline(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    metrics = node.text_metrics_frame
    if metrics is None or metrics.delta_top is None:
        return None
    if abs(metrics.delta_top) <= _BASELINE_EPSILON:
        return None
    slot = node.layout_slot
    if slot is not None and WrapKind.DELTA_TOP_PADDING in slot.wraps:
        return None
    return GeometryInvariantViolation(
        code="t3_baseline_delta",
        node_id=node.id,
        detail=f"delta_top={metrics.delta_top:.3f} without delta_top_padding wrap",
    )


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
                    WrapKind.REPAINT_BOUNDARY in (c.layout_slot.wraps if c.layout_slot else ())
                    for c in node.children[start : end + 1]
                )
                if not wrapped:
                    return GeometryInvariantViolation(
                        code="t5_repaint_partition",
                        node_id=node.id,
                        detail="interactive z-index inside static run without RepaintBoundary",
                    )
    return None


def validate_geometry_invariants(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
) -> list[GeometryInvariantViolation]:
    """Validate translation-theory geometry invariants on a clean tree."""
    violations: list[GeometryInvariantViolation] = []
    for node in _walk_nodes(root):
        if require_layout_slots and node.layout_slot is None:
            violations.append(
                GeometryInvariantViolation(
                    code="missing_layout_slot",
                    node_id=node.id,
                    detail="geometry planner did not attach layout_slot",
                )
            )
            continue
        for check in (
            _check_t1_reproject,
            _check_t2_stack_conservation,
            _check_t3_baseline,
            _check_t5_repaint_z,
        ):
            item = check(node)
            if item is not None:
                violations.append(item)
    return violations


def assert_geometry_invariants_clean(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
) -> None:
    """Raise when any geometry invariant is violated."""
    violations = validate_geometry_invariants(
        root,
        require_layout_slots=require_layout_slots,
    )
    if not violations:
        return
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in violations[:8])
    extra = len(violations) - 8
    suffix = f" (+{extra} more)" if extra > 0 else ""
    from figma_flutter_agent.errors import GenerationError

    raise GenerationError(f"Geometry invariant violations: {summary}{suffix}")
