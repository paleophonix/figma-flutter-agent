"""Bottom navigation widget composition."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.navigation.items import (
    bottom_nav_current_index,
    collect_bottom_nav_items,
    nav_icon_asset_path,
    nav_icon_expr,
    nav_pill_palette,
)
from figma_flutter_agent.generator.layout.navigation.labels import label_from_child
from figma_flutter_agent.schemas import CleanDesignTreeNode


def render_bottom_navigation(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str = "material_3",
) -> str:
    """Render adaptive navigation chrome from child nav items."""
    nav_children = collect_bottom_nav_items(node)
    if nav_children:
        items = ", ".join(
            "BottomNavigationBarItem("
            f"icon: {nav_icon_expr(child, uses_svg=uses_svg)}, "
            f"activeIcon: {nav_icon_expr(child, uses_svg=uses_svg)}, "
            f"label: '{label_from_child(child)}'"
            ")"
            for child in nav_children
        )
    else:
        items = (
            "BottomNavigationBarItem("
            "icon: const Icon(Icons.home_outlined), "
            "activeIcon: const Icon(Icons.home_outlined), "
            "label: 'Home'"
            ")"
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
    if not nav_children:
        return render_bottom_navigation(node, uses_svg=uses_svg)
    palette = nav_pill_palette(node)
    tab_specs: list[str] = []
    for child in nav_children:
        label = escape_dart_string(label_from_child(child))
        asset = nav_icon_asset_path(child, uses_svg=uses_svg)
        asset_lit = escape_dart_string(asset or "")
        tab_specs.append(
            f"_PillNavTabSpec(label: '{label}', iconAsset: '{asset_lit}')"
        )
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
