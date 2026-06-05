"""Cupertino navigation and shell codegen tests."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_cupertino import screen_shell_dart
from figma_flutter_agent.generator.layout_navigation import (
    bottom_nav_stateful_helpers,
    render_bottom_navigation,
    render_tabs,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_screen_shell_cupertino_uses_page_scaffold() -> None:
    root, preamble = screen_shell_dart(
        body="const SizedBox.shrink()",
        theme_variant="cupertino",
        use_scaffold=True,
        title="Home",
        needs_scaler_preamble=True,
    )
    assert "CupertinoPageScaffold" in root
    assert "CupertinoNavigationBar" in root
    assert preamble


def test_bottom_nav_helpers_cupertino_use_tab_bar() -> None:
    helpers = bottom_nav_stateful_helpers(theme_variant="cupertino", node_id="some_node_id")
    assert "CupertinoTabBar(" in helpers
    assert "BottomNavigationBar(" not in helpers.split("NavigationRail")[0]


def test_render_tabs_cupertino_uses_tab_scaffold() -> None:
    node = CleanDesignTreeNode(
        id="1:1",
        name="Profile Tabs",
        type=NodeType.TABS,
        children=[
            CleanDesignTreeNode(id="1:2", name="Feed", type=NodeType.STACK, children=[]),
            CleanDesignTreeNode(id="1:3", name="Settings", type=NodeType.STACK, children=[]),
        ],
    )
    widget = render_tabs(
        ["const SizedBox.shrink()", "const Placeholder()"],
        node,
        theme_variant="cupertino",
    )
    assert "CupertinoTabScaffold" in widget
    assert "CupertinoTabBar" in widget


def test_render_bottom_navigation_material_by_default() -> None:
    node = CleanDesignTreeNode(
        id="1:10",
        name="Main Bottom Nav",
        type=NodeType.BOTTOM_NAV,
        children=[
            CleanDesignTreeNode(
                id="1:11",
                name="Home",
                type=NodeType.STACK,
                sizing=Sizing(width=24.0, height=24.0),
                children=[],
            ),
        ],
    )
    widget = render_bottom_navigation(node, uses_svg=False, theme_variant="material_3")
    assert widget.startswith("_LayoutChromeNav(")
