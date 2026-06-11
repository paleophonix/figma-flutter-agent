"""Figma ``absoluteRenderBounds`` vs ``absoluteBoundingBox`` expansion (FID-39)."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    Padding,
    StackPlacement,
)

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


def _stroke_outward_expand(style: NodeStyle) -> float:
    """Return outward stroke expansion per edge when render bounds are unavailable."""
    if not style.has_stroke or style.border_width is None or style.border_width <= 0:
        return 0.0
    align = (style.stroke_align or "INSIDE").upper()
    if align == "OUTSIDE":
        return style.border_width
    if align == "CENTER":
        return style.border_width / 2.0
    return 0.0


def _shadow_outward_expand(style: NodeStyle) -> Padding:
    """Estimate outward drop-shadow extent per edge from effect metadata."""
    expand_top = expand_bottom = expand_left = expand_right = 0.0
    for effect in style.effects:
        if effect.kind != "drop" or effect.blur <= 0:
            continue
        blur_extent = effect.blur / 2.0 + max(0.0, effect.spread)
        expand_top = max(expand_top, blur_extent + max(0.0, -effect.offset_y))
        expand_bottom = max(expand_bottom, blur_extent + max(0.0, effect.offset_y))
        expand_left = max(expand_left, blur_extent + max(0.0, -effect.offset_x))
        expand_right = max(expand_right, blur_extent + max(0.0, effect.offset_x))
    return Padding(
        top=expand_top,
        bottom=expand_bottom,
        left=expand_left,
        right=expand_right,
    )


def compute_style_outward_expand_fallback(style: NodeStyle) -> Padding | None:
    """Synthetic render-bound expansion when ``absoluteRenderBounds`` is missing.

    Args:
        style: Parsed node style with stroke/shadow metadata.

    Returns:
        Non-zero padding expansion per edge, or ``None`` when within threshold.
    """
    stroke_expand = _stroke_outward_expand(style)
    shadow = _shadow_outward_expand(style)
    expand_top = max(stroke_expand, shadow.top or 0.0)
    expand_bottom = max(stroke_expand, shadow.bottom or 0.0)
    expand_left = max(stroke_expand, shadow.left or 0.0)
    expand_right = max(stroke_expand, shadow.right or 0.0)
    if (
        expand_top <= _RENDER_EXPAND_THRESHOLD
        and expand_bottom <= _RENDER_EXPAND_THRESHOLD
        and expand_left <= _RENDER_EXPAND_THRESHOLD
        and expand_right <= _RENDER_EXPAND_THRESHOLD
    ):
        return None
    return Padding(
        top=round_geometry(expand_top) or 0.0,
        bottom=round_geometry(expand_bottom) or 0.0,
        left=round_geometry(expand_left) or 0.0,
        right=round_geometry(expand_right) or 0.0,
    )


def child_has_outward_paint(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack child paints outside its layout bounding box."""
    if node_needs_render_bounds_expansion(node):
        return True
    if node.style.effects:
        for effect in node.style.effects:
            if effect.kind == "drop" and effect.blur > _RENDER_EXPAND_THRESHOLD:
                return True
    stroke_expand = _stroke_outward_expand(node.style)
    return stroke_expand > _RENDER_EXPAND_THRESHOLD


def stack_needs_soft_clip(node: CleanDesignTreeNode) -> bool:
    """Return True when a stack must not clip outward paint at its edges."""
    return any(child_has_outward_paint(child) for child in node.children)


def node_needs_render_bounds_expansion(node: CleanDesignTreeNode) -> bool:
    """Return True when outward paint extends beyond the layout bounding box."""
    expand = node.style.render_bounds_expand
    if expand is None:
        return False
    return (
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
    """Return the tree unchanged (E0.2).

    ``style.render_bounds_expand`` must not be folded into ``stack_placement``.
    Soft-clip consumers read the expand field directly at emit time.
    """
    return tree
