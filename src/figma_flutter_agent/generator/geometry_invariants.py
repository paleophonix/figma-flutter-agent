"""Geometry invariant validation for translation theory (T1–T5)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.geometry_affine import (
    aabb_residual,
    expand_aabb,
    geom_epsilon,
    is_axis_aligned,
)
from figma_flutter_agent.generator.geometry_planner import extent_conservation_error
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    LayerClass,
    LayoutBackend,
    NodeType,
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
    intrinsic = frame.intrinsic_size
    derived = expand_aabb(frame.world_transform, intrinsic.width, intrinsic.height)
    reference = frame.parsed_world_aabb or frame.world_aabb
    residual = aabb_residual(reference, derived)
    if residual <= geom_epsilon():
        return None
    return GeometryInvariantViolation(
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
        return GeometryInvariantViolation(
            code="t1_placement_origin",
            node_id=node.id,
            detail="Positioned origin must match placement_origin for rotated nodes",
        )
    return None


def _check_t2_flex_conservation(
    node: CleanDesignTreeNode,
) -> GeometryInvariantViolation | None:
    slot = node.layout_slot
    if slot is None or slot.backend != LayoutBackend.FLEX:
        return None
    if node.type not in {NodeType.ROW, NodeType.COLUMN} or not node.children:
        return None
    if node.type == NodeType.ROW:
        parent_span = node.sizing.width or node.geometry_frame.intrinsic_size.width if node.geometry_frame else None
        child_spans = [child.layout_slot.slot_rect.width for child in node.children if child.layout_slot]
    else:
        parent_span = node.sizing.height or node.geometry_frame.intrinsic_size.height if node.geometry_frame else None
        child_spans = [child.layout_slot.slot_rect.height for child in node.children if child.layout_slot]
    if parent_span is None or parent_span <= 0 or not child_spans:
        return None
    residual = extent_conservation_error(parent_span, child_spans, gap=node.spacing)
    if residual <= 0.5:
        return None
    return GeometryInvariantViolation(
        code="t2_flex_conservation",
        node_id=node.id,
        detail=f"flex extent residual {residual:.3f}px > 0.5",
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
    return GeometryInvariantViolation(
        code="t3_baseline_delta",
        node_id=node.id,
        detail=f"delta_top={metrics.delta_top:.3f} without padding channel",
    )


def _check_t5_z_order(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    if node.type != NodeType.STACK or len(node.children) < 2:
        return None
    from figma_flutter_agent.parser.overlap_sweep import sibling_overlap_pairs
    from figma_flutter_agent.parser.z_bands import _is_interactive, _is_presentational

    pairs = sibling_overlap_pairs(node.children)
    order = {child.id: index for index, child in enumerate(node.children)}
    for pair in pairs:
        first = next((c for c in node.children if c.id == pair.first_id), None)
        second = next((c for c in node.children if c.id == pair.second_id), None)
        if first is None or second is None:
            continue
        for decor, interactive in ((first, second), (second, first)):
            if not _is_presentational(decor) or not _is_interactive(interactive):
                continue
            if order.get(decor.id, 0) > order.get(interactive.id, 0):
                return GeometryInvariantViolation(
                    code="t5_z_order",
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
    layout_source: str | None = None,
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
            _check_t1_placement,
            _check_t2_flex_conservation,
            _check_t3_baseline,
            _check_t5_z_order,
            _check_t5_repaint_z,
        ):
            item = check(node)
            if item is not None:
                violations.append(item)
    if layout_source:
        from figma_flutter_agent.generator.geometry_emit_invariants import (
            validate_emit_geometry_invariants,
        )

        violations.extend(validate_emit_geometry_invariants(root, layout_source))
    return violations


def assert_geometry_invariants_clean(
    root: CleanDesignTreeNode,
    *,
    require_layout_slots: bool = False,
    layout_source: str | None = None,
) -> None:
    """Raise when any geometry invariant is violated."""
    violations = validate_geometry_invariants(
        root,
        require_layout_slots=require_layout_slots,
        layout_source=layout_source,
    )
    if not violations:
        return
    summary = "; ".join(f"{v.code}@{v.node_id}" for v in violations[:8])
    extra = len(violations) - 8
    suffix = f" (+{extra} more)" if extra > 0 else ""
    from figma_flutter_agent.errors import GenerationError

    raise GenerationError(f"Geometry invariant violations: {summary}{suffix}")
