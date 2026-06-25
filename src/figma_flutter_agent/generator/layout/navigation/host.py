"""Bottom navigation host and Figma chrome composition."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.navigation.constants import MIN_BOTTOM_NAV_ITEMS
from figma_flutter_agent.schemas import CleanDesignTreeNode


def bottom_nav_has_compact_pill_tabs(node: CleanDesignTreeNode) -> bool:
    """Return True when bottom-nav tabs include compact pill hosts (column or stack)."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        collect_bottom_nav_items,
        layout_fact_column_compact_nav_tab,
        layout_fact_stack_pill_nav_tab,
    )

    items = collect_bottom_nav_items(node)
    if len(items) < 2:
        return False
    return any(layout_fact_column_compact_nav_tab(item) or layout_fact_stack_pill_nav_tab(item) for item in items)


def wrap_bottom_nav_figma_chrome(
    node: CleanDesignTreeNode,
    nav_body: str,
    *,
    solid_shell: bool = False,
) -> str:
    """Preserve painted Figma chrome while hosting an interactive nav bar body."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        find_nav_chrome_background_shell,
    )
    from figma_flutter_agent.generator.layout.widgets import (
        _decorate_widget_with_box_decoration,
    )

    chrome_node = find_nav_chrome_background_shell(node) or node
    working = _decorate_widget_with_box_decoration(
        chrome_node,
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
        render_icon_only_bottom_navigation,
        render_passive_bottom_chrome,
        render_pill_bottom_navigation,
    )
    from figma_flutter_agent.generator.layout.navigation.items import (
        bottom_nav_host_uses_icon_only_tabs,
        collect_bottom_nav_items,
    )

    nav_children = collect_bottom_nav_items(node)
    if len(nav_children) < MIN_BOTTOM_NAV_ITEMS:
        passive = render_passive_bottom_chrome(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
        if bottom_nav_has_figma_chrome(node):
            from figma_flutter_agent.generator.layout.widgets.decoration import (
                _effective_backdrop_blur,
            )

            preserve_blur = _effective_backdrop_blur(node) is not None
            return wrap_bottom_nav_figma_chrome(
                node,
                passive,
                solid_shell=not preserve_blur,
            )
        return passive

    use_pill = bottom_nav_has_compact_pill_tabs(node)
    use_icon_row = bottom_nav_has_figma_chrome(node) and bottom_nav_host_uses_icon_only_tabs(node)
    if use_icon_row:
        nav_body = render_icon_only_bottom_navigation(node, uses_svg=uses_svg)
    elif use_pill:
        nav_body = render_pill_bottom_navigation(node, uses_svg=uses_svg)
    else:
        nav_body = render_bottom_navigation(
            node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
        )
    if bottom_nav_has_figma_chrome(node):
        from figma_flutter_agent.generator.layout.widgets.decoration import (
            _effective_backdrop_blur,
        )

        preserve_blur = _effective_backdrop_blur(node) is not None
        return wrap_bottom_nav_figma_chrome(
            node,
            nav_body,
            solid_shell=use_pill and not preserve_blur,
        )
    return nav_body


def bottom_nav_host_should_stretch_horizontal(node: CleanDesignTreeNode) -> bool:
    """Docked bottom navigation shells should span the viewport width."""
    from figma_flutter_agent.parser.stack_paint import _is_bottom_screen_chrome
    from figma_flutter_agent.schemas import NodeType

    width = node.sizing.width
    if width is None or float(width) < 300.0:
        return False
    if node.type == NodeType.BOTTOM_NAV:
        return True
    if _is_bottom_screen_chrome(node):
        return True
    placement = node.stack_placement
    return placement is not None and placement.vertical == "BOTTOM"


def bottom_nav_has_figma_chrome(node: CleanDesignTreeNode) -> bool:
    """Return True when a bottom-nav host carries painted Figma chrome to preserve."""
    from figma_flutter_agent.generator.layout.navigation.items import (
        find_nav_chrome_background_shell,
    )

    if not node.children:
        return False
    if find_nav_chrome_background_shell(node) is not None:
        return True
    style = node.style
    if style.border_radius_corners is not None:
        return True
    if style.background_blur is not None and float(style.background_blur) > 0:
        return True
    if style.effects:
        return True
    radius = style.border_radius
    return radius is not None and float(radius) >= 16.0
