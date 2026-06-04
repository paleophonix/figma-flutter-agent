"""Tests for Figma name-hint semantic type validation."""

from figma_flutter_agent.parser.components import (
    match_semantic_type_from_name,
    match_semantic_type_from_name_fallback,
)
from figma_flutter_agent.schemas import NodeType


def test_bottom_navbar_name_maps_to_bottom_nav() -> None:
    assert match_semantic_type_from_name("BottomNavBar") == NodeType.BOTTOM_NAV


def test_misnamed_bottom_navbar_cta_footer_is_not_bottom_nav() -> None:
    footer = {
        "type": "FRAME",
        "name": "BottomNavBar",
        "absoluteBoundingBox": {"width": 390.0, "height": 106.0},
        "children": [
            {
                "type": "FRAME",
                "name": "Container",
                "absoluteBoundingBox": {"width": 390.0, "height": 106.0},
                "children": [
                    {
                        "type": "FRAME",
                        "name": "Frame 46",
                        "absoluteBoundingBox": {"width": 336.5, "height": 56.0},
                        "children": [
                            {
                                "type": "FRAME",
                                "name": "Button",
                                "absoluteBoundingBox": {"width": 336.5, "height": 56.0},
                                "children": [
                                    {
                                        "type": "TEXT",
                                        "name": "Save",
                                        "characters": "Save",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    assert match_semantic_type_from_name_fallback(footer, "BottomNavBar") is None


def test_real_bottom_nav_with_multiple_tabs_still_matches() -> None:
    nav = {
        "type": "FRAME",
        "name": "App Bottom Nav",
        "absoluteBoundingBox": {"width": 390.0, "height": 72.0},
        "children": [
            {
                "type": "FRAME",
                "name": "Home Tab",
                "absoluteBoundingBox": {"width": 48.0, "height": 48.0},
                "children": [{"type": "TEXT", "name": "Home", "characters": "Home"}],
            },
            {
                "type": "FRAME",
                "name": "Search Tab",
                "absoluteBoundingBox": {"width": 48.0, "height": 48.0},
                "children": [{"type": "TEXT", "name": "Search", "characters": "Search"}],
            },
            {
                "type": "FRAME",
                "name": "Profile Tab",
                "absoluteBoundingBox": {"width": 48.0, "height": 48.0},
                "children": [{"type": "TEXT", "name": "Profile", "characters": "Profile"}],
            },
        ],
    }
    assert match_semantic_type_from_name_fallback(nav, "App Bottom Nav") == NodeType.BOTTOM_NAV
