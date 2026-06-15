"""Formal activation criteria for IR layout passes (EPIC 4)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Literal

from figma_flutter_agent.generator.ir.passes.geometry import (
    _GAP_VARIANCE_TOLERANCE_PX,
    _HEIGHT_DELTA_TOLERANCE_PX,
    _OVERLAP_TOLERANCE_PX,
    child_layout_height,
    child_layout_width,
    child_layout_x,
    child_layout_y,
    compute_axis_gaps_sorted,
    compute_flex_gaps_paint_order,
    content_vertical_extent,
    horizontal_extent_delta,
    stack_children_overlap_on_x,
    stack_children_overlap_on_y,
    vertical_extent_delta,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

LayoutAxis = Literal["horizontal", "vertical"]
GapMode = Literal["uniform", "explicit"]


@dataclass(frozen=True)
class LayoutActivationDecision:
    """Outcome of a layout pass activation predicate."""

    activated: bool
    target_type: NodeType | None = None
    axis: LayoutAxis | None = None
    gap_mode: GapMode | None = None
    spacing: float = 0.0
    explicit_gaps: tuple[float, ...] = field(default_factory=tuple)
    reject_reason: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)


def stack_has_protected_archetype(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack encodes interaction chrome, not a false flex row."""
    from figma_flutter_agent.parser.interaction import (
        looks_like_back_nav_stack,
        looks_like_skip_control_stack,
        stack_interaction_kind,
    )
    from figma_flutter_agent.parser.semantics.signals.chip_anatomy import (
        is_static_segmented_number_row,
    )

    if is_static_segmented_number_row(node):
        return True
    if looks_like_back_nav_stack(node) or looks_like_skip_control_stack(node):
        return True
    return stack_interaction_kind(node) is not None


def _children_have_axis_layout(
    children: list[CleanDesignTreeNode],
    *,
    axis: LayoutAxis,
) -> bool:
    if len(children) < 2:
        return False
    for child in children:
        if axis == "horizontal":
            if child_layout_x(child) is None or child_layout_width(child) is None:
                return False
            continue
        if child_layout_y(child) is None or child_layout_height(child) is None:
            return False
    return True


def _child_ids(children: list[CleanDesignTreeNode]) -> list[str]:
    return [child.id for child in children]


def _axis_sorted_children(
    children: list[CleanDesignTreeNode],
    *,
    axis: LayoutAxis,
) -> list[CleanDesignTreeNode]:
    if axis == "horizontal":
        return sorted(
            children,
            key=lambda child: child_layout_x(child) if child_layout_x(child) is not None else 0.0,
        )
    return sorted(
        children,
        key=lambda child: child_layout_y(child) if child_layout_y(child) is not None else 0.0,
    )


def _paint_order_matches_axis_sorted(
    children: list[CleanDesignTreeNode],
    *,
    axis: LayoutAxis,
) -> bool:
    """Return True when Figma paint order already matches axis-sorted layout order."""
    return _child_ids(children) == _child_ids(_axis_sorted_children(children, axis=axis))


def _wrap_row_major_child_ids(children: list[CleanDesignTreeNode]) -> list[str]:
    """Flatten Y-clustered rows into row-major child id order."""
    rows = _cluster_rows(children)
    ordered: list[str] = []
    for row in rows:
        for child in _axis_sorted_children(row, axis="horizontal"):
            ordered.append(child.id)
    return ordered


def _paint_order_matches_wrap_row_major(children: list[CleanDesignTreeNode]) -> bool:
    """Return True when paint order matches row-major wrap traversal."""
    return _child_ids(children) == _wrap_row_major_child_ids(children)


