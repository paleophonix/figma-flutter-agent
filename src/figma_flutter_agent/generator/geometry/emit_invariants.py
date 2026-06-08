"""Emit-level geometry invariant validation (RC-10)."""

from __future__ import annotations

import math
import re

from figma_flutter_agent.generator.figma_anchor import figma_key_token
from figma_flutter_agent.generator.geometry.affine import (
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
    Affine2,
    AxisPins,
    CleanDesignTreeNode,
    LayoutBackend,
    NodeType,
    SizingMode,
    WrapKind,
)

_TRANSLATE_IN_TRANSFORM = re.compile(r"\.\.translate\([^0][^)]*\)")
_ROTATE_ANGLE_RE = re.compile(r"Transform\.rotate\(angle:\s*([^,)]+)")
_TWO_PI = 2.0 * math.pi


def _walk_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []

    def visit(node: CleanDesignTreeNode) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return nodes


def _walk_with_parent(
    root: CleanDesignTreeNode,
) -> list[tuple[CleanDesignTreeNode | None, CleanDesignTreeNode]]:
    pairs: list[tuple[CleanDesignTreeNode | None, CleanDesignTreeNode]] = []

    def visit(parent: CleanDesignTreeNode | None, node: CleanDesignTreeNode) -> None:
        pairs.append((parent, node))
        for child in node.children:
            visit(node, child)

    visit(None, root)
    return pairs


def _snippet_for_node(source: str, node_id: str) -> str | None:
    token = figma_key_token(node_id)
    marker = f"ValueKey('{token}')"
    index = source.find(marker)
    if index < 0:
        return None
    start = max(0, source.rfind("Positioned(", 0, index))
    if start < 0:
        start = max(0, source.rfind("Expanded(", 0, index))
    if start < 0:
        start = max(0, source.rfind("SizedBox(", 0, index))
    end = source.find(marker, index) + len(marker) + 200
    return source[start:end]


def _parse_angle_literal(raw: str) -> float | None:
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _emit_reproject_residual(
    *,
    origin_x: float,
    origin_y: float,
    pins: AxisPins,
    residual: Affine2,
    intrinsic_width: float,
    intrinsic_height: float,
) -> float:
    """Max placement-origin error for stack ``Positioned`` pin law."""
    _ = intrinsic_width, intrinsic_height
    # Axis-aligned stack children emit ``Positioned`` from pins only; translation,
    # render-boundary bleed, and expand insets live in slot_rect / child content.
    if is_axis_aligned(residual):
        return 0.0
    # Rotated children anchor at pin origin (see ``_check_t1_placement``).
    errs: list[float] = []
    if pins.left is not None:
        errs.append(abs(origin_x - pins.left))
    if pins.top is not None:
        errs.append(abs(origin_y - pins.top))
    return max(errs) if errs else 0.0


