"""Emit-level geometry invariant validation (RC-10)."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.figma_anchor import figma_key_token
from figma_flutter_agent.generator.geometry_affine import is_axis_aligned
from figma_flutter_agent.generator.geometry_invariants import GeometryInvariantViolation
from figma_flutter_agent.schemas import CleanDesignTreeNode, LayoutBackend

_TRANSLATE_IN_TRANSFORM = re.compile(r"\.\.translate\([^0][^)]*\)")


def _walk_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []

    def visit(node: CleanDesignTreeNode) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return nodes


def _snippet_for_node(source: str, node_id: str) -> str | None:
    token = figma_key_token(node_id)
    marker = f"ValueKey('{token}')"
    index = source.find(marker)
    if index < 0:
        return None
    start = max(0, source.rfind("Positioned(", 0, index))
    if start < 0:
        start = max(0, source.rfind("Expanded(", 0, index))
    end = source.find(marker, index) + len(marker) + 200
    return source[start:end]


def validate_emit_geometry_invariants(
    root: CleanDesignTreeNode,
    layout_source: str,
) -> list[GeometryInvariantViolation]:
    """Validate emitted Dart against geometry planner contracts."""
    violations: list[GeometryInvariantViolation] = []
    for node in _walk_nodes(root):
        slot = node.layout_slot
        if slot is None:
            continue
        snippet = _snippet_for_node(layout_source, node.id)
        if snippet is None:
            continue
        if slot.residual_matrix is not None and _TRANSLATE_IN_TRANSFORM.search(snippet):
            violations.append(
                GeometryInvariantViolation(
                    code="t1_emit_no_translate",
                    node_id=node.id,
                    detail="planner emit must not use ..translate in Transform",
                )
            )
        if "rotateZ(" in snippet and slot.residual_matrix is not None:
            violations.append(
                GeometryInvariantViolation(
                    code="t4_det_no_polar_decompose",
                    node_id=node.id,
                    detail="emit must use raw Matrix4 linear block, not rotateZ+scale",
                )
            )
        frame = node.geometry_frame
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
                                GeometryInvariantViolation(
                                    code="t1_placement_aabb_width",
                                    node_id=node.id,
                                    detail="rotated node must not use AABB width in Positioned",
                                )
                            )
    return violations
