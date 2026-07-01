"""Tests for Figma layoutGrow and sizing extraction."""

from figma_flutter_agent.parser.layout import (
    enforce_fixed_sizing_for_stack_and_button,
    extract_sizing,
)
from figma_flutter_agent.schemas import NodeType, Sizing, SizingMode, StackPlacement


def test_layout_grow_fills_primary_axis_in_horizontal_parent() -> None:
    child = {
        "layoutGrow": 1,
        "layoutSizingHorizontal": "HUG",
        "layoutSizingVertical": "HUG",
    }
    parent = {"layoutMode": "HORIZONTAL"}

    sizing = extract_sizing(child, parent=parent)

    assert sizing.width_mode == SizingMode.FILL
    assert sizing.height_mode == SizingMode.HUG


def test_layout_grow_fills_primary_axis_in_vertical_parent() -> None:
    child = {
        "layoutGrow": 1,
        "layoutSizingHorizontal": "HUG",
        "layoutSizingVertical": "HUG",
    }
    parent = {"layoutMode": "VERTICAL"}

    sizing = extract_sizing(child, parent=parent)

    assert sizing.width_mode == SizingMode.HUG
    assert sizing.height_mode == SizingMode.FILL


def test_enforce_fixed_sizing_rewrites_stack_hug_modes() -> None:
    sizing = Sizing(width_mode=SizingMode.HUG, height_mode=SizingMode.HUG)
    figma_node = {"absoluteBoundingBox": {"width": 120.0, "height": 48.0}}
    placement = StackPlacement(width=120.0, height=48.0)

    fixed = enforce_fixed_sizing_for_stack_and_button(
        NodeType.STACK,
        sizing,
        stack_placement=placement,
        figma_node=figma_node,
    )

    assert fixed.width_mode == SizingMode.FIXED
    assert fixed.height_mode == SizingMode.FIXED
    assert fixed.width == 120.0
    assert fixed.height == 48.0


def test_hug_vertical_extent_excludes_absolute_children() -> None:
    """Law: absolute_children_must_not_contribute_to_flex_hug_extent."""
    from figma_flutter_agent.parser.layout.sizing import adjust_sizing_for_visible_children

    frame = {
        "layoutMode": "VERTICAL",
        "layoutSizingVertical": "HUG",
        "paddingTop": 24.0,
        "paddingBottom": 24.0,
        "itemSpacing": 24.0,
        "children": [
            {
                "visible": True,
                "absoluteBoundingBox": {"height": 34.0},
            },
            {
                "visible": True,
                "absoluteBoundingBox": {"height": 71.0},
            },
            {
                "visible": True,
                "layoutPositioning": "ABSOLUTE",
                "absoluteBoundingBox": {"height": 320.5},
            },
        ],
    }
    sizing = Sizing(width_mode=SizingMode.FIXED, height_mode=SizingMode.HUG)
    adjusted = adjust_sizing_for_visible_children(frame, sizing)
    assert adjusted.height == 177.0
    assert adjusted.height_mode == SizingMode.FIXED


def test_extract_sizing_min_max_from_figma_json() -> None:
    node = {
        "absoluteBoundingBox": {"width": 200.0, "height": 100.0},
        "minWidth": 120.0,
        "maxWidth": 320.0,
        "minHeight": 80.0,
        "maxHeight": 240.0,
    }
    sizing = extract_sizing(node)
    assert sizing.min_width == 120.0
    assert sizing.max_width == 320.0
    assert sizing.min_height == 80.0
    assert sizing.max_height == 240.0
