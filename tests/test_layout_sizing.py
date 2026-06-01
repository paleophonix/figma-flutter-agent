"""Tests for Figma layoutGrow and sizing extraction."""

from figma_flutter_agent.parser.layout import (
    enforce_fixed_sizing_for_stack_and_button,
    extract_sizing,
)
from figma_flutter_agent.schemas import NodeType, Sizing, SizingMode, StackPlacement


def test_layout_grow_fills_counter_axis_in_horizontal_parent() -> None:
    child = {
        "layoutGrow": 1,
        "layoutSizingHorizontal": "HUG",
        "layoutSizingVertical": "HUG",
    }
    parent = {"layoutMode": "HORIZONTAL"}

    sizing = extract_sizing(child, parent=parent)

    assert sizing.width_mode == SizingMode.HUG
    assert sizing.height_mode == SizingMode.FILL


def test_layout_grow_fills_counter_axis_in_vertical_parent() -> None:
    child = {
        "layoutGrow": 1,
        "layoutSizingHorizontal": "HUG",
        "layoutSizingVertical": "HUG",
    }
    parent = {"layoutMode": "VERTICAL"}

    sizing = extract_sizing(child, parent=parent)

    assert sizing.width_mode == SizingMode.FILL
    assert sizing.height_mode == SizingMode.HUG


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
