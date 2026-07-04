"""Regression tests for food_menu_2 profile-screen emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.geometry.text_metrics import (
    placement_is_right_edge_pinned,
    positioned_text_preserves_right_edge,
    positioned_text_width_with_metric_slack,
)
from figma_flutter_agent.generator.layout.widgets.button.core import (
    render_compact_icon_host_stack_body,
)
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.flex_sizing import (
    _button_absolute_slot_stack_body,
)
from figma_flutter_agent.parser.interaction import (
    button_has_absolute_slot_children,
    button_has_icon_label_inline_affordance,
    compact_icon_host_layers,
    compact_icon_host_tap_role,
    stack_action_intent_vetoes_input,
    stack_interaction_kind,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_FIXTURE = Path("tests/fixtures/layouts/extracted/food_menu_2/processed.json")


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def _load_menu_root() -> CleanDesignTreeNode:
    if not _FIXTURE.is_file():
        pytest.skip("food_menu_2 fixture unavailable")
    processed = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def test_withdraw_stack_is_button_not_input() -> None:
    root = _load_menu_root()
    withdraw = _find_node(root, "602:753")
    assert withdraw is not None
    assert stack_interaction_kind(withdraw) == "button"
    assert stack_action_intent_vetoes_input(withdraw)


def test_disclosure_menu_rows_are_buttons_not_inputs() -> None:
    root = _load_menu_root()
    for node_id in ("602:788", "602:806"):
        row = _find_node(root, node_id)
        assert row is not None, node_id
        assert stack_interaction_kind(row) == "button", node_id
        assert stack_action_intent_vetoes_input(row), node_id


def test_withdraw_stack_does_not_emit_textfield() -> None:
    root = _load_menu_root()
    withdraw = _find_node(root, "602:753")
    assert withdraw is not None
    dart = render_node_body(withdraw, uses_svg=True, theme_variant="material")
    assert "TextField" not in dart
    assert "InkWell" in dart or "onTap" in dart


def test_profile_icon_host_emits_foreground_glyph_not_back_nav() -> None:
    root = _load_menu_root()
    icon_button = _find_node(root, "602:768")
    assert icon_button is not None
    plate, foreground = compact_icon_host_layers(icon_button)
    assert plate is not None
    assert foreground is not None
    assert "profile" in (foreground.name or "").lower()
    assert compact_icon_host_tap_role(icon_button, foreground=foreground) == "button-action"
    body = render_compact_icon_host_stack_body(icon_button, uses_svg=True)
    assert body is not None
    assert "icon_profile" in body
    assert "ellipse_1" in body


def test_withdrawal_history_preserves_absolute_slots_not_inline_row() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:825")
    assert row is not None
    assert button_has_absolute_slot_children(row)
    assert not button_has_icon_label_inline_affordance(row)
    dart = render_node_body(row, uses_svg=True, theme_variant="material")
    assert "MainAxisAlignment.center" not in dart
    assert "Stack(" in dart


def test_right_pinned_value_text_reflows_from_right_edge() -> None:
    root = _load_menu_root()
    value = _find_node(root, "602:837")
    assert value is not None
    placement = value.stack_placement
    assert placement is not None
    parent = _find_node(root, "602:836")
    assert parent is not None
    parent_width = float(parent.sizing.width or 0.0)
    figma_width = float(value.sizing.width or 0.0)
    assert placement_is_right_edge_pinned(
        placement,
        parent_width=parent_width,
        figma_width=figma_width,
    )
    slack_width = positioned_text_width_with_metric_slack(figma_width)
    assert positioned_text_preserves_right_edge(
        value,
        placement,
        parent_width=parent_width,
        figma_width=figma_width,
    )
    adjusted_left = parent_width - slack_width
    assert adjusted_left < float(placement.left or 0.0)


def test_absolute_slot_row_body_uses_stack() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:825")
    assert row is not None
    widgets = ["const Text('Withdrawal History')", "const SizedBox.shrink()"]
    body = _button_absolute_slot_stack_body(row, widgets)
    assert "Stack(" in body
    assert "MainAxisAlignment.center" not in body
