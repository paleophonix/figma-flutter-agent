"""Emit laws for light_theme_06 viewport, carousel, and section header."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.generator.layout.widgets.positioned import (
    _positioned_fields,
    _should_pin_bottom,
)
from figma_flutter_agent.generator.normalize import reconcile_layout_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, StackPlacement

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROCESSED = _REPO_ROOT / ".debug" / "screen" / "limbo" / "light_theme_06" / "processed.json"


def _light_theme_tree() -> CleanDesignTreeNode:
    if not _PROCESSED.is_file():
        pytest.skip("light_theme_06 processed dump not present")
    payload = json.loads(_PROCESSED.read_text(encoding="utf-8"))
    return reconcile_layout_tree(CleanDesignTreeNode.model_validate(payload["cleanTree"]))


def _scroll_group_placement() -> StackPlacement:
    tree = _light_theme_tree()
    scroll = next(child for child in tree.children if child.name == "Scroll_group")
    placement = scroll.stack_placement
    assert placement is not None
    return placement


def test_tall_top_anchored_scroll_body_must_not_auto_bottom_pin() -> None:
    """Law: tall_top_anchored_scroll_body_must_not_auto_bottom_pin."""
    placement = _scroll_group_placement()
    parent_height = 844.0
    assert not _should_pin_bottom(placement, parent_height=parent_height)
    fields = ", ".join(_positioned_fields(placement, parent_height=parent_height))
    assert "top: 120.0" in fields
    assert "bottom:" not in fields


def test_bottom_docked_footer_still_pins_bottom() -> None:
    """Docked footer chrome must keep bottom pin."""
    placement = StackPlacement(vertical="BOTTOM", top=738.0, width=390.0, height=106.0)
    assert _should_pin_bottom(placement, parent_height=844.0)
    fields = ", ".join(_positioned_fields(placement, parent_height=844.0))
    assert "bottom: 0.0" in fields
    assert "top:" not in fields


def test_light_theme_layout_initial_viewport_pins_scroll_body_to_top() -> None:
    """Law: light_theme_06_initial_viewport_regression_gate."""
    tree = _light_theme_tree()
    layout = render_layout_file(
        tree,
        feature_name="light_theme_06",
        package_name="inbox",
        uses_svg=True,
        use_geometry_planner=True,
    )["lib/generated/light_theme_06_layout.dart"]
    compact = layout.replace("\n", "")
    assert "Page title" in layout
    assert "bottom: 0.0, height: 1448.0" not in compact
    assert "top: 120.0" in compact
    assert "scrollDirection: Axis.horizontal" in layout
    assert "SECTION HEADER" in layout


def test_light_theme_carousel_host_is_horizontally_scrollable() -> None:
    """Law: carousel_is_scrollable."""
    tree = _light_theme_tree()

    def find_slider(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if node.name == "Content row slider":
            return node
        for child in node.children:
            found = find_slider(child)
            if found is not None:
                return found
        return None

    slider = find_slider(tree)
    assert slider is not None
    body = render_node_body(slider, uses_svg=True, parent_type=NodeType.COLUMN).replace("\n", "")
    assert "ListView(" in body or "SingleChildScrollView(" in body
    assert "scrollDirection: Axis.horizontal" in body


def test_light_theme_section_header_row_preserves_full_title_width() -> None:
    """Law: section_header_title_must_preserve_full_text_and_available_width."""
    tree = _light_theme_tree()

    def find_section_header_row(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
        if node.type == NodeType.ROW and node.name == "Section Header":
            return node
        for child in node.children:
            found = find_section_header_row(child)
            if found is not None:
                return found
        return None

    row = find_section_header_row(tree)
    assert row is not None
    body = render_node_body(row, uses_svg=False, parent_type=NodeType.COLUMN).replace("\n", "")
    assert "SECTION HEADER" in body
    assert "Expanded(child:" in body
    assert "BoxConstraints(minHeight: 24.0)" in body
    assert "SizedBox(height: 24.0" not in body
