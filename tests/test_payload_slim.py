"""Tests for LLM payload slimming (Stream B)."""

from __future__ import annotations

from figma_flutter_agent.llm.payload_slim import (
    dump_clean_tree_for_llm,
    dump_tokens_for_llm,
    flatten_tokens_dict,
    prune_nullish,
    slim_clean_tree_dict,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    NodeStyle,
    NodeType,
    Padding,
    StackPlacement,
    TypographyToken,
)


def test_prune_nullish_drops_false_null_empty() -> None:
    raw = {
        "a": None,
        "b": False,
        "c": "",
        "d": [],
        "e": {},
        "f": "keep",
        "nested": {"g": 0, "h": None},
    }
    assert prune_nullish(raw) == {"f": "keep", "nested": {"g": 0}}


def test_slim_removes_css_properties_and_zero_geometry() -> None:
    node = {
        "id": "1:1",
        "name": "Frame",
        "type": "CONTAINER",
        "padding": {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0},
        "spacing": 0.0,
        "vectorSvgHasFilter": False,
        "style": {
            "backgroundColor": "0xFFFFFFFF",
            "cssProperties": {"background-color": "rgba(255,255,255,1)"},
            "hasStroke": False,
        },
        "children": [],
    }
    slim = slim_clean_tree_dict(node)
    assert "padding" not in slim
    assert "spacing" not in slim
    assert "vectorSvgHasFilter" not in slim
    assert "cssProperties" not in slim.get("style", {})


def test_slim_drops_offset_when_absolute_stack_placement() -> None:
    node = {
        "id": "1:3571",
        "layoutPositioning": "ABSOLUTE",
        "offsetX": -101.14,
        "offsetY": 92.0,
        "stackPlacement": {"left": -101.14, "top": 92.0, "width": 10.0, "height": 10.0},
    }
    slim = slim_clean_tree_dict(node)
    assert "offsetX" not in slim
    assert "offsetY" not in slim
    assert slim["stackPlacement"]["left"] == -101.14


def test_slim_keeps_offset_without_stack_placement() -> None:
    node = {
        "layoutPositioning": "ABSOLUTE",
        "offsetX": 1.0,
        "offsetY": 2.0,
    }
    slim = slim_clean_tree_dict(node)
    assert slim["offsetX"] == 1.0
    assert slim["offsetY"] == 2.0


def test_flatten_tokens_dict_prunes_empty_sections() -> None:
    raw = {
        "colors": {"primary": "0xFF3F414E", "color1": "0xFFFAF8F5"},
        "typography": {"body": {"fontSize": 16.0, "fontWeight": "w400"}},
        "spacing": {"md": 16.0},
        "radii": {},
        "elevations": [],
    }
    flat = flatten_tokens_dict(raw)
    assert flat["colors"]["primary"] == "0xFF3F414E"
    assert flat["typography"]["body"]["fontSize"] == 16.0
    assert flat["spacing"]["md"] == 16.0
    assert "radii" not in flat
    assert "elevations" not in flat


def test_slim_drops_default_string_fields() -> None:
    node = {
        "id": "1:1",
        "scrollAxis": "none",
        "layoutPositioning": "AUTO",
        "children": [],
    }
    slim = slim_clean_tree_dict(node)
    assert "scrollAxis" not in slim
    assert "layoutPositioning" not in slim


def test_slim_strips_duplicate_cluster_subtrees() -> None:
    heavy_child = {
        "id": "2:1",
        "name": "Icon",
        "type": "VECTOR",
        "children": [{"id": "3:1", "name": "Nested", "type": "TEXT", "text": "x"}],
    }
    root = {
        "id": "root",
        "name": "List",
        "type": "COLUMN",
        "children": [
            {
                "id": "1:1",
                "name": "Card",
                "type": "CARD",
                "clusterId": "cluster_0",
                "children": [heavy_child],
            },
            {
                "id": "1:2",
                "name": "Card",
                "type": "CARD",
                "clusterId": "cluster_0",
                "children": [heavy_child],
            },
        ],
    }
    slim = slim_clean_tree_dict(root)
    first, second = slim["children"]
    assert first.get("children")
    assert not second.get("children")


def test_dump_helpers_from_models() -> None:
    tree = CleanDesignTreeNode(
        id="1:1",
        name="Root",
        type=NodeType.STACK,
        padding=Padding(),
        spacing=0,
        style=NodeStyle(background_color="0xFF000000"),
        layout_positioning="ABSOLUTE",
        offset_x=-1.0,
        offset_y=2.0,
        stack_placement=StackPlacement(left=-1.0, top=2.0, width=100.0, height=200.0),
    )
    slim = dump_clean_tree_for_llm(tree)
    assert "offsetX" not in slim
    assert slim["stackPlacement"]["left"] == -1.0

    tokens = DesignTokens(
        colors={"primary": "0xFF000000"},
        typography={"body": TypographyToken(font_size=14, font_weight="w500")},
    )
    flat = dump_tokens_for_llm(tokens)
    assert flat["colors"]["primary"] == "0xFF000000"
    assert flat["typography"]["body"]["fontSize"] == 14