def _monotonic_along_axis(
    children: list[CleanDesignTreeNode],
    *,
    axis: LayoutAxis,
) -> bool:
    if axis == "horizontal":
        ordered = _axis_sorted_children(children, axis="horizontal")
        for index in range(len(ordered) - 1):
            if stack_children_overlap_on_x(ordered[index], ordered[index + 1]):
                return False
            left_x = child_layout_x(ordered[index])
            left_w = child_layout_width(ordered[index])
            right_x = child_layout_x(ordered[index + 1])
            if left_x is None or left_w is None or right_x is None:
                return False
            if right_x - (left_x + left_w) < -_OVERLAP_TOLERANCE_PX:
                return False
        return True
    ordered = _axis_sorted_children(children, axis="vertical")
    for index in range(len(ordered) - 1):
        if stack_children_overlap_on_y(ordered[index], ordered[index + 1]):
            return False
        top_y = child_layout_y(ordered[index])
        top_h = child_layout_height(ordered[index])
        bottom_y = child_layout_y(ordered[index + 1])
        if top_y is None or top_h is None or bottom_y is None:
            return False
        if bottom_y - (top_y + top_h) < -_OVERLAP_TOLERANCE_PX:
            return False
    return True


def _cluster_rows(children: list[CleanDesignTreeNode]) -> list[list[CleanDesignTreeNode]]:
    clusters: list[list[CleanDesignTreeNode]] = []
    for child in children:
        child_y = child_layout_y(child)
        if child_y is None:
            return []
        placed = False
        for cluster in clusters:
            rep_y = child_layout_y(cluster[0])
            if rep_y is not None and abs(child_y - rep_y) <= _HEIGHT_DELTA_TOLERANCE_PX:
                cluster.append(child)
                placed = True
                break
        if not placed:
            clusters.append([child])
    clusters.sort(
        key=lambda row: child_layout_y(row[0]) if child_layout_y(row[0]) is not None else 0.0,
    )
    return clusters


def _wrap_row_cluster_decision(
    node: CleanDesignTreeNode,
    children: list[CleanDesignTreeNode],
) -> LayoutActivationDecision | None:
    rows = _cluster_rows(children)
    if len(rows) < 2:
        return None
    if not any(len(row) >= 2 for row in rows):
        return None
    for row in rows:
        if not _monotonic_along_axis(row, axis="horizontal"):
            return None
    row_tops = [child_layout_y(row[0]) for row in rows]
    row_bottoms: list[float] = []
    for row in rows:
        bottom = 0.0
        for child in row:
            child_y = child_layout_y(child)
            child_h = child_layout_height(child)
            if child_y is None or child_h is None:
                return None
            bottom = max(bottom, child_y + child_h)
        row_bottoms.append(bottom)
    inter_row_gaps: list[float] = []
    for index in range(len(rows) - 1):
        top_y = row_tops[index + 1]
        if top_y is None:
            return None
        inter_row_gaps.append(max(0.0, top_y - row_bottoms[index]))
    if not inter_row_gaps:
        return None
    if max(inter_row_gaps) - min(inter_row_gaps) > _GAP_VARIANCE_TOLERANCE_PX:
        return None
    if not _paint_order_matches_wrap_row_major(children):
        return None
    sorted_gaps = compute_axis_gaps_sorted(children, axis="horizontal")
    gap_mode, spacing, explicit = _resolve_gap_policy(
        children,
        axis="horizontal",
        sorted_gaps=sorted_gaps,
    )
    return LayoutActivationDecision(
        activated=True,
        target_type=NodeType.WRAP,
        axis="horizontal",
        gap_mode=gap_mode,
        spacing=spacing,
        explicit_gaps=explicit,
        evidence={"rows": len(rows), "inter_row_gaps": inter_row_gaps},
    )


def _resolve_gap_policy(
    children: list[CleanDesignTreeNode],
    *,
    axis: LayoutAxis,
    sorted_gaps: list[float],
) -> tuple[GapMode, float, tuple[float, ...]]:
    if not sorted_gaps:
        return "uniform", 0.0, tuple()
    if len(sorted_gaps) == 1:
        return "uniform", sorted_gaps[0], tuple()
    spread = max(sorted_gaps) - min(sorted_gaps)
    if spread <= _GAP_VARIANCE_TOLERANCE_PX:
        return "uniform", float(statistics.median(sorted_gaps)), tuple()
    paint_gaps = tuple(compute_flex_gaps_paint_order(children, axis=axis))
    return "explicit", 0.0, paint_gaps


