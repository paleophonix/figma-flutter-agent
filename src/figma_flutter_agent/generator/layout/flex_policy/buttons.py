"""Button and chip flex policies."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode


def button_hosts_status_pill(node: CleanDesignTreeNode) -> bool:
    """Return True when a ``BUTTON`` wraps a painted status-pill label row."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        layout_fact_row_status_pill_badge,
        layout_fact_row_tight_horizontal_pill_label,
    )

    if node.type != NodeType.BUTTON or not node.children:
        return False
    host = node.children[0]
    return layout_fact_row_status_pill_badge(host) or layout_fact_row_tight_horizontal_pill_label(host)


def horizontal_chip_button_should_hug_width(node: CleanDesignTreeNode) -> bool:
    """Return True when a short pill button should hug chip copy, not a tight bbox."""
    if node.type != NodeType.BUTTON:
        return False
    height = node.sizing.height
    if height is None or float(height) <= 0 or float(height) > 44.0:
        return False
    if node.sizing.width_mode == SizingMode.FIXED:
        width = node.sizing.width
        if width is not None and float(width) > 0:
            return False
    if node.sizing.width_mode == SizingMode.FILL:
        return False
    width = node.sizing.width
    if width is None or float(width) <= 0 or float(width) > 180.0:
        return False
    return bool(node.style.background_color)


def button_is_pill_with_centered_label(node: CleanDesignTreeNode) -> bool:
    """Pill-shaped button whose sole child is centered label copy."""
    if node.type != NodeType.BUTTON:
        return False
    height = node.sizing.height
    radius = node.style.border_radius
    if height is None or radius is None or float(height) <= 0:
        return False
    if float(radius) < float(height) * 0.35:
        return False
    return not (len(node.children) != 1 or node.children[0].type != NodeType.TEXT)


def button_should_fitted_box_label(node: CleanDesignTreeNode) -> bool:
    """Fixed-size chip buttons need scale-down labels to avoid clipping."""
    if node.type != NodeType.BUTTON:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or float(width) <= 0 or float(height) <= 0:
        return False
    if float(height) > 44.0 or float(width) > 180.0:
        return False
    if len(node.children) != 1 or node.children[0].type != NodeType.TEXT:
        return False
    return bool(node.style.background_color)


def _bound_compact_icon_button(node: CleanDesignTreeNode, widget: str) -> str | None:
    """Pin circular icon buttons to Figma bounds before flex loose-wrap."""
    from figma_flutter_agent.parser.interaction import layout_fact_compact_icon_action_button

    if node.type != NodeType.BUTTON or not layout_fact_compact_icon_action_button(node):
        return None
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: {widget})"
