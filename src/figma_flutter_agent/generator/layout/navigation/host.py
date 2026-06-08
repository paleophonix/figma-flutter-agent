"""Bottom navigation host and Figma chrome composition."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode


def bottom_nav_has_compact_pill_tabs(node: CleanDesignTreeNode) -> bool:
    """Return True when bottom-nav tabs are compact pill columns with labels."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        collect_bottom_nav_items,
        column_is_compact_nav_tab,
    )

    items = collect_bottom_nav_items(node)
    if len(items) < 2:
        return False
    return all(column_is_compact_nav_tab(item) for item in items)


def wrap_bottom_nav_figma_chrome(
    node: CleanDesignTreeNode,
    nav_body: str,
    *,
    solid_shell: bool = False,
) -> str:
    """Preserve painted Figma chrome while hosting an interactive nav bar body."""
    from figma_flutter_agent.generator.layout.widgets.render import (
        _decorate_widget_with_box_decoration,
    )

    working = _decorate_widget_with_box_decoration(
        node,
        nav_body,
        omit_backdrop_blur=solid_shell,
    )
    return f"RepaintBoundary(child: {working})"


def compose_bottom_navigation_host(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str = "material_3",
) -> str:
    """Render clickable nav items inside optional Figma chrome shell."""
    from figma_flutter_agent.generator.layout.navigation.bottom import (
        render_bottom_navigation,
        render_pill_bottom_navigation,
    )

    use_pill = bottom_nav_has_figma_chrome(node) and bottom_nav_has_compact_pill_tabs(node)
    if use_pill:
        nav_body = render_pill_bottom_navigation(node, uses_svg=uses_svg)
    else:
        nav_body = render_bottom_navigation(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
    if bottom_nav_has_figma_chrome(node):
        return wrap_bottom_nav_figma_chrome(node, nav_body, solid_shell=use_pill)
    return nav_body


def bottom_nav_has_figma_chrome(node: CleanDesignTreeNode) -> bool:
    """Return True when a bottom-nav host carries painted Figma chrome to preserve."""
    if not node.children:
        return False
    style = node.style
    if style.border_radius_corners is not None:
        return True
    if style.background_blur is not None and float(style.background_blur) > 0:
        return True
    if style.effects:
        return True
    radius = style.border_radius
    return radius is not None and float(radius) >= 16.0