def _evaluate_axis_candidate(
    node: CleanDesignTreeNode,
    *,
    axis: LayoutAxis,
) -> LayoutActivationDecision | None:
    children = node.children
    if not _children_have_axis_layout(children, axis=axis):
        return None
    cross_delta = (
        vertical_extent_delta(children)
        if axis == "horizontal"
        else horizontal_extent_delta(children)
    )
    if axis == "horizontal" and cross_delta > _HEIGHT_DELTA_TOLERANCE_PX:
        wrap_decision = _wrap_row_cluster_decision(node, children)
        if wrap_decision is not None:
            return wrap_decision
        return None
    if axis == "vertical" and cross_delta > _HEIGHT_DELTA_TOLERANCE_PX:
        return None
    if not _monotonic_along_axis(children, axis=axis):
        return None
    if not _paint_order_matches_axis_sorted(children, axis=axis):
        return None
    sorted_gaps = compute_axis_gaps_sorted(children, axis=axis)
    gap_mode, spacing, explicit = _resolve_gap_policy(children, axis=axis, sorted_gaps=sorted_gaps)
    target = NodeType.ROW if axis == "horizontal" else NodeType.COLUMN
    return LayoutActivationDecision(
        activated=True,
        target_type=target,
        axis=axis,
        gap_mode=gap_mode,
        spacing=spacing,
        explicit_gaps=explicit,
        evidence={
            "cross_delta": cross_delta,
            "gap_spread": max(sorted_gaps) - min(sorted_gaps) if sorted_gaps else 0.0,
        },
    )


def evaluate_stack_flex_candidate(node: CleanDesignTreeNode) -> LayoutActivationDecision:
    """Return whether a STACK may become ROW, COLUMN, or WRAP."""
    if node.type != NodeType.STACK or len(node.children) < 2:
        return LayoutActivationDecision(
            activated=False, reject_reason="not_stack_or_too_few_children"
        )
    if stack_has_protected_archetype(node):
        return LayoutActivationDecision(activated=False, reject_reason="protected_archetype")
    vertical = _evaluate_axis_candidate(node, axis="vertical")
    horizontal = _evaluate_axis_candidate(node, axis="horizontal")
    if (
        vertical is not None
        and horizontal is not None
        and horizontal.target_type == NodeType.WRAP
        and horizontal_extent_delta(node.children) <= _HEIGHT_DELTA_TOLERANCE_PX
    ):
        return vertical
    if horizontal is not None:
        return horizontal
    if vertical is not None:
        return vertical
    return LayoutActivationDecision(activated=False, reject_reason="no_axis_candidate")


def evaluate_scroll_host(
    root: CleanDesignTreeNode,
    *,
    artboard_height: float | None,
    fallback_threshold_px: int,
) -> LayoutActivationDecision:
    """Return whether the layout root should receive vertical scroll semantics."""
    extent = content_vertical_extent(root)
    if artboard_height is not None and artboard_height > 0:
        if extent > artboard_height + _OVERLAP_TOLERANCE_PX:
            return LayoutActivationDecision(
                activated=True,
                evidence={"extent": extent, "artboard_height": artboard_height},
            )
        return LayoutActivationDecision(
            activated=False,
            reject_reason="within_artboard",
            evidence={"extent": extent, "artboard_height": artboard_height},
        )
    if extent > float(fallback_threshold_px):
        return LayoutActivationDecision(
            activated=True,
            evidence={"extent": extent, "fallback_threshold_px": fallback_threshold_px},
        )
    return LayoutActivationDecision(
        activated=False,
        reject_reason="below_fallback_threshold",
        evidence={"extent": extent, "fallback_threshold_px": fallback_threshold_px},
    )
