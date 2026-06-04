"""Tabs, carousel, and bottom navigation layout renderers."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    block_custom_code_close,
    block_custom_code_open,
    custom_code_zone_id,
)
from figma_flutter_agent.generator.layout_common import escape_dart_string, wrap_repaint_boundary
from figma_flutter_agent.generator.variant_props import get_variant_property, variant_is_checked
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_NAV_ICON_BY_NAME: tuple[tuple[tuple[str, ...], str], ...] = (
    (("home",), "Icons.home_outlined"),
    (("search", "explore"), "Icons.search"),
    (("profile", "account", "user"), "Icons.person_outline"),
    (("settings", "gear"), "Icons.settings_outlined"),
    (("favorite", "heart"), "Icons.favorite_border"),
    (("cart", "shop", "bag"), "Icons.shopping_bag_outlined"),
)


def tree_contains_node_type(tree: CleanDesignTreeNode, node_type: NodeType) -> bool:
    """Return True when ``node_type`` appears anywhere in the clean tree."""
    if tree.type == node_type:
        return True
    return any(tree_contains_node_type(child, node_type) for child in tree.children)


def first_node_id_of_type(tree: CleanDesignTreeNode, node_type: NodeType) -> str | None:
    """Return the first ``node_type`` id in depth-first order."""
    if tree.type == node_type:
        return tree.id
    for child in tree.children:
        found = first_node_id_of_type(child, node_type)
        if found is not None:
            return found
    return None


def bottom_nav_stateful_helpers(
    *,
    theme_variant: str = "material_3",
    node_id: str,
) -> str:
    """Return Dart helpers for adaptive bottom bar / side rail chrome (spec §7.3)."""
    zone = custom_code_zone_id(node_id, "bottom-nav")
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

  List<NavigationRailDestination> get _railDestinations => widget.items
      .map(
        (item) => NavigationRailDestination(
          icon: item.icon,
          selectedIcon: item.activeIcon ?? item.icon,
          label: Text(item.label ?? ''),
        ),
      )
      .toList();

  @override
  Widget build(BuildContext context) {{
    return LayoutBuilder(
      builder: (context, constraints) {{
        final screenWidth = MediaQuery.sizeOf(context).width;
        final useRail = AppBreakpoints.isTablet(screenWidth)
            || AppBreakpoints.isDesktop(screenWidth);
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


def label_from_child(child: CleanDesignTreeNode) -> str:
    """Resolve a tab or nav item label from a child node."""
    if child.text and child.text.strip():
        return escape_dart_string(child.text.strip())
    for descendant in child.children:
        if descendant.type == NodeType.TEXT and descendant.text:
            return escape_dart_string(descendant.text.strip())
    return escape_dart_string(child.name)


def tab_label_from_child(child: CleanDesignTreeNode) -> str:
    """Use panel frame names for tab labels (not inner headline text)."""
    return escape_dart_string(child.name)


def render_tabs(
    child_widgets: list[str],
    node: CleanDesignTreeNode,
    *,
    theme_variant: str = "material_3",
) -> str:
    """Render tabbed navigation (Material or Cupertino)."""
    tab_count = max(len(node.children), 1)
    views = ", ".join(child_widgets) if child_widgets else "const SizedBox.shrink()"
    if theme_variant == "cupertino":
        if node.children:
            items = ", ".join(
                "BottomNavigationBarItem("
                f"icon: Icon(CupertinoIcons.circle), "
                f"label: '{tab_label_from_child(child)}'"
                ")"
                for child in node.children
            )
        else:
            items = (
                "BottomNavigationBarItem("
                "icon: Icon(CupertinoIcons.circle), "
                "label: 'Tab'"
                ")"
            )
        cases = "\n".join(
            f"      case {index}: return {child_widgets[index] if index < len(child_widgets) else 'const SizedBox.shrink()'};"
            for index in range(tab_count)
        )
        tabs_widget = (
            f"CupertinoTabScaffold("
            f"tabBar: CupertinoTabBar(items: [{items}]), "
            f"tabBuilder: (context, index) {{"
            f"switch (index) {{"
            f"{cases}"
            f"      default: return const SizedBox.shrink();"
            f"    }}"
            f"  }}"
            f")"
        )
        return wrap_repaint_boundary(tabs_widget)
    if node.children:
        tabs = ", ".join(f"Tab(text: '{tab_label_from_child(child)}')" for child in node.children)
    else:
        tabs = "Tab(text: 'Tab')"
    tabs_widget = (
        f"DefaultTabController("
        f"length: {tab_count}, "
        f"child: Column("
        f"children: ["
        f"TabBar(tabs: [{tabs}]), "
        f"Expanded(child: TabBarView(children: [{views}]))"
        f"]"
        f")"
        f")"
    )
    return wrap_repaint_boundary(tabs_widget)


def carousel_aspect_ratio_expr(node: CleanDesignTreeNode) -> str:
    """Return aspect ratio for a bounded carousel without fixed pixel height."""
    width = node.sizing.width if node.sizing.width is not None else 360.0
    height = node.sizing.height if node.sizing.height is not None else 240.0
    if height <= 0:
        height = 240.0
    return f"{width / height:.4f}"


def render_carousel(
    child_widgets: list[str],
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None,
) -> str:
    """Render a snapping horizontal carousel using PageView."""
    body = ", ".join(child_widgets) if child_widgets else "const SizedBox.shrink()"
    page_view = f"PageView(children: [{body}])"
    if parent_type == NodeType.COLUMN and node.sizing.height_mode == SizingMode.FILL:
        return f"Expanded(child: {wrap_repaint_boundary(page_view)})"
    aspect_ratio = carousel_aspect_ratio_expr(node)
    return wrap_repaint_boundary(f"AspectRatio(aspectRatio: {aspect_ratio}, child: {page_view})")


def find_nav_icon_node(child: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    """Return the first descendant that carries a vector asset for a nav icon."""
    if child.vector_asset_key and child.type in {NodeType.IMAGE, NodeType.VECTOR}:
        return child
    for descendant in child.children:
        found = find_nav_icon_node(descendant)
        if found is not None:
            return found
    return None


def nav_icon_expr(child: CleanDesignTreeNode, *, uses_svg: bool) -> str:
    """Build icon widget expression for a bottom-nav item."""
    icon_node = find_nav_icon_node(child)
    if icon_node is not None and icon_node.vector_asset_key and uses_svg:
        asset = escape_dart_string(icon_node.vector_asset_key)
        return f"SvgPicture.asset('{asset}', width: 24, height: 24)"
    name_lower = child.name.lower()
    for tokens, icon_name in _NAV_ICON_BY_NAME:
        if any(token in name_lower for token in tokens):
            return f"const Icon({icon_name})"
    return "const Icon(Icons.circle_outlined)"


def bottom_nav_current_index(node: CleanDesignTreeNode) -> int:
    """Resolve selected tab index from child variants or nav-level metadata."""
    for index, child in enumerate(node.children):
        if variant_is_checked(child):
            return index
    selected = get_variant_property(node, "selected", "selectedIndex", "activeIndex")
    if selected is not None and selected.strip().isdigit():
        return int(selected.strip())
    return 0


def render_bottom_navigation(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
    theme_variant: str = "material_3",
) -> str:
    """Render adaptive navigation chrome from child nav items."""
    if node.children:
        items = ", ".join(
            "BottomNavigationBarItem("
            f"icon: {nav_icon_expr(child, uses_svg=uses_svg)}, "
            f"activeIcon: {nav_icon_expr(child, uses_svg=uses_svg)}, "
            f"label: '{label_from_child(child)}'"
            ")"
            for child in node.children
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
    return f"_LayoutChromeNav(initialIndex: {current_index}, items: [{items}])"
