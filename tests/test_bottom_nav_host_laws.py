"""Regression tests for bottom-nav host scope and item collection laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.generator.layout.navigation.items import collect_bottom_nav_items
from figma_flutter_agent.parser.components import (
    match_semantic_type_from_name_fallback,
    raw_looks_like_bottom_nav_dock,
)
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _screen_named_bottom_navigation_raw() -> dict:
    return {
        "type": "FRAME",
        "id": "7342:2818",
        "name": "9 - A - Home - Bottom Navigation",
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 430.0, "height": 932.0},
        "children": [
            {
                "type": "TEXT",
                "id": "7342:2826",
                "name": "Food Last Week",
                "characters": "Food Last Week",
                "absoluteBoundingBox": {"width": 116.0, "height": 18.0},
            },
            {
                "type": "TEXT",
                "id": "7342:2875",
                "name": "Total Balance",
                "characters": "Total Balance",
                "absoluteBoundingBox": {"width": 116.0, "height": 18.0},
            },
            {
                "type": "FRAME",
                "id": "7342:2879",
                "name": "Bottom Navigation - Light Mode",
                "absoluteBoundingBox": {"x": 0, "y": 824.0, "width": 430.0, "height": 108.0},
                "children": [
                    {
                        "type": "FRAME",
                        "id": "I7342:2879;7045:344",
                        "name": "Home",
                        "absoluteBoundingBox": {"width": 57.0, "height": 53.0},
                        "children": [
                            {
                                "type": "VECTOR",
                                "id": "home-vec",
                                "name": "Vector",
                                "absoluteBoundingBox": {"width": 22.0, "height": 22.0},
                            }
                        ],
                    },
                    {
                        "type": "FRAME",
                        "id": "I7342:2879;7045:346",
                        "name": "Analysis",
                        "absoluteBoundingBox": {"width": 57.0, "height": 53.0},
                        "children": [
                            {
                                "type": "VECTOR",
                                "id": "analysis-vec",
                                "name": "Vector",
                                "absoluteBoundingBox": {"width": 22.0, "height": 22.0},
                            }
                        ],
                    },
                    {
                        "type": "FRAME",
                        "id": "I7342:2879;7045:348",
                        "name": "Transactions",
                        "absoluteBoundingBox": {"width": 57.0, "height": 53.0},
                        "children": [
                            {
                                "type": "VECTOR",
                                "id": "tx-vec",
                                "name": "Vector",
                                "absoluteBoundingBox": {"width": 22.0, "height": 22.0},
                            }
                        ],
                    },
                    {
                        "type": "FRAME",
                        "id": "I7342:2879;7045:350",
                        "name": "Category",
                        "absoluteBoundingBox": {"width": 57.0, "height": 53.0},
                        "children": [
                            {
                                "type": "VECTOR",
                                "id": "cat-vec",
                                "name": "Vector",
                                "absoluteBoundingBox": {"width": 22.0, "height": 22.0},
                            }
                        ],
                    },
                    {
                        "type": "FRAME",
                        "id": "I7342:2879;7045:352",
                        "name": "Profile",
                        "absoluteBoundingBox": {"width": 57.0, "height": 53.0},
                        "children": [
                            {
                                "type": "VECTOR",
                                "id": "profile-vec",
                                "name": "Vector",
                                "absoluteBoundingBox": {"width": 22.0, "height": 22.0},
                            }
                        ],
                    },
                ],
            },
        ],
    }


def test_viewport_sized_frame_rejects_bottom_nav_name_fallback() -> None:
    screen = _screen_named_bottom_navigation_raw()
    assert match_semantic_type_from_name_fallback(screen, screen["name"]) is None
    assert raw_looks_like_bottom_nav_dock(screen) is False


def test_screen_name_containing_bottom_navigation_is_not_bottom_nav() -> None:
    tree, _, _, _ = build_clean_tree(_screen_named_bottom_navigation_raw())
    assert tree.type != NodeType.BOTTOM_NAV
    assert tree.type in {NodeType.STACK, NodeType.COLUMN, NodeType.GRID}


def test_oversized_host_prefers_nested_bottom_nav_items() -> None:
    debug_root = Path(".debug/screen/limbo/9_a_home_bottom_navigation")
    if not (debug_root / "processed.json").is_file():
        pytest.skip("home bottom navigation debug bundle unavailable")
    proc = json.loads((debug_root / "processed.json").read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(proc["cleanTree"])
    if root.type != NodeType.BOTTOM_NAV:
        pytest.skip("processed tree no longer reproduces oversized bottom-nav host")
    items = collect_bottom_nav_items(root)
    assert 2 <= len(items) <= 7
    assert all(item.name not in {"Total Balance", "Food Last Week", "Groceries"} for item in items)


def test_oversized_bottom_nav_host_rejects_screen_text_children() -> None:
    host = CleanDesignTreeNode(
        id="screen",
        name="9 - A - Home - Bottom Navigation",
        type=NodeType.BOTTOM_NAV,
        sizing=Sizing(width=430.0, height=932.0),
        children=[
            CleanDesignTreeNode(
                id="t1",
                name="Total Balance",
                type=NodeType.TEXT,
                text="Total Balance",
            ),
            CleanDesignTreeNode(
                id="t2",
                name="Groceries",
                type=NodeType.TEXT,
                text="Groceries",
            ),
            CleanDesignTreeNode(
                id="t3",
                name="Rent",
                type=NodeType.TEXT,
                text="Rent",
            ),
        ],
    )
    assert collect_bottom_nav_items(host) == []


def test_validate_screen_ir_rejects_nav_bottom_bar_on_screen_frame() -> None:
    root = CleanDesignTreeNode(
        id="7342:2818",
        name="9 - A - Home - Bottom Navigation",
        type=NodeType.STACK,
        sizing=Sizing(width=430.0, height=932.0),
        children=[
            CleanDesignTreeNode(
                id="7342:2826",
                name="Food Last Week",
                type=NodeType.TEXT,
                text="Food Last Week",
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="7342:2818",
            kind=WidgetIrKind.NAV_BOTTOM_BAR,
            children=[],
        )
    )
    with pytest.raises(GenerationError, match="nav_bottom_bar"):
        validate_screen_ir(screen_ir, root, apply_guards=False)


def test_compact_bottom_nav_still_collects_text_tabs() -> None:
    nav = CleanDesignTreeNode(
        id="nav",
        name="App Bottom Nav",
        type=NodeType.BOTTOM_NAV,
        sizing=Sizing(width=390.0, height=72.0),
        children=[
            CleanDesignTreeNode(id="home", name="Home", type=NodeType.TEXT, text="Home"),
            CleanDesignTreeNode(id="search", name="Search", type=NodeType.TEXT, text="Search"),
            CleanDesignTreeNode(id="profile", name="Profile", type=NodeType.TEXT, text="Profile"),
        ],
    )
    items = collect_bottom_nav_items(nav)
    assert len(items) == 3


def test_nested_icon_tabs_resolve_from_oversized_host() -> None:
    def icon_tab(tab_id: str, *, left: float, name: str) -> CleanDesignTreeNode:
        return CleanDesignTreeNode(
            id=tab_id,
            name=name,
            type=NodeType.STACK,
            sizing=Sizing(width=57.0, height=53.0),
            stack_placement=StackPlacement(left=left, top=24.0, width=57.0, height=53.0),
            children=[
                CleanDesignTreeNode(
                    id=f"{tab_id}-vec",
                    name="Vector",
                    type=NodeType.VECTOR,
                    vector_asset_key=f"assets/icons/{tab_id}.svg",
                    sizing=Sizing(width=22.0, height=22.0),
                ),
            ],
        )

    host = CleanDesignTreeNode(
        id="screen",
        name="Home - Bottom Navigation",
        type=NodeType.BOTTOM_NAV,
        sizing=Sizing(width=430.0, height=932.0),
        children=[
            CleanDesignTreeNode(
                id="copy",
                name="Total Balance",
                type=NodeType.TEXT,
                text="Total Balance",
            ),
            CleanDesignTreeNode(
                id="nav",
                name="Bottom Navigation - Light Mode",
                type=NodeType.BOTTOM_NAV,
                sizing=Sizing(width=430.0, height=108.0),
                stack_placement=StackPlacement(top=824.0, width=430.0, height=108.0),
                children=[
                    icon_tab("home", left=36.0, name="Home"),
                    icon_tab("analysis", left=120.0, name="Analysis"),
                    icon_tab("tx", left=204.0, name="Transactions"),
                    icon_tab("cat", left=288.0, name="Category"),
                    icon_tab("profile", left=360.0, name="Profile"),
                ],
            ),
        ],
    )
    items = collect_bottom_nav_items(host)
    assert len(items) == 5
    assert items[0].name == "Home"
    assert items[-1].name == "Profile"
