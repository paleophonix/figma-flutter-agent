"""Tests for Figma layoutGrow and sizing extraction."""

from figma_flutter_agent.parser.layout import extract_sizing
from figma_flutter_agent.schemas import SizingMode


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
