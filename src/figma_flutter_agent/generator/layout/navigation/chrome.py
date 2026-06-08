"""Bottom navigation chrome helpers."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+(?!_LayoutChromeNav)(?!_LayoutPillNav)(\w+)\s+extends\s+(?:Stateless|Stateful)Widget\b"
)


def ensure_layout_chrome_nav_helpers(
    source: str,
    *,
    theme_variant: str = "material_3",
) -> str:
    """Inject private bottom-nav helpers into widget libraries that reference them."""
    needs_chrome = "_LayoutChromeNav(" in source
    needs_pill = "_LayoutPillNav(" in source
    if not needs_chrome and not needs_pill:
        return source
    if needs_chrome and "class _LayoutChromeNav extends StatefulWidget" not in source:
        decl = _WIDGET_CLASS_DECL_RE.search(source)
        if decl is not None:
            helpers = bottom_nav_stateful_helpers(
                theme_variant=theme_variant,
                node_id="widget-bottom-nav",
            )
            source = f"{source[: decl.start()]}{helpers}\n{source[decl.start() :]}"
    if needs_pill and "class _LayoutPillNav extends StatefulWidget" not in source:
        decl = _WIDGET_CLASS_DECL_RE.search(source)
        if decl is not None:
            helpers = pill_nav_stateful_helpers(node_id="widget-bottom-nav")
            source = f"{source[: decl.start()]}{helpers}\n{source[decl.start() :]}"
    if "app_layout.dart" not in source and (
        "_LayoutChromeNav(" in source or "_LayoutPillNav(" in source
    ):
        package_name = "demo_app"
        package_match = re.search(r"import 'package:([^/]+)/theme/", source)
        if package_match is not None:
            package_name = package_match.group(1)
        material_import = re.search(
            r"import 'package:flutter/material.dart';\n",
            source,
        )
        if material_import is not None:
            layout_import = f"import 'package:{package_name}/theme/app_layout.dart';\n"
            insert_at = material_import.end()
            source = f"{source[:insert_at]}{layout_import}{source[insert_at:]}"
    return source


def bottom_nav_stateful_helpers(
    *,
    theme_variant: str = "material_3",
    node_id: str,
) -> str:
    """Return Dart helpers for adaptive bottom bar / side rail chrome (spec section 7.3)."""
    zone = "bottom-nav"
    open_zone = block_custom_code_open(zone)
    close_zone = block_custom_code_close(zone)
    mobile_bar = (
        "CupertinoTabBar("
        "currentIndex: _currentIndex, "
        "onTap: (index) {"
        "setState(() => _currentIndex = index);"
        f"{open_zone}"
        f"{close_zone}"
        "}, "
        "items: widget.items,"
        ")"
        if theme_variant == "cupertino"
        else f"""BottomNavigationBar(
            currentIndex: _currentIndex,
            onTap: (index) {{
              setState(() => _currentIndex = index);
              {open_zone}
              {close_zone}
            }},
            items: widget.items,
          )"""
    )
    return f"""
class _LayoutChromeNav extends StatefulWidget {{
  const _LayoutChromeNav({{required this.initialIndex, required this.items, super.key}});

  final int initialIndex;
  final List<BottomNavigationBarItem> items;

  @override
  State<_LayoutChromeNav> createState() => _LayoutChromeNavState();
}}

class _LayoutChromeNavState extends State<_LayoutChromeNav> {{
  late int _currentIndex = widget.initialIndex;

  List<NavigationRailDestination> get _railDestinations {{
    final textScaler = MediaQuery.textScalerOf(context);
    return widget.items
        .map(
          (item) => NavigationRailDestination(
            icon: item.icon,
            selectedIcon: item.activeIcon ?? item.icon,
            label: Text(item.label ?? '', textScaler: textScaler),
          ),
        )
        .toList();
  }}

