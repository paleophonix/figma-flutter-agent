"""Bottom navigation widget composition."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.navigation.constants import MIN_BOTTOM_NAV_ITEMS
from figma_flutter_agent.generator.layout.navigation.items import (
    bottom_nav_current_index,
    collect_bottom_nav_items,
    nav_icon_asset_path,
    nav_icon_expr,
    nav_icon_tab_spec_expr,
    nav_pill_palette,
)
from figma_flutter_agent.generator.layout.navigation.labels import label_from_child
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def render_passive_bottom_chrome(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str = "material_3",
) -> str:
    """Render non-interactive bottom chrome when fewer than two nav destinations exist."""
    from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body

    if not node.children:
        return "const SizedBox.shrink()"
    parts = [
        render_node_body(
            child,
            uses_svg=uses_svg,
            parent_type=NodeType.STACK,
            parent_node=node,
            theme_variant=theme_variant,
        )
        for child in node.children
    ]
    body = parts[0] if len(parts) == 1 else f"Stack(children: [{', '.join(parts)}])"
    width = node.sizing.width
    height = node.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        body = (
            f"SizedBox(width: {format_geometry_literal(width)}, "
            f"height: {format_geometry_literal(height)}, child: {body})"
        )
    return f"IgnorePointer(ignoring: true, child: {body})"


def render_icon_only_bottom_navigation(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str:
    """Render icon-only bottom navigation for Figma chrome shells (no Material labels)."""
    nav_children = collect_bottom_nav_items(node)
    if len(nav_children) < MIN_BOTTOM_NAV_ITEMS:
        return render_passive_bottom_chrome(node, uses_svg=uses_svg)
    palette = nav_pill_palette(node)
    tab_specs: list[str] = []
    for child in nav_children:
        tab_specs.append(nav_icon_tab_spec_expr(child, uses_svg=uses_svg))
    current_index = bottom_nav_current_index(node)
    radius = format_geometry_literal(float(palette["pill_radius"]))
    substrate_width = format_geometry_literal(float(palette["active_substrate_width"]))
    substrate_height = format_geometry_literal(float(palette["active_substrate_height"]))
    return (
        "_LayoutIconNav("
        f"initialIndex: {current_index}, "
        f"tabs: [{', '.join(tab_specs)}], "
        f"activeBackground: {palette['active_bg']}, "
        f"activeForeground: {palette['active_fg']}, "
        f"inactiveForeground: {palette['inactive_fg']}, "
        f"activePillRadius: {radius}, "
        f"activeSubstrateWidth: {substrate_width}, "
        f"activeSubstrateHeight: {substrate_height}"
        ")"
    )


def render_bottom_navigation(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str = "material_3",
) -> str:
    """Render adaptive navigation chrome from child nav items."""
    nav_children = collect_bottom_nav_items(node)
    if len(nav_children) < MIN_BOTTOM_NAV_ITEMS:
        return render_passive_bottom_chrome(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
    items = ", ".join(
        "BottomNavigationBarItem("
        f"icon: {nav_icon_expr(child, uses_svg=uses_svg)}, "
        f"activeIcon: {nav_icon_expr(child, uses_svg=uses_svg)}, "
        f"label: '{label_from_child(child)}'"
        ")"
        for child in nav_children
    )
    current_index = bottom_nav_current_index(node)
    _ = theme_variant
    return f"_LayoutChromeNav(initialIndex: {current_index}, items: [{items}])"


def render_pill_bottom_navigation(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str:
    """Render Figma-style pill tabs (background highlight, no Material lift)."""
    nav_children = collect_bottom_nav_items(node)
    if len(nav_children) < MIN_BOTTOM_NAV_ITEMS:
        return render_passive_bottom_chrome(node, uses_svg=uses_svg)
    palette = nav_pill_palette(node)
    tab_specs: list[str] = []
    for child in nav_children:
        label = escape_dart_string(label_from_child(child))
        asset = nav_icon_asset_path(child, uses_svg=uses_svg)
        asset_lit = escape_dart_string(asset or "")
        tab_specs.append(f"_PillNavTabSpec(label: '{label}', iconAsset: '{asset_lit}')")
    current_index = bottom_nav_current_index(node)
    radius = palette["pill_radius"]
    return (
        "_LayoutPillNav("
        f"initialIndex: {current_index}, "
        f"tabs: [{', '.join(tab_specs)}], "
        f"activeBackground: {palette['active_bg']}, "
        f"activeForeground: {palette['active_fg']}, "
        f"inactiveForeground: {palette['inactive_fg']}, "
        f"pillRadius: {radius}"
        ")"
    )
