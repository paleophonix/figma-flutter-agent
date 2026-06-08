"""Tests for Tabs and BottomNavigation deterministic layout rendering."""

import json
from pathlib import Path

from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_planned_widget_syntax
from figma_flutter_agent.generator.layout.navigation.chrome import (
    ensure_layout_chrome_nav_helpers,
)
from figma_flutter_agent.generator.layout import render_layout_file, render_widget_file
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


def test_widget_file_includes_layout_chrome_nav_helpers() -> None:
    body = (
        "_LayoutChromeNav(initialIndex: 0, items: ["
        "BottomNavigationBarItem(icon: const Icon(Icons.home_outlined), "
        "activeIcon: const Icon(Icons.home_outlined), label: 'Home')"
        "])"
    )
    source = render_widget_file(
        class_name="BottomnavbarWidget",
        body=body,
        uses_svg=False,
        package_name="ataev",
        source_file="lib/widgets/bottomnavbar_widget.dart",
    )

    assert source.count("class _LayoutChromeNav extends StatefulWidget") == 1
    assert "class BottomnavbarWidget extends StatelessWidget" in source
    assert "theme/app_layout.dart" in source


def test_ensure_layout_chrome_nav_helpers_repairs_llm_widget_file() -> None:
    broken = """import 'package:flutter/material.dart';

class BottomnavbarWidget extends StatelessWidget {
  const BottomnavbarWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return _LayoutChromeNav(initialIndex: 0, items: const []);
  }
}
"""
    fixed = ensure_layout_chrome_nav_helpers(broken, theme_variant="material_3")

    assert "class _LayoutChromeNav extends StatefulWidget" in fixed
    assert "theme/app_layout.dart" in fixed


def test_sanitize_planned_widget_syntax_injects_layout_chrome_nav_helpers() -> None:
    broken = """import 'package:flutter/material.dart';
import 'package:ataev/theme/app_colors.dart';

class BottomnavbarWidget extends StatelessWidget {
  const BottomnavbarWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      ignoring: true,
      child: _LayoutChromeNav(initialIndex: 0, items: const []),
    );
  }
}
"""
    fixed = sanitize_planned_widget_syntax(broken)

    assert "class _LayoutChromeNav extends StatefulWidget" in fixed


