"""Geometry planning pass: world cascade, slots, baseline and repaint (T1–T5)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.cascade_context import cascade_context_from_node
from figma_flutter_agent.generator.geometry.affine import (
    compose_affine,
    expand_aabb,
    has_non_trivial_linear,
    linear_affine,
    requires_raster_tier,
    transform_point,
)
from figma_flutter_agent.generator.geometry.flex import compute_flex_deltas
from figma_flutter_agent.generator.geometry.repaint import apply_repaint_rle
from figma_flutter_agent.generator.geometry.slots import (
    layer_class,
    resolve_backend,
    slot_rect,
    stack_pins_from_placement,
)
from figma_flutter_agent.generator.geometry.text_metrics import (
    compute_delta_top,
    leading_above_flutter,
)
from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree
from figma_flutter_agent.parser.numeric_rounding import round_axis_prefix
from figma_flutter_agent.schemas import (
    Affine2,
    CleanDesignTreeNode,
    FlexSolution,
    GeomRect,
    HeightFit,
    LayerClass,
    LayoutBackend,
    LayoutSlotIr,
    NodeType,
    WrapKind,
)

def _residual_matrix(local: Affine2) -> Affine2 | None:
    if requires_raster_tier(local):
        return None
    linear = linear_affine(local)
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
    cascade = cascade_context_from_node(node, parent_world=parent_world)
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
        if cascade is not None:
            origin_x, origin_y = cascade.pivot_x, cascade.pivot_y
        else:
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
        from figma_flutter_agent.generator.geometry.flex import compute_input_metrics

        input_metrics = compute_input_metrics(node)
        if input_metrics is not None:
            text_metrics = input_metrics
    elif text_metrics is not None:
        glyph = (node.text or "").strip()
        skip_delta = (
            node.type == NodeType.TEXT
            and (node.style.text_align or "").upper() == "CENTER"
            and 0 < len(glyph) <= 3
        )
        if not skip_delta:
            delta = compute_delta_top(text_metrics)
            if delta is not None:
                text_metrics = text_metrics.model_copy(
                    update={
                        "delta_top": delta,
                        "leading_above_flutter": leading_above_flutter(
                            text_metrics.font_size or 0.0,
                            text_metrics.strut_height_ratio,
                        ),
                    }
                )
                wraps.append(WrapKind.DELTA_TOP_PADDING)

    backend = resolve_backend(node, local=local)
    flex_solution = None
    if backend == LayoutBackend.FLEX:
        flex_solution = FlexSolution(
            main_axis="vertical" if node.type == NodeType.COLUMN else "horizontal",
        )
    min_height: float | None = None
    max_height: float | None = None
    height_fit: HeightFit | None = None
    if node.type == NodeType.INPUT:
        from figma_flutter_agent.generator.geometry.flex import min_input_height
        from figma_flutter_agent.parser.interaction import looks_like_checkbox_control

        if not looks_like_checkbox_control(node):
            min_height = min_input_height(node.sizing.height)
            height_fit = HeightFit.MIN
            frame_h = node.sizing.height
            if frame_h is not None and frame_h > 0 and min_height > frame_h:
                max_height = None
            elif frame_h is not None and frame_h > 0:
                max_height = float(frame_h)
    layout_slot = LayoutSlotIr(
        backend=backend,
        slot_rect=slot_rect(node),
        positioned_pins=stack_pins_from_placement(node, parent_type=parent_type),
        flex_solution=flex_solution,
        residual_matrix=_residual_matrix(local),
        layer_class=layer_class(node),
        z_index=z_index,
        wraps=tuple(wraps),
        min_height=min_height,
        max_height=max_height,
        height_fit=height_fit,
    )
    return node.model_copy(
        update={
            "children": children,
            "geometry_frame": geometry,
            "text_metrics_frame": text_metrics,
            "layout_slot": layout_slot,
        }
    )


def plan_geometry_tree(
    tree: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
) -> CleanDesignTreeNode:
    """Run geometry planning passes and attach ``layout_slot`` on every node."""
    from figma_flutter_agent.generator.geometry.baseline import seed_baseline_oracle

    seed_baseline_oracle(tree, project_dir=project_dir)
    working = deep_copy_clean_tree(tree)
    root_world = Affine2()
    planned = _plan_node(
        working,
        parent_world=root_world,
        parent_type=None,
        z_index=0,
    )
    return apply_repaint_rle(planned)


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
