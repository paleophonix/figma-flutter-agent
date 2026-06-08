"""Tabs and carousel layout renderers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import wrap_repaint_boundary
from figma_flutter_agent.generator.layout.navigation.labels import tab_label_from_child
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode


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
