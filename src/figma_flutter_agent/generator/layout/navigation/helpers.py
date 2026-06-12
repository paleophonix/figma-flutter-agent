"""Dart helper classes for bottom navigation chrome."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
)


def bottom_nav_stateful_helpers(
    *,
    theme_variant: str = "material_3",
    node_id: str,
) -> str:
    """Return Dart helpers for adaptive bottom bar / side rail chrome."""
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
        final width = constraints.maxWidth;
        final useRail = (AppBreakpoints.isTablet(width)
            || AppBreakpoints.isDesktop(width))
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
