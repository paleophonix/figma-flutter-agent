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
    return layout_fact_row_status_pill_badge(host) or layout_fact_row_tight_horizontal_pill_label(
        host
    )


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


def vertical_chip_button_should_paint_icon_surface_only(node: CleanDesignTreeNode) -> bool:
    """Category chips with a lower label band must not paint ink across the full tile."""
    from figma_flutter_agent.parser.interaction import (
        layout_fact_stack_vertical_icon_label_chip_tile,
    )

    return layout_fact_stack_vertical_icon_label_chip_tile(node)


def vertical_chip_icon_surface_height(node: CleanDesignTreeNode) -> float:
    """Return the icon-surface band height for a vertical category chip tile."""
    width = float(node.sizing.width or 0.0)
    height = float(node.sizing.height or 0.0)
    if width <= 0.0 or height <= 0.0:
        return 65.0
    label_reserve = max(height * 0.28, 24.0)
    return max(min(width, height - label_reserve), min(width, 65.0))


def bottom_nav_active_tab_should_split_surface_label(node: CleanDesignTreeNode) -> bool:
    """Bottom-nav active tabs must bind ink to the painted pill, not the full tab stack."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        layout_fact_stack_bottom_nav_active_tab_pill,
    )

    return layout_fact_stack_bottom_nav_active_tab_pill(node)


def bottom_nav_active_tab_icon_band_height(node: CleanDesignTreeNode) -> float:
    """Return the painted pill height for an active bottom-nav tab."""
    from figma_flutter_agent.parser.interaction import primary_surface_node

    surface = primary_surface_node(node)
    if surface is not None and surface.sizing.height is not None and surface.sizing.height > 0:
        return float(surface.sizing.height)
    return float(node.sizing.height or 46.0)


def button_is_pill_with_label_column(node: CleanDesignTreeNode) -> bool:
    """Pill CTA whose label copy lives in a centered inner ``COLUMN`` (multi-line stack)."""
    if node.type != NodeType.BUTTON:
        return False
    height = node.sizing.height
    radius = node.style.border_radius
    if height is None or radius is None or float(height) <= 0:
        return False
    if float(radius) < float(height) * 0.35:
        return False
    if len(node.children) != 1 or node.children[0].type != NodeType.COLUMN:
        return False
    label_column = node.children[0]
    text_children = [
        child
        for child in label_column.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    return bool(text_children)


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
    text_children = [child for child in node.children if child.type == NodeType.TEXT]
    if len(text_children) != 1:
        return False
    if len(node.children) == 1:
        return True
    from figma_flutter_agent.parser.interaction import primary_surface_node, surface_covers_node

    surface = primary_surface_node(node)
    if surface is None:
        return False
    non_text = [child for child in node.children if child.type != NodeType.TEXT]
    return (
        len(non_text) == 1 and surface_covers_node(node, surface) and non_text[0].id == surface.id
    )


def button_should_center_sole_text_label(node: CleanDesignTreeNode) -> bool:
    """Wide or square CTAs with a single centered label (not only high-radius pills)."""
    if node.type != NodeType.BUTTON:
        return False
    from figma_flutter_agent.parser.interaction import (
        button_has_list_tile_row_body,
        button_is_left_aligned_text_label,
        button_stack_has_left_icon,
    )

    if button_has_list_tile_row_body(node) or button_stack_has_left_icon(node):
        return False
    if button_is_left_aligned_text_label(node):
        return False
    text_children = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and (child.text or "").strip()
    ]
    if len(text_children) != 1:
        return False
    text = text_children[0]
    if (text.style.text_align or "").upper() == "CENTER":
        return True
    parent_width = node.sizing.width
    text_width = text.sizing.width
    placement = text.stack_placement
    if placement is not None and placement.width is not None and placement.width > 0:
        text_width = placement.width
    if parent_width is None or text_width is None or float(parent_width) <= 0:
        return False
    return float(text_width) >= float(parent_width) * 0.55


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
