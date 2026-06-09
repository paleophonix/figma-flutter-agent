"""Viewport bounds validation for stack-placed IR nodes."""

from __future__ import annotations

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.layout.widgets import figma_positioned_dimensions
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    StackPlacement,
)
from figma_flutter_agent.generator.ir.validate.guards import _in_scroll_context

_VIEWPORT_OVERFLOW_MARGIN_PX = 20.0


def _viewport_box_metrics(
    clean: CleanDesignTreeNode,
    placement: StackPlacement,
) -> tuple[float, float, float, float] | None:
    width, height = figma_positioned_dimensions(clean, placement)
    left = placement.left if placement.left is not None else clean.offset_x
    top = placement.top if placement.top is not None else clean.offset_y
    box_width = width if width is not None else (clean.sizing.width or 0.0)
    box_height = height if height is not None else (clean.sizing.height or 0.0)
    if box_width <= 0 or box_height <= 0:
        return None
    return left, top, box_width, box_height


def _clamp_viewport_bounds(
    clean: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    """Shift ``stackPlacement`` so positioned nodes fit the root viewport (non-scroll)."""
    placement = clean.stack_placement
    if placement is None:
        return False
    if _in_scroll_context(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id):
        return False
    metrics = _viewport_box_metrics(clean, placement)
    if metrics is None:
        return False
    left, top, box_width, box_height = metrics
    margin = _VIEWPORT_OVERFLOW_MARGIN_PX
    new_left = left
    new_top = top
    if new_left < -margin:
        new_left = -margin
    if new_left + box_width > viewport_width + margin:
        new_left = viewport_width + margin - box_width
    if new_top < -margin:
        new_top = -margin
    if new_top + box_height > viewport_height + margin:
        new_top = viewport_height + margin - box_height
    center_x = new_left + box_width / 2.0
    center_y = new_top + box_height / 2.0
    min_center_x = margin
    max_center_x = viewport_width - margin
    min_center_y = margin
    max_center_y = viewport_height - margin
    if center_x < min_center_x:
        new_left += min_center_x - center_x
    elif center_x > max_center_x:
        new_left -= center_x - max_center_x
    if center_y < min_center_y:
        new_top += min_center_y - center_y
    elif center_y > max_center_y:
        new_top -= center_y - max_center_y
    if abs(new_left - left) < 0.5 and abs(new_top - top) < 0.5:
        return False
    clean.stack_placement = placement.model_copy(update={"left": new_left, "top": new_top})
    return True


def _validate_viewport_bounds(
    clean: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
    root_id: str,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    placement = clean.stack_placement
    if placement is None:
        return
    if parent_by_id.get(clean.id) != root_id:
        return
    if _in_scroll_context(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id):
        return
    metrics = _viewport_box_metrics(clean, placement)
    if metrics is None:
        return
    left, top, box_width, box_height = metrics
    center_x = left + box_width / 2.0
    center_y = top + box_height / 2.0
    margin = _VIEWPORT_OVERFLOW_MARGIN_PX
    if (
        center_x < -margin
        or center_x > viewport_width + margin
        or center_y < -margin
        or center_y > viewport_height + margin
    ):
        raise GenerationError(
            f"IR node {clean.id!r} center ({center_x:.1f}, {center_y:.1f}) lies outside the "
            f"{viewport_width:.0f}x{viewport_height:.0f} root frame without a scroll ancestor; "
            "likely hallucinated stackPlacement coordinates"
        )