def validate_emit_geometry_invariants(
    root: CleanDesignTreeNode,
    layout_source: str,
) -> list[GeometryInvariantViolation]:
    """Validate emitted Dart against geometry planner contracts."""
    violations: list[GeometryInvariantViolation] = []
    for parent, node in _walk_with_parent(root):
        slot = node.layout_slot
        if slot is None:
            continue
        snippet = _snippet_for_node(layout_source, node.id)
        if snippet is None:
            continue
        if slot.residual_matrix is not None and _TRANSLATE_IN_TRANSFORM.search(snippet):
            violations.append(
                geometry_violation(
                    code="inv_emit_no_translate",
                    node_id=node.id,
                    detail="planner emit must not use ..translate in Transform",
                )
            )
        if "rotateZ(" in snippet and slot.residual_matrix is not None:
            violations.append(
                geometry_violation(
                    code="inv_affine_det",
                    node_id=node.id,
                    detail="emit must use raw Matrix4 linear block, not rotateZ+scale",
                )
            )
        frame = node.geometry_frame
        local = slot.residual_matrix or (frame.local_transform if frame else None)
        if local is not None and requires_raster_tier(local) and "Matrix4(" in snippet:
            violations.append(
                geometry_violation(
                    code="inv_affine_det",
                    node_id=node.id,
                    detail="raster-tier transform must not emit Matrix4 linear block",
                )
            )
        if "Transform.rotate" in snippet:
            for match in _ROTATE_ANGLE_RE.finditer(snippet):
                angle = _parse_angle_literal(match.group(1))
                if angle is not None and abs(angle) > _TWO_PI + 0.01:
                    violations.append(
                        geometry_violation(
                            code="inv_unit",
                            node_id=node.id,
                            detail=f"Transform.rotate angle {angle} exceeds 2π radians",
                        )
                    )
        if parent is not None and WrapKind.EXPANDED in slot.wraps:
            if parent.type == NodeType.COLUMN and node.sizing.width_mode == SizingMode.FILL:
                if node.sizing.height_mode != SizingMode.FILL and "Expanded(" in snippet:
                    violations.append(
                        geometry_violation(
                            code="inv_flex_axis",
                            node_id=node.id,
                            detail="Column width FILL must not emit Expanded on cross axis",
                        )
                    )
            if parent.type == NodeType.ROW and node.sizing.height_mode == SizingMode.FILL:
                if node.sizing.width_mode != SizingMode.FILL and "Expanded(" in snippet:
                    violations.append(
                        geometry_violation(
                            code="inv_flex_axis",
                            node_id=node.id,
                            detail="Row height FILL must not emit Expanded on cross axis",
                        )
                    )
        if frame is not None and frame.placement_origin is not None:
            if slot.backend == LayoutBackend.STACK and not is_axis_aligned(
                slot.residual_matrix or frame.local_transform
            ):
                if "width:" in snippet and frame.intrinsic_size.width > 0:
                    aabb_w = frame.parsed_world_aabb.width if frame.parsed_world_aabb else 0
                    intrinsic_w = frame.intrinsic_size.width
                    if aabb_w > 0 and abs(aabb_w - intrinsic_w) > 1.0:
                        aabb_w_lit = format(aabb_w, ".1f")
                        if f"width: {aabb_w_lit}" in snippet:
                            violations.append(
                                geometry_violation(
                                    code="t1_placement_aabb_width",
                                    node_id=node.id,
                                    detail="rotated node must not use AABB width in Positioned",
                                )
                            )
        if frame is not None and frame.world_transform is not None and slot.positioned_pins:
            pins = slot.positioned_pins
            if pins is not None and frame.placement_origin is not None:
                intrinsic = frame.intrinsic_size
                residual = slot.residual_matrix or frame.local_transform
                origin = frame.placement_origin
                residual_err = _emit_reproject_residual(
                    origin_x=origin.x,
                    origin_y=origin.y,
                    pins=pins,
                    residual=residual,
                    intrinsic_width=intrinsic.width,
                    intrinsic_height=intrinsic.height,
                )
                if residual_err > geom_epsilon():
                    violations.append(
                        geometry_violation(
                            code="inv_reproject",
                            node_id=node.id,
                            detail=f"emit reproject residual {residual_err:.3f}px",
                        )
                    )
    return violations


def validate_ast_coverage(
    root: CleanDesignTreeNode,
    layout_source: str,
    *,
    sidecar_skipped: bool,
    strict: bool = False,
) -> list[GeometryInvariantViolation]:
    """INV-AST-COVERAGE: layout safety rules must not silently skip AST passes."""
    _ = layout_source
    if not sidecar_skipped:
        return []
    has_slots = any(n.layout_slot is not None for n in _walk_nodes(root))
    if not has_slots:
        return []
    return [
        geometry_violation(
            code="inv_ast_coverage",
            node_id=root.id,
            detail="oversized layout skipped AST sidecar while layout_slot present",
            strict=strict,
        )
    ]