def test_bottom_nav_unwraps_row_container_children() -> None:
    nav = CleanDesignTreeNode(
        id="nav",
        name="BottomNavBar",
        type=NodeType.BOTTOM_NAV,
        children=[
            CleanDesignTreeNode(
                id="wrap",
                name="Container",
                type=NodeType.ROW,
                children=[
                    CleanDesignTreeNode(
                        id="row",
                        name="Frame 20",
                        type=NodeType.ROW,
                        children=[
                            CleanDesignTreeNode(
                                id="1",
                                name="Link",
                                type=NodeType.COLUMN,
                                children=[
                                    CleanDesignTreeNode(
                                        id="1t",
                                        name="Home",
                                        type=NodeType.TEXT,
                                        text="Главная",
                                    )
                                ],
                            ),
                            CleanDesignTreeNode(
                                id="2",
                                name="Link",
                                type=NodeType.COLUMN,
                                children=[
                                    CleanDesignTreeNode(
                                        id="2t",
                                        name="Catalog",
                                        type=NodeType.TEXT,
                                        text="Каталог",
                                    )
                                ],
                            ),
                            CleanDesignTreeNode(
                                id="3",
                                name="Link",
                                type=NodeType.COLUMN,
                                children=[
                                    CleanDesignTreeNode(
                                        id="3t",
                                        name="Cart",
                                        type=NodeType.TEXT,
                                        text="Корзина",
                                    )
                                ],
                            ),
                            CleanDesignTreeNode(
                                id="4",
                                name="Link",
                                type=NodeType.COLUMN,
                                children=[
                                    CleanDesignTreeNode(
                                        id="4t",
                                        name="Profile",
                                        type=NodeType.TEXT,
                                        text="Профиль",
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    layout = render_layout_file(nav, feature_name="partner", uses_svg=False)[
        "lib/generated/partner_layout.dart"
    ]

    assert "label: 'Главная'" in layout
    assert "label: 'Каталог'" in layout
    assert "label: 'Корзина'" in layout
    assert "label: 'Профиль'" in layout
    assert layout.count("BottomNavigationBarItem(") == 4
    assert "label: 'Главная'" in layout


def test_bottom_nav_label_from_nested_text_column() -> None:
    nav = CleanDesignTreeNode(
        id="nav",
        name="BottomNavBar",
        type=NodeType.BOTTOM_NAV,
        children=[
            CleanDesignTreeNode(
                id="wrap",
                name="Container",
                type=NodeType.ROW,
                children=[
                    CleanDesignTreeNode(
                        id="link",
                        name="Link",
                        type=NodeType.COLUMN,
                        children=[
                            CleanDesignTreeNode(
                                id="wrap2",
                                name="Container",
                                type=NodeType.COLUMN,
                                children=[
                                    CleanDesignTreeNode(
                                        id="text",
                                        name="Главная",
                                        type=NodeType.TEXT,
                                        text="Главная",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )
    layout = render_layout_file(nav, feature_name="nested_nav", uses_svg=False)[
        "lib/generated/nested_nav_layout.dart"
    ]
    assert "label: 'Главная'" in layout
    assert "label: 'Link'" not in layout


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


def test_render_layout_file_chunk_includes_pill_nav_helpers(monkeypatch) -> None:
    """Chunk files that emit _LayoutPillNav must include private nav helper classes."""
    from figma_flutter_agent.generator.chunking import CHUNK_TARGET_BYTES
    from figma_flutter_agent.schemas import NodeStyle, Sizing, SizingMode

    def _compact_nav_tab(label: str) -> CleanDesignTreeNode:
        return CleanDesignTreeNode(
            id=f"tab-{label}",
            name="Link",
            type=NodeType.COLUMN,
            padding={"top": 6.0, "bottom": 6.0, "left": 16.0, "right": 16.0},
            sizing=Sizing(width=80.0, height=49.0),
            children=[
                CleanDesignTreeNode(
                    id=f"text-{label}",
                    name="Label",
                    type=NodeType.TEXT,
                    text=label,
                    style=NodeStyle(font_size=12.0),
                ),
                *[
                    CleanDesignTreeNode(
                        id=f"pad-{label}-{index}",
                        name=f"pad-{index}",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=4.0, height=4.0),
                    )
                    for index in range(24)
                ],
            ],
        )

    nav = CleanDesignTreeNode(
        id="610:nav",
        name="BottomNavBar",
        type=NodeType.BOTTOM_NAV,
        style=NodeStyle(
            background_color="0xFFFFFFFF",
            border_radius_corners={
                "topLeft": 32.0,
                "topRight": 32.0,
                "bottomLeft": 0.0,
                "bottomRight": 0.0,
            },
        ),
        sizing=Sizing(width=390.0, height=113.0),
        children=[
            CleanDesignTreeNode(
                id="610:row",
                name="Container",
                type=NodeType.ROW,
                sizing=Sizing(width_mode=SizingMode.FILL, width=390.0, height=81.0),
                children=[
                    _compact_nav_tab("Главная"),
                    _compact_nav_tab("Каталог"),
                    _compact_nav_tab("Корзина"),
                    _compact_nav_tab("Профиль"),
                ],
            )
        ],
    )
    monkeypatch.setattr(
        "figma_flutter_agent.generator.chunking.CHUNK_TARGET_BYTES",
        max(2048, CHUNK_TARGET_BYTES // 8),
    )
    screen = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=844.0),
        children=[nav],
    )
    files = render_layout_file(screen, feature_name="pill_nav_chunk", uses_svg=True)
    chunk_sources = [
        content for path, content in files.items() if "chunk" in path
    ]
    assert chunk_sources, "Expected bottom nav host to be extracted into a chunk file"
    pill_chunk = next(
        content for content in chunk_sources if "_LayoutPillNav(" in content
    )
    assert "class _LayoutPillNav extends StatefulWidget" in pill_chunk
    assert "class _PillNavTabSpec" in pill_chunk
    assert "import 'package:flutter_svg/flutter_svg.dart';" in pill_chunk
