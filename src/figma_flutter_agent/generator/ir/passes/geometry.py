"""Geometry helpers for IR layout passes."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, StackPlacement

_OVERLAP_TOLERANCE_PX = 0.5
_GAP_VARIANCE_TOLERANCE_PX = 0.5
_HEIGHT_DELTA_TOLERANCE_PX = 1.0


def child_layout_x(node: CleanDesignTreeNode) -> float | None:
    """Return the child x offset within its parent stack, if known."""
    frame = node.geometry_frame
    if frame is not None and frame.layout_rect.width > 0:
        return float(frame.layout_rect.x)
    placement = node.stack_placement
    if placement is not None:
        return float(placement.left)
    if node.offset_x:
        return float(node.offset_x)
    return None


def child_layout_y(node: CleanDesignTreeNode) -> float | None:
    """Return the child y offset within its parent stack, if known."""
    frame = node.geometry_frame
    if frame is not None and frame.layout_rect.height > 0:
        return float(frame.layout_rect.y)
    placement = node.stack_placement
    if placement is not None:
        return float(placement.top)
    if node.offset_y:
        return float(node.offset_y)
    return None


def child_layout_width(node: CleanDesignTreeNode) -> float | None:
    """Return the laid-out width of a stack child."""
    placement = node.stack_placement
    if placement is not None and placement.width is not None and placement.width > 0:
        return float(placement.width)
    if node.sizing.width is not None and node.sizing.width > 0:
        return float(node.sizing.width)
    frame = node.geometry_frame
    if frame is not None and frame.layout_rect.width > 0:
        return float(frame.layout_rect.width)
    return None


def child_layout_height(node: CleanDesignTreeNode) -> float | None:
    """Return the laid-out height of a stack child."""
    placement = node.stack_placement
    if placement is not None and placement.height is not None and placement.height > 0:
        return float(placement.height)
    if node.sizing.height is not None and node.sizing.height > 0:
        return float(node.sizing.height)
    frame = node.geometry_frame
    if frame is not None and frame.layout_rect.height > 0:
        return float(frame.layout_rect.height)
    return None


def stack_children_overlap_on_y(
    top: CleanDesignTreeNode,
    bottom: CleanDesignTreeNode,
) -> bool:
    """Return True when two siblings overlap on the vertical axis."""
    top_y = child_layout_y(top)
    bottom_y = child_layout_y(bottom)
    top_h = child_layout_height(top)
    bottom_h = child_layout_height(bottom)
    if top_y is None or bottom_y is None or top_h is None or bottom_h is None:
        return True
    top_end = top_y + top_h
    overlap = min(top_end, bottom_y + bottom_h) - max(top_y, bottom_y)
    return overlap > _OVERLAP_TOLERANCE_PX


def stack_children_overlap_on_x(
    left: CleanDesignTreeNode,
    right: CleanDesignTreeNode,
) -> bool:
    """Return True when two siblings overlap on the horizontal axis."""
    left_x = child_layout_x(left)
    right_x = child_layout_x(right)
    left_w = child_layout_width(left)
    right_w = child_layout_width(right)
    if left_x is None or right_x is None or left_w is None or right_w is None:
        return True
    left_end = left_x + left_w
    overlap = min(left_end, right_x + right_w) - max(left_x, right_x)
    return overlap > _OVERLAP_TOLERANCE_PX


def horizontal_extent_delta(children: list[CleanDesignTreeNode]) -> float:
    """Return horizontal spread of child left edges for a vertical column candidate."""
    lefts = [child_layout_x(child) for child in children]
    if any(value is None for value in lefts):
        return float("inf")
    left_values = [float(value) for value in lefts if value is not None]
    if not left_values:
        return float("inf")
    return max(left_values) - min(left_values)


def vertical_extent_delta(children: list[CleanDesignTreeNode]) -> float:
    """Return vertical spread of child tops for a horizontal row candidate."""
    tops = [child_layout_y(child) for child in children]
    if any(value is None for value in tops):
        return float("inf")
    top_values = [float(value) for value in tops if value is not None]
    if not top_values:
        return float("inf")
    return max(top_values) - min(top_values)


def compute_axis_gaps_sorted(
    children: list[CleanDesignTreeNode],
    *,
    axis: str,
) -> list[float]:
    """Compute gaps between consecutive children sorted along ``axis``."""
    if len(children) < 2:
        return []
    if axis == "horizontal":
        ordered = sorted(
            children,
            key=lambda child: child_layout_x(child) if child_layout_x(child) is not None else 0.0,
        )
        gaps: list[float] = []
        for index in range(len(ordered) - 1):
            current = ordered[index]
            nxt = ordered[index + 1]
            current_x = child_layout_x(current)
            next_x = child_layout_x(nxt)
            current_w = child_layout_width(current)
            if current_x is None or next_x is None or current_w is None:
                continue
            gap = next_x - current_x - current_w
            if gap >= -_OVERLAP_TOLERANCE_PX:
                gaps.append(max(0.0, gap))
        return gaps
    ordered = sorted(
        children,
        key=lambda child: child_layout_y(child) if child_layout_y(child) is not None else 0.0,
    )
    gaps = []
    for index in range(len(ordered) - 1):
        current = ordered[index]
        nxt = ordered[index + 1]
        current_y = child_layout_y(current)
        next_y = child_layout_y(nxt)
        current_h = child_layout_height(current)
        if current_y is None or next_y is None or current_h is None:
            continue
        gap = next_y - current_y - current_h
        if gap >= -_OVERLAP_TOLERANCE_PX:
            gaps.append(max(0.0, gap))
    return gaps


def compute_flex_gaps_paint_order(
    children: list[CleanDesignTreeNode],
    *,
    axis: str,
) -> list[float]:
    """Compute gaps between paint-order siblings along the main axis."""
    if len(children) < 2:
        return []
    gaps: list[float] = []
    for index in range(len(children) - 1):
        current = children[index]
        nxt = children[index + 1]
        if axis == "horizontal":
            current_x = child_layout_x(current)
            next_x = child_layout_x(nxt)
            current_w = child_layout_width(current)
            if current_x is None or next_x is None or current_w is None:
                gaps.append(0.0)
                continue
            gaps.append(max(0.0, next_x - current_x - current_w))
            continue
        current_y = child_layout_y(current)
        next_y = child_layout_y(nxt)
        current_h = child_layout_height(current)
        if current_y is None or next_y is None or current_h is None:
            gaps.append(0.0)
            continue
        gaps.append(max(0.0, next_y - current_y - current_h))
    return gaps


def compute_flex_spacing(children: list[CleanDesignTreeNode]) -> float | None:
    """Compute average horizontal gap between sorted stack children."""
    if len(children) < 2:
        return None
    ordered = sorted(
        children,
        key=lambda child: child_layout_x(child) if child_layout_x(child) is not None else 0.0,
    )
    gaps: list[float] = []
    for index in range(len(ordered) - 1):
        current = ordered[index]
        nxt = ordered[index + 1]
        current_x = child_layout_x(current)
        next_x = child_layout_x(nxt)
        current_w = child_layout_width(current)
        if current_x is None or next_x is None or current_w is None:
            continue
        gap = next_x - current_x - current_w
        if gap >= 0:
            gaps.append(gap)
    if not gaps:
        return None
    return sum(gaps) / len(gaps)


def clear_stack_placement(placement: StackPlacement | None) -> None:
    """No-op placeholder; placements are replaced via model_copy in passes."""


def content_vertical_extent(node: CleanDesignTreeNode) -> float:
    """Estimate laid-out content height inside a host (ignores artboard cap)."""
    child_bottom = 0.0
    for child in node.children:
        child_y = child_layout_y(child) or 0.0
        child_h = child_layout_height(child) or 0.0
        child_bottom = max(child_bottom, child_y + child_h)
    if child_bottom > 0:
        return child_bottom
    if node.sizing.height is not None and node.sizing.height > 0:
        return float(node.sizing.height)
    if node.geometry_frame is not None and node.geometry_frame.world_aabb.height > 0:
        return float(node.geometry_frame.world_aabb.height)
    return 0.0


def root_vertical_extent(node: CleanDesignTreeNode) -> float:
    """Estimate vertical extent of a screen root."""
    if node.geometry_frame is not None and node.geometry_frame.world_aabb.height > 0:
        return float(node.geometry_frame.world_aabb.height)
    if node.sizing.height is not None and node.sizing.height > 0:
        return float(node.sizing.height)
    if not node.children:
        return 0.0
    return content_vertical_extent(node)


__all__ = [
    "_GAP_VARIANCE_TOLERANCE_PX",
    "_HEIGHT_DELTA_TOLERANCE_PX",
    "_OVERLAP_TOLERANCE_PX",
    "child_layout_height",
    "child_layout_width",
    "child_layout_x",
    "child_layout_y",
    "compute_axis_gaps_sorted",
    "compute_flex_gaps_paint_order",
    "compute_flex_spacing",
    "content_vertical_extent",
    "horizontal_extent_delta",
    "root_vertical_extent",
    "stack_children_overlap_on_x",
    "stack_children_overlap_on_y",
    "vertical_extent_delta",
]
