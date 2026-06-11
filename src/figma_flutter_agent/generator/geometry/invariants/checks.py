"""Individual T1-T5 geometry invariant checks."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.affine import (
    aabb_residual,
    affine_det,
    expand_aabb,
    geom_epsilon,
    is_axis_aligned,
    requires_raster_tier,
)
from figma_flutter_agent.generator.geometry.invariants.models import (
    GeometryInvariantViolation,
    geometry_violation,
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
_T2_ARTBOARD_DRIFT_HARD_PX = 16.0

_FLOW_PANEL_TYPES = frozenset(
    {
        NodeType.ROW,
        NodeType.COLUMN,
        NodeType.STACK,
        NodeType.CONTAINER,
        NodeType.CARD,
        NodeType.BUTTON,
    }
)


def _check_t1_reproject(node: CleanDesignTreeNode) -> GeometryInvariantViolation | None:
    """Verify world cascade reprojection in tree space (not Figma document space)."""
    frame = node.geometry_frame
    if frame is None or frame.world_transform is None:
        return None
    intrinsic = frame.intrinsic_size
    if intrinsic.width <= geom_epsilon() and intrinsic.height <= geom_epsilon():
        return None
    derived = expand_aabb(frame.world_transform, intrinsic.width, intrinsic.height)
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


def _bounded_slot_inner_span(node: CleanDesignTreeNode) -> float | None:
    """Return the vertical span available inside a bounded positioned host."""
    height: float | None = None
    if node.stack_placement is not None and node.stack_placement.height is not None:
        height = float(node.stack_placement.height)
    if (height is None or height <= 0) and node.sizing.height is not None:
        height = float(node.sizing.height)
    if height is None or height <= 0:
        return None
    padding = node.padding
    vertical_pad = float(padding.top or 0.0) + float(padding.bottom or 0.0)
    return max(0.0, height - vertical_pad)


def _child_vertical_extent(child: CleanDesignTreeNode) -> float | None:
    """Predict a flow child's vertical extent including typography slack."""
    from figma_flutter_agent.generator.geometry.text_metrics import predict_typography_slack
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_bounded_slot_should_grow,
    )
    from figma_flutter_agent.parser.interaction import (
        button_should_flow_as_column,
        host_prefers_intrinsic_extent,
    )

    height: float | None = None
    slot = child.layout_slot
    if slot is not None and slot.slot_rect.height > 0:
        height = float(slot.slot_rect.height)
    if (height is None or height <= 0) and child.sizing.height is not None:
        height = float(child.sizing.height)
    if height is None or height <= 0:
        return None
    base = height + predict_typography_slack(child)
    if (
        column_bounded_slot_should_grow(child)
        or host_prefers_intrinsic_extent(child)
        or button_should_flow_as_column(child)
        or child.type == NodeType.STACK
    ):
        grown = _predict_vertical_flow_extent(child)
        if grown is not None:
            return max(base, grown)
    return base


