"""Tests for Tabs and BottomNavigation deterministic layout rendering."""

import json
from pathlib import Path

from figma_flutter_agent.generator.layout_renderer import render_layout_file
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, ComponentVariant, NodeType


def test_tabs_frame_from_fixture_renders_tab_controller() -> None:
    root = json.loads(Path("tests/fixtures/figma_tabs_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)

    assert tree.type == NodeType.TABS
    layout = render_layout_file(tree, feature_name="profile", uses_svg=False)[
        "lib/generated/profile_layout.dart"
    ]

    assert "DefaultTabController(" in layout
    assert "TabBar(tabs:" in layout
    assert "TabBarView(children:" in layout
    assert "Tab(text: 'General'" in layout
    assert "Tab(text: 'Security'" in layout


def test_bottom_nav_renders_navigation_bar() -> None:
    nav = CleanDesignTreeNode(
        id="1",
        name="App Bottom Nav",
        type=NodeType.BOTTOM_NAV,
        children=[
            CleanDesignTreeNode(id="2", name="Home", type=NodeType.TEXT, text="Home"),
            CleanDesignTreeNode(id="3", name="Search", type=NodeType.TEXT, text="Search"),
            CleanDesignTreeNode(id="4", name="Profile", type=NodeType.TEXT, text="Profile"),
        ],
    )

    layout = render_layout_file(nav, feature_name="shell", uses_svg=False)[
        "lib/generated/shell_layout.dart"
    ]

    assert "_LayoutChromeNav(" in layout
    assert "class _LayoutChromeNav extends StatefulWidget" in layout
    assert "NavigationRail(" in layout
    assert "setState(() => _currentIndex = index)" in layout
    assert "initialIndex: 0" in layout
    assert "label: 'Home'" in layout
    assert "label: 'Profile'" in layout
    assert "custom-code:bottom-nav" in layout


def test_bottom_nav_uses_name_based_icons() -> None:
    nav = CleanDesignTreeNode(
        id="1",
        name="App Bottom Nav",
        type=NodeType.BOTTOM_NAV,
        children=[
            CleanDesignTreeNode(id="2", name="Home Tab", type=NodeType.TEXT, text="Home"),
            CleanDesignTreeNode(id="3", name="Search Tab", type=NodeType.TEXT, text="Search"),
        ],
    )

    layout = render_layout_file(nav, feature_name="shell_icons", uses_svg=False)[
        "lib/generated/shell_icons_layout.dart"
    ]

    assert "Icons.home_outlined" in layout
    assert "Icons.search" in layout
    assert "activeIcon:" in layout


def test_bottom_nav_selected_index_from_child_variant() -> None:
    nav = CleanDesignTreeNode(
        id="1",
        name="App Bottom Nav",
        type=NodeType.BOTTOM_NAV,
        children=[
            CleanDesignTreeNode(id="2", name="Home", type=NodeType.TEXT, text="Home"),
            CleanDesignTreeNode(
                id="3",
                name="Profile",
                type=NodeType.TEXT,
                text="Profile",
                variant=ComponentVariant(
                    component_id="c1",
                    variant_properties={"State": "Selected"},
                    state="Selected",
                ),
            ),
        ],
    )

    layout = render_layout_file(nav, feature_name="shell_selected", uses_svg=False)[
        "lib/generated/shell_selected_layout.dart"
    ]

    assert "initialIndex: 1" in layout
