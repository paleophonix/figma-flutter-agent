"""Tests for layout numeric rounding policy."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.parser.layout import extract_padding, extract_stack_placement
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
    geometry_precision_scope,
    round_geometry,
    round_micro_style,
)
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.parser.typography import resolve_letter_spacing


def test_round_geometry_one_decimal() -> None:
    assert round_geometry(287.466064453125) == 287.5
    assert round_geometry(20.04) == 20.0
    assert round_geometry(None) is None


def test_round_geometry_full_precision_preserves_sub_dp() -> None:
    with geometry_precision_scope("full"):
        assert round_geometry(140.56) == 140.56
        assert round_geometry(20.04) == 20.04


def test_round_geometry_standard_still_one_dp() -> None:
    with geometry_precision_scope("standard"):
        assert round_geometry(140.56) == 140.6
        assert round_geometry(287.466064453125) == 287.5


def test_round_micro_style_two_decimals() -> None:
    assert round_micro_style(0.154) == 0.15
    assert round_micro_style(1.256) == 1.26


def test_format_geometry_literal_uses_one_decimal() -> None:
    assert format_geometry_literal(20.0) == "20.0"
    assert format_geometry_literal(287.466) == "287.5"


def test_format_micro_style_literal() -> None:
    assert format_micro_style_literal(0.15) == "0.15"


def test_extract_padding_rounds() -> None:
    padding = extract_padding(
        {
            "paddingTop": 12.04,
            "paddingBottom": 8.96,
            "paddingLeft": 20.01,
            "paddingRight": 20.02,
        }
    )
    assert padding.top == 12.0
    assert padding.bottom == 9.0
    assert padding.left == 20.0
    assert padding.right == 20.0


def test_extract_stack_placement_rounds_edges() -> None:
    parent = {
        "layoutMode": "NONE",
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 414, "height": 896},
    }
    child = {
        "absoluteBoundingBox": {
            "x": 20.04,
            "y": 287.466064453125,
            "width": 373.96,
            "height": 63.04,
        },
        "constraints": {"horizontal": "LEFT", "vertical": "TOP"},
    }
    placement = extract_stack_placement(child, parent)
    assert placement is not None
    assert placement.left == 20.0
    assert placement.top == 287.5
    assert placement.width == 374.0
    assert placement.height == 63.0


def test_resolve_letter_spacing_two_decimals() -> None:
    spacing = resolve_letter_spacing({"letterSpacing": 0.154}, font_size=14.0)
    assert spacing == 0.15


def test_clean_tree_json_has_rounded_geometry() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_absolute_stack_sample.json").read_text(encoding="utf-8")
    )
    tree, _, _, _ = build_clean_tree(root)
    dumped = tree.model_dump(mode="json", by_alias=True)
    placement = dumped.get("stackPlacement")
    if placement is not None:
        for key in ("left", "top", "right", "bottom", "width", "height"):
            value = placement.get(key)
            if value is not None and isinstance(value, float):
                assert value == round(value, 1), f"{key}={value}"
