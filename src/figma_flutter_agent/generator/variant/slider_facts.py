"""Structural facts for dual-thumb range slider hosts."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import dart_color_expr
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MIN_THUMB_HOST_HEIGHT_PX = 16.0
_DEFAULT_RANGE_START = "0.2"
_DEFAULT_RANGE_END = "0.8"
_RANGE_SLIDER_MIN_HEIGHT_PX = 48.0


def _thumb_stack_children(host: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    return [
        child
        for child in host.children
        if child.type in {NodeType.STACK, NodeType.CONTAINER}
        and child.sizing.height is not None
        and float(child.sizing.height) >= _MIN_THUMB_HOST_HEIGHT_PX
    ]


def range_slider_track_host(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Return the SLIDER node that owns thumb children when nested under a track shell."""
    if node.type != NodeType.SLIDER:
        return node
    if _thumb_stack_children(node):
        return node
    for child in node.children:
        if child.type == NodeType.SLIDER and _thumb_stack_children(child):
            return child
    return node


def layout_fact_dual_thumb_range_slider(node: CleanDesignTreeNode) -> bool:
    """True when a slider host materializes as a dual-thumb range control."""
    if node.type != NodeType.SLIDER:
        return False
    host = range_slider_track_host(node)
    return len(_thumb_stack_children(host)) >= 2


def dual_thumb_range_values(node: CleanDesignTreeNode) -> tuple[str, str]:
    """Derive ``Range`` endpoint literals from thumb placement when available."""
    host = range_slider_track_host(node)
    thumbs = _thumb_stack_children(host)
    if len(thumbs) < 2:
        return _DEFAULT_RANGE_START, _DEFAULT_RANGE_END

    def x_position(item: CleanDesignTreeNode) -> float:
        placement = item.stack_placement
        if placement is not None and placement.left is not None:
            return float(placement.left)
        return 0.0

    ordered = sorted(thumbs, key=x_position)
    track_width = float(host.sizing.width or node.sizing.width or 0.0)
    if track_width <= 0.0:
        return _DEFAULT_RANGE_START, _DEFAULT_RANGE_END
    thumb_radius = float(ordered[0].sizing.width or 12.0) / 2.0
    start = min(1.0, max(0.0, (x_position(ordered[0]) + thumb_radius) / track_width))
    end = min(1.0, max(0.0, (x_position(ordered[1]) + thumb_radius) / track_width))
    if end <= start:
        return _DEFAULT_RANGE_START, _DEFAULT_RANGE_END
    return str(round(start, 2)), str(round(end, 2))


def range_slider_active_color_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart color expression for the painted range track."""
    for candidate in (node, *node.children):
        if candidate.style.background_color:
            return dart_color_expr(candidate.style, fallback="Theme.of(context).colorScheme.primary")
    return "Theme.of(context).colorScheme.primary"


def range_slider_emit_height(node: CleanDesignTreeNode) -> float:
    """Minimum vertical extent for a native range slider with thumb affordances."""
    host = range_slider_track_host(node)
    thumb_heights = [
        float(child.sizing.height or 0.0)
        for child in _thumb_stack_children(host)
        if child.sizing.height is not None
    ]
    if thumb_heights:
        return max(_RANGE_SLIDER_MIN_HEIGHT_PX, max(thumb_heights) + 16.0)
    host_height = float(node.sizing.height or 0.0)
    if host_height > _MIN_THUMB_HOST_HEIGHT_PX:
        return host_height
    return _RANGE_SLIDER_MIN_HEIGHT_PX
