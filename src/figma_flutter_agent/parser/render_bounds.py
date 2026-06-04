"""Figma ``absoluteRenderBounds`` vs ``absoluteBoundingBox`` expansion (FID-39)."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Padding, StackPlacement

_RENDER_EXPAND_THRESHOLD = 0.5


def _box(value: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return ``(x, y, width, height)`` when all keys are present."""
    if not value:
        return None
    try:
        return (
            float(value["x"]),
            float(value["y"]),
            float(value["width"]),
            float(value["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def compute_render_bounds_expand(
    bbox: dict[str, Any],
    render_bounds: dict[str, Any],
) -> Padding | None:
    """Compute outward paint expansion from layout box to render bounds.

    Args:
        bbox: Figma ``absoluteBoundingBox``.
        render_bounds: Figma ``absoluteRenderBounds``.

    Returns:
        Non-zero padding expansion per edge, or ``None`` when within threshold.
    """
    layout = _box(bbox)
    painted = _box(render_bounds)
    if layout is None or painted is None:
        return None
    lx, ly, lw, lh = layout
    rx, ry, rw, rh = painted
    expand_left = max(0.0, lx - rx)
    expand_top = max(0.0, ly - ry)
    expand_right = max(0.0, (rx + rw) - (lx + lw))
    expand_bottom = max(0.0, (ry + rh) - (ly + lh))
    if (
        expand_left <= _RENDER_EXPAND_THRESHOLD
        and expand_top <= _RENDER_EXPAND_THRESHOLD
        and expand_right <= _RENDER_EXPAND_THRESHOLD
        and expand_bottom <= _RENDER_EXPAND_THRESHOLD
    ):
        return None
    return Padding(
        top=round_geometry(expand_top) or 0.0,
        bottom=round_geometry(expand_bottom) or 0.0,
        left=round_geometry(expand_left) or 0.0,
        right=round_geometry(expand_right) or 0.0,
    )


def node_needs_render_bounds_expansion(node: CleanDesignTreeNode) -> bool:
    """Return True when outward paint extends beyond the layout bounding box."""
    expand = node.style.render_bounds_expand
    if expand is None:
        return False
    return any(
        (expand.top or 0) > _RENDER_EXPAND_THRESHOLD
        or (expand.bottom or 0) > _RENDER_EXPAND_THRESHOLD
        or (expand.left or 0) > _RENDER_EXPAND_THRESHOLD
        or (expand.right or 0) > _RENDER_EXPAND_THRESHOLD
    )


def expand_stack_placement(
    placement: StackPlacement,
    expand: Padding,
) -> StackPlacement:
    """Widen absolute placement to include outward render-bound paint.

    Args:
        placement: Original stack child placement from bounding box.
        expand: Outward expansion per edge.

    Returns:
        Placement with adjusted edges and dimensions.
    """
    left = (placement.left or 0.0) - (expand.left or 0.0)
    top = (placement.top or 0.0) - (expand.top or 0.0)
    right = (placement.right or 0.0) - (expand.right or 0.0)
    bottom = (placement.bottom or 0.0) - (expand.bottom or 0.0)
    width = placement.width
    height = placement.height
    if width is not None:
        width = width + (expand.left or 0.0) + (expand.right or 0.0)
    if height is not None:
        height = height + (expand.top or 0.0) + (expand.bottom or 0.0)
    return placement.model_copy(
        update={
            "left": round_geometry(left) or 0.0,
            "top": round_geometry(top) or 0.0,
            "right": round_geometry(right) or 0.0,
            "bottom": round_geometry(bottom) or 0.0,
            "width": round_geometry(width) if width is not None else None,
            "height": round_geometry(height) if height is not None else None,
        }
    )


def reconcile_render_bounds_expansion_in_tree(
    tree: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Apply render-bound expansion to absolute stack placements (FID-39)."""

    def visit(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [visit(child) for child in node.children]
        working = node.model_copy(update={"children": children})
        if working.type != NodeType.STACK:
            return working
        updated_children: list[CleanDesignTreeNode] = []
        for child in working.children:
            expand = child.style.render_bounds_expand
            placement = child.stack_placement
            if (
                expand is None
                or placement is None
                or not node_needs_render_bounds_expansion(child)
            ):
                updated_children.append(child)
                continue
            updated_children.append(
                child.model_copy(
                    update={
                        "stack_placement": expand_stack_placement(placement, expand),
                    }
                )
            )
        return working.model_copy(update={"children": updated_children})

    return visit(tree)