def _predict_vertical_flow_extent(node: CleanDesignTreeNode) -> float | None:
    """Sum vertical flow children, spacing, and host padding."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_ordinal_bottom,
        stack_child_ordinal_top,
        stack_should_flow_as_column,
    )
    from figma_flutter_agent.parser.interaction import button_should_flow_as_column

    if node.type == NodeType.STACK:
        if not stack_should_flow_as_column(node):
            return None
        ordered = sorted(
            node.children,
            key=lambda child: (stack_child_ordinal_top(child), child.id),
        )
        if not ordered:
            return None
        total = 0.0
        previous: CleanDesignTreeNode | None = None
        for child in ordered:
            if previous is not None:
                gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(previous)
                if gap > 0.5:
                    total += gap
            extent = _child_vertical_extent(child)
            if extent is None:
                return None
            total += extent
            previous = child
        return total
    if node.type == NodeType.BUTTON and not button_should_flow_as_column(node):
        return None
    if node.type not in {NodeType.COLUMN, NodeType.BUTTON, NodeType.CARD}:
        return None
    panels = [child for child in node.children if child.type in _FLOW_PANEL_TYPES]
    if len(panels) < 1:
        return None
    extents: list[float] = []
    for child in panels:
        extent = _child_vertical_extent(child)
        if extent is None:
            if node.type == NodeType.BUTTON and button_should_flow_as_column(node):
                continue
            return None
        extents.append(extent)
    if not extents:
        return None
    gap_total = float(node.spacing or 0.0) * max(0, len(extents) - 1)
    padding = node.padding
    vertical_pad = float(padding.top or 0.0) + float(padding.bottom or 0.0)
    return sum(extents) + gap_total + vertical_pad


def _check_t2_bounded_slot_conservation(
    node: CleanDesignTreeNode,
) -> GeometryInvariantViolation | None:
    """Fail when predicted vertical flow exceeds a bounded positioned slot."""
    from figma_flutter_agent.generator.layout.flex_policy.column import (
        column_bounded_slot_should_grow,
    )

    if node.stack_placement is None and (node.sizing.height is None or node.sizing.height <= 0):
        return None
    if column_bounded_slot_should_grow(node):
        return None
    slot_span = _bounded_slot_inner_span(node)
    predicted = _predict_vertical_flow_extent(node)
    if slot_span is None or predicted is None:
        return None
    overflow = predicted - slot_span
    if overflow <= _T2_OVERFLOW_TOLERANCE:
        return None
    return geometry_violation(
        code="t2_bounded_slot_conservation",
        node_id=node.id,
        detail=f"bounded slot overflow {overflow:.3f}px > {_T2_OVERFLOW_TOLERANCE}",
    )


def _stack_child_bottom_ordinal(child: CleanDesignTreeNode) -> float:
    """Return a positioned child's bottom edge in stack coordinates."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_ordinal_bottom,
        stack_child_ordinal_top,
    )

    top = stack_child_ordinal_top(child)
    predicted = _predict_vertical_flow_extent(child)
    if predicted is not None and child.stack_placement is not None:
        return top + predicted
    return stack_child_ordinal_bottom(child)


def _check_t2_artboard_extent_drift(
    root: CleanDesignTreeNode,
) -> GeometryInvariantViolation | None:
    """Warn when grown intrinsic content exceeds the artboard height."""
    artboard_height = root.sizing.height
    if artboard_height is None or artboard_height <= 0:
        return None
    if root.type != NodeType.STACK:
        return None
    max_bottom = 0.0
    for child in root.children:
        if child.stack_placement is None:
            continue
        bottom = _stack_child_bottom_ordinal(child)
        max_bottom = max(max_bottom, bottom)
    drift = max_bottom - float(artboard_height)
    if drift <= _T2_OVERFLOW_TOLERANCE:
        return None
    severity_detail = f"artboard drift {drift:.3f}px"
    if drift > _T2_ARTBOARD_DRIFT_HARD_PX:
        return geometry_violation(
            code="t2_artboard_extent_drift",
            node_id=root.id,
            detail=f"{severity_detail} > {_T2_ARTBOARD_DRIFT_HARD_PX}",
        )
    return geometry_violation(
        code="t2_artboard_extent_drift",
        node_id=root.id,
        detail=severity_detail,
    )


def check_post_tree_invariants(
    root: CleanDesignTreeNode,
) -> list[GeometryInvariantViolation]:
    """Run checks that require the full tree root context."""
    item = _check_t2_artboard_extent_drift(root)
    return [item] if item is not None else []


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
                    WrapKind.REPAINT_BOUNDARY in (c.layout_slot.wraps if c.layout_slot else ())
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
    if min_height is not None and max_height is not None and max_height < min_height:
        return geometry_violation(
            code="constraint_normal",
            node_id=node.id,
            detail=f"inverted height constraints min={min_height} max={max_height}",
        )
    return None


NODE_CHECKS = (
    _check_t1_reproject,
    _check_t1_placement,
    _check_t2_flex_conservation,
    _check_t2_bounded_slot_conservation,
    _check_t3_baseline,
    _check_t5_z_order,
    _check_t5_repaint_z,
    _check_inv_affine_det,
    _check_constraint_normal,
)