  @override
  Widget build(BuildContext context) {{
    return LayoutBuilder(
      builder: (context, constraints) {{
        final screenWidth = MediaQuery.sizeOf(context).width;
        final useRail = (AppBreakpoints.isTablet(screenWidth)
            || AppBreakpoints.isDesktop(screenWidth))
            && constraints.maxHeight > 120.0;
        if (useRail) {{
          return RepaintBoundary(
            child: NavigationRail(
              selectedIndex: _currentIndex,
              onDestinationSelected: (index) {{
                setState(() => _currentIndex = index);
                {open_zone}
                {close_zone}
              }},
              labelType: NavigationRailLabelType.all,
              destinations: _railDestinations,
            ),
          );
        }}
        return RepaintBoundary(
          child: {mobile_bar},
        );
      }},
    );
  }}
}}
"""


def pill_nav_stateful_helpers(*, node_id: str) -> str:
    """Return Dart helpers for Figma-style pill bottom navigation."""
    zone = "bottom-nav"
    open_zone = block_custom_code_open(zone)
    close_zone = block_custom_code_close(zone)
    return f"""
class _PillNavTabSpec {{
  const _PillNavTabSpec({{required this.label, required this.iconAsset}});

  final String label;
  final String iconAsset;
}}

class _LayoutPillNav extends StatefulWidget {{
  const _LayoutPillNav({{
    required this.initialIndex,
    required this.tabs,
    required this.activeBackground,
    required this.activeForeground,
    required this.inactiveForeground,
    required this.pillRadius,
    super.key,
  }});

  final int initialIndex;
  final List<_PillNavTabSpec> tabs;
  final Color activeBackground;
  final Color activeForeground;
  final Color inactiveForeground;
  final double pillRadius;

  @override
  State<_LayoutPillNav> createState() => _LayoutPillNavState();
}}

class _LayoutPillNavState extends State<_LayoutPillNav> {{
  late int _currentIndex = widget.initialIndex;

  Widget _buildTab(int index) {{
    final tab = widget.tabs[index];
    final isActive = _currentIndex == index;
    final foreground = isActive ? widget.activeForeground : widget.inactiveForeground;
    final icon = tab.iconAsset.isNotEmpty
        ? SvgPicture.asset(
            tab.iconAsset,
            width: 22,
            height: 22,
            colorFilter: ColorFilter.mode(foreground, BlendMode.srcIn),
          )
        : Icon(Icons.circle_outlined, size: 22, color: foreground);
    return GestureDetector(
      onTap: () {{
        setState(() => _currentIndex = index);
        {open_zone}
        {close_zone}
      }},
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
        decoration: BoxDecoration(
          color: isActive ? widget.activeBackground : null,
          borderRadius: BorderRadius.circular(widget.pillRadius),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            icon,
            const SizedBox(height: 2),
            Text(
              tab.label,
              textScaler: MediaQuery.textScalerOf(context),
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: foreground,
              ),
            ),
          ],
        ),
      ),
    );
  }}

  List<NavigationRailDestination> get _railDestinations {{
    final textScaler = MediaQuery.textScalerOf(context);
    return widget.tabs
        .map(
          (tab) => NavigationRailDestination(
            icon: tab.iconAsset.isNotEmpty
                ? SvgPicture.asset(tab.iconAsset, width: 22, height: 22)
                : const Icon(Icons.circle_outlined, size: 22),
            selectedIcon: tab.iconAsset.isNotEmpty
                ? SvgPicture.asset(
                    tab.iconAsset,
                    width: 22,
                    height: 22,
                    colorFilter: ColorFilter.mode(
                      widget.activeForeground,
                      BlendMode.srcIn,
                    ),
                  )
                : Icon(Icons.circle_outlined, size: 22, color: widget.activeForeground),
            label: Text(tab.label, textScaler: textScaler),
          ),
        )
        .toList();
  }}

  @override
  Widget build(BuildContext context) {{
    return LayoutBuilder(
      builder: (context, constraints) {{
        final screenWidth = MediaQuery.sizeOf(context).width;
        final useRail = (AppBreakpoints.isTablet(screenWidth)
            || AppBreakpoints.isDesktop(screenWidth))
            && constraints.maxHeight > 120.0;
        if (useRail) {{
          return RepaintBoundary(
            child: NavigationRail(
              selectedIndex: _currentIndex,
              onDestinationSelected: (index) {{
                setState(() => _currentIndex = index);
                {open_zone}
                {close_zone}
              }},
              labelType: NavigationRailLabelType.all,
              destinations: _railDestinations,
            ),
          );
        }}
        return RepaintBoundary(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              for (var index = 0; index < widget.tabs.length; index++)
                _buildTab(index),
            ],
          ),
        );
      }},
    );
  }}
}}
"""


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
