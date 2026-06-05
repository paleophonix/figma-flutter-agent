"""Geometry planning pass: world cascade, slots, baseline and repaint (T1–T5)."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry_affine import (
    compose_affine,
    expand_aabb,
    linear_affine,
    requires_raster_tier,
    transform_point,
)
from figma_flutter_agent.generator.geometry_flex import compute_flex_deltas
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.parser.interaction import stack_interaction_kind
from figma_flutter_agent.parser.numeric_rounding import round_axis_prefix
from figma_flutter_agent.schemas import (
    Affine2,
    AxisPins,
    CleanDesignTreeNode,
    FlexSolution,
    GeomRect,
    LayerClass,
    LayoutBackend,
    LayoutSlotIr,
    NodeType,
    TextMetricsFrame,
    WrapKind,
)

_BASELINE_EPSILON = 0.5
_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
    }
)


def _leading_above_flutter(font_size: float, line_height_ratio: float | None) -> float:
    if line_height_ratio is None or line_height_ratio <= 0:
        return 0.0
    line_box = font_size * line_height_ratio
    metric_glyph = font_size * 0.72
    return max(0.0, (line_box - metric_glyph) * 0.5)


def _compute_delta_top(metrics: TextMetricsFrame) -> float | None:
    if metrics.glyph_top_offset is None or metrics.font_size is None:
        return None
    leading = _leading_above_flutter(metrics.font_size, metrics.strut_height_ratio)
    delta = metrics.glyph_top_offset - leading
    if abs(delta) <= _BASELINE_EPSILON:
        return None
    return delta


def _layer_class(node: CleanDesignTreeNode) -> LayerClass:
    if node.type in _INTERACTIVE_TYPES:
        return LayerClass.INTERACTIVE
    if stack_interaction_kind(node) == "button":
        return LayerClass.INTERACTIVE
    return LayerClass.STATIC


def _stack_pins_from_placement(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
) -> AxisPins | None:
    frame = node.geometry_frame
    placement = node.stack_placement
    if placement is None and frame is not None and frame.placement_aabb is not None:
        aabb = frame.placement_aabb
        placement_left = aabb.x
        placement_top = aabb.y
        placement_width = aabb.width
        placement_height = aabb.height
    elif placement is not None:
        placement_left = placement.left
        placement_top = placement.top
        placement_width = placement.width
        placement_height = placement.height
    elif frame is not None and frame.placement_origin is not None:
        origin = frame.placement_origin
        intrinsic = frame.intrinsic_size
        return AxisPins(
            free_horizontal="left",
            free_vertical="top",
            left=origin.x,
            top=origin.y,
            width=intrinsic.width if intrinsic.width > 0 else None,
            height=intrinsic.height if intrinsic.height > 0 else None,
        )
    else:
        return None

    free_h: str | None = "left"
    if placement is not None and placement.horizontal == "RIGHT":
        free_h = "right"
    elif placement is not None and (
        placement.horizontal in {"LEFT_RIGHT", "SCALE"}
        or placement.horizontal == "CENTER"
        and placement.width is not None
    ):
        free_h = "width"
    free_v: str | None = "top"
    if placement is not None and placement.vertical == "BOTTOM":
        free_v = "bottom"
    elif placement is not None and (
        placement.vertical in {"TOP_BOTTOM", "SCALE"}
        or placement.vertical == "CENTER"
        and placement.height is not None
    ):
        free_v = "height"
    _ = parent_type
    return AxisPins(
        free_horizontal=free_h,  # type: ignore[arg-type]
        free_vertical=free_v,  # type: ignore[arg-type]
        left=placement_left,
        top=placement_top,
        right=placement.right if placement else None,
        bottom=placement.bottom if placement else None,
        width=placement_width,
        height=placement_height,
    )


def _slot_rect(node: CleanDesignTreeNode) -> GeomRect:
    frame = node.geometry_frame
    if frame is not None:
        intrinsic = frame.intrinsic_size
        if intrinsic.width > 0 or intrinsic.height > 0:
            origin = frame.placement_aabb or frame.placement_origin
            return GeomRect(
                x=origin.x if origin is not None else 0.0,
                y=origin.y if origin is not None else 0.0,
                width=intrinsic.width,
                height=intrinsic.height,
            )
    placement = node.stack_placement
    if (
        placement is not None
        and placement.width is not None
        and placement.height is not None
    ):
        return GeomRect(
            x=placement.left,
            y=placement.top,
            width=placement.width,
            height=placement.height,
        )
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    return GeomRect(width=width, height=height)


def _resolve_backend(node: CleanDesignTreeNode, *, local: Affine2) -> LayoutBackend:
    if node.render_boundary:
        return LayoutBackend.BOUNDARY
    if node.scroll_axis != "none":
        return LayoutBackend.SCROLL
    if requires_raster_tier(local):
        return LayoutBackend.BOUNDARY
    if node.type in {NodeType.ROW, NodeType.COLUMN, NodeType.WRAP}:
        return LayoutBackend.FLEX
    return LayoutBackend.STACK


def _residual_matrix(local: Affine2) -> Affine2 | None:
    if requires_raster_tier(local):
        return None
    linear = linear_affine(local)
    from figma_flutter_agent.generator.geometry_affine import has_non_trivial_linear

    if not has_non_trivial_linear(linear):
        return None
    return linear


def _plan_node(
    node: CleanDesignTreeNode,
    *,
    parent_world: Affine2,
    parent_type: NodeType | None,
    z_index: int,
) -> CleanDesignTreeNode:
    local = node.geometry_frame.local_transform if node.geometry_frame else Affine2()
    world = compose_affine(parent_world, local)
    children: list[CleanDesignTreeNode] = []
    child_z = z_index
    for child in node.children:
        child_z += 1
        planned_child = _plan_node(
            child,
            parent_world=world,
            parent_type=node.type,
            z_index=child_z,
        )
        flex_wraps, input_metrics = compute_flex_deltas(node, planned_child)
        if flex_wraps or input_metrics is not None:
            child_slot = planned_child.layout_slot
            if child_slot is not None:
                merged_wraps = tuple(dict.fromkeys((*child_slot.wraps, *flex_wraps)))
                child_slot = child_slot.model_copy(update={"wraps": merged_wraps})
                text_metrics = planned_child.text_metrics_frame
                if input_metrics is not None:
                    text_metrics = input_metrics
                    merged_wraps = tuple(
                        w
                        for w in merged_wraps
                        if w != WrapKind.DELTA_TOP_PADDING
                    )
                    child_slot = child_slot.model_copy(update={"wraps": merged_wraps})
                planned_child = planned_child.model_copy(
                    update={
                        "layout_slot": child_slot,
                        "text_metrics_frame": text_metrics,
                    }
                )
        children.append(planned_child)

    geometry = node.geometry_frame
    if geometry is not None:
        intrinsic = geometry.intrinsic_size
        derived = expand_aabb(world, intrinsic.width, intrinsic.height)
        origin_x, origin_y = transform_point(local, 0.0, 0.0)
        geometry = geometry.model_copy(
            update={
                "world_transform": world,
                "placement_origin": GeomRect(x=origin_x, y=origin_y),
                "world_aabb": derived,
            }
        )

    text_metrics = node.text_metrics_frame
    wraps: list[WrapKind] = []
    if node.type == NodeType.INPUT:
        from figma_flutter_agent.generator.geometry_flex import compute_input_metrics

        input_metrics = compute_input_metrics(node)
        if input_metrics is not None:
            text_metrics = input_metrics
    elif text_metrics is not None:
        delta = _compute_delta_top(text_metrics)
        if delta is not None:
            text_metrics = text_metrics.model_copy(
                update={
                    "delta_top": delta,
                    "leading_above_flutter": _leading_above_flutter(
                        text_metrics.font_size or 0.0,
                        text_metrics.strut_height_ratio,
                    ),
                }
            )
            wraps.append(WrapKind.DELTA_TOP_PADDING)

    backend = _resolve_backend(node, local=local)
    flex_solution = None
    if backend == LayoutBackend.FLEX:
        flex_solution = FlexSolution(
            main_axis="vertical" if node.type == NodeType.COLUMN else "horizontal",
        )
    layout_slot = LayoutSlotIr(
        backend=backend,
        slot_rect=_slot_rect(node),
        positioned_pins=_stack_pins_from_placement(node, parent_type=parent_type),
        flex_solution=flex_solution,
        residual_matrix=_residual_matrix(local),
        layer_class=_layer_class(node),
        z_index=z_index,
        wraps=tuple(wraps),
    )
    return node.model_copy(
        update={
            "children": children,
            "geometry_frame": geometry,
            "text_metrics_frame": text_metrics,
            "layout_slot": layout_slot,
        }
    )


def _apply_repaint_rle(root: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """RLE static runs under stack parents (T5)."""

    def visit(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [visit(child) for child in node.children]
        working = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK or not children:
            return working
        updated: list[CleanDesignTreeNode] = []
        run_start: int | None = None
        for index, child in enumerate(children):
            slot = child.layout_slot
            is_static = slot is not None and slot.layer_class == LayerClass.STATIC
            if is_static:
                if run_start is None:
                    run_start = index
                updated.append(child)
                continue
            if run_start is not None:
                for run_index in range(run_start, index):
                    run_child = updated[run_index]
                    run_slot = run_child.layout_slot
                    if run_slot is None:
                        continue
                    run_wraps = tuple(
                        dict.fromkeys((*run_slot.wraps, WrapKind.REPAINT_BOUNDARY))
                    )
                    updated[run_index] = run_child.model_copy(
                        update={
                            "layout_slot": run_slot.model_copy(update={"wraps": run_wraps}),
                        }
                    )
                run_start = None
            updated.append(child)
        if run_start is not None:
            for run_index in range(run_start, len(updated)):
                run_child = updated[run_index]
                run_slot = run_child.layout_slot
                if run_slot is None:
                    continue
                run_wraps = tuple(
                    dict.fromkeys((*run_slot.wraps, WrapKind.REPAINT_BOUNDARY))
                )
                updated[run_index] = run_child.model_copy(
                    update={"layout_slot": run_slot.model_copy(update={"wraps": run_wraps})}
                )
        return working.model_copy(update={"children": updated})

    return visit(root)


def plan_geometry_tree(tree: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Run geometry planning passes and attach ``layout_slot`` on every node."""
    working = deep_copy_clean_tree(tree)
    root_world = Affine2()
    planned = _plan_node(
        working,
        parent_world=root_world,
        parent_type=None,
        z_index=0,
    )
    return _apply_repaint_rle(planned)


def extent_conservation_error(
    parent_span: float, child_spans: list[float], *, gap: float = 0.0
) -> float:
    """Return absolute residual for T2 extent conservation check."""
    if not child_spans:
        return 0.0
    positions = [0.0]
    cursor = 0.0
    for index, span in enumerate(child_spans):
        if index > 0:
            cursor += gap
        cursor += span
        positions.append(cursor)
    if abs(positions[-1] - parent_span) > 1e-6:
        positions.append(parent_span)
    rounded = round_axis_prefix(positions)
    child_total = rounded[len(child_spans)] - rounded[0]
    from figma_flutter_agent.parser.numeric_rounding import round_geometry

    parent_rounded = round_geometry(parent_span) or parent_span
    return abs(parent_rounded - child_total)
