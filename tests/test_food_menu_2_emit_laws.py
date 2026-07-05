"""Regression tests for food_menu_2 profile-screen emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.geometry.text_metrics import (
    placement_is_fill_width_centered_text,
    placement_is_right_edge_pinned,
    positioned_text_allows_metric_slack,
    positioned_text_preserves_right_edge,
    positioned_text_width_with_metric_slack,
)
from figma_flutter_agent.generator.layout.widget_roots import (
    finalize_extracted_widget_body,
    validate_widget_build_has_no_parent_data_root,
)
from figma_flutter_agent.generator.layout.widgets.button.core import (
    _button_ink_surface_params,
    render_compact_icon_host_stack_body,
)
from figma_flutter_agent.generator.layout.widgets.emit.dispatch import render_node_body
from figma_flutter_agent.generator.layout.widgets.flex_sizing import (
    _button_absolute_slot_stack_body,
)
from figma_flutter_agent.generator.layout.widgets.svg import _render_svg_picture
from figma_flutter_agent.parser.interaction import (
    button_has_absolute_slot_children,
    button_has_icon_label_inline_affordance,
    compact_icon_host_layers,
    compact_icon_host_tap_role,
    layout_fact_checkbox_control,
    layout_fact_directional_glyph_host,
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
    widgets = ["const Text('x')"] * len(row.children)
    body = _button_absolute_slot_stack_body(row, widgets)
    assert "Stack(" in body
    assert "MainAxisAlignment.center" not in body


def test_extracted_widget_body_strips_positioned_root() -> None:
    wrapped = (
        "Positioned(left: 15.0, top: 15.0, width: 296.0, height: 48.0, "
        "child: ClipRect(child: const Text('Log Out')))"
    )
    stripped = finalize_extracted_widget_body(wrapped)
    assert not stripped.startswith("Positioned(")
    source = (
        "class Group3304Widget extends StatelessWidget {\n"
        "  const Group3304Widget({super.key});\n"
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        f"    return {stripped};\n"
        "  }\n"
        "}\n"
    )
    assert validate_widget_build_has_no_parent_data_root(source) == []


def test_trailing_chevron_hosts_veto_checkbox_classification() -> None:
    root = _load_menu_root()
    for node_id in ("602:775", "602:809"):
        node = _find_node(root, node_id)
        assert node is not None, node_id
        assert layout_fact_directional_glyph_host(node), node_id
        assert not layout_fact_checkbox_control(node), node_id


def test_balance_text_fill_width_centered_skips_metric_slack() -> None:
    root = _load_menu_root()
    balance = _find_node(root, "602:758")
    assert balance is not None
    placement = balance.stack_placement
    assert placement is not None
    assert placement_is_fill_width_centered_text(balance, placement)
    assert not positioned_text_allows_metric_slack(balance, placement)
    dart = render_node_body(balance, uses_svg=True, theme_variant="material")
    assert "left: -" not in dart


def test_withdraw_outlined_button_has_no_synthetic_fill() -> None:
    root = _load_menu_root()
    withdraw = _find_node(root, "602:753")
    assert withdraw is not None
    surface = _find_node(root, "602:754")
    assert surface is not None
    fill, border, _shadows, _gradient, _inner = _button_ink_surface_params(surface)
    assert fill is None
    assert border is not None
    dart = render_node_body(withdraw, uses_svg=True, theme_variant="material")
    assert "colorScheme.onPrimary" not in dart
    assert "color: const Color(0xFFFFFFFF)" not in dart


def test_compact_icon_host_plate_uses_host_extent() -> None:
    root = _load_menu_root()
    icon_button = _find_node(root, "602:768")
    assert icon_button is not None
    body = render_compact_icon_host_stack_body(icon_button, uses_svg=True)
    assert body is not None
    assert "width: 48.0" in body
    assert "height: 48.0" in body
    assert "ellipse_1" in body


def test_absolute_slot_row_reconstructs_positioned_children() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:825")
    assert row is not None
    assert button_has_absolute_slot_children(row)
    child_widgets = [
        "const Text('Withdrawal History')",
        "SvgPicture.asset('assets/icons/chevron-right.svg')",
        "SvgPicture.asset('assets/icons/ellipse.svg')",
    ]
    body = _button_absolute_slot_stack_body(row, child_widgets[: len(row.children)])
    assert body.count("Positioned(") >= 2


def test_command_icon_host_vetoes_checkbox_classification() -> None:
    root = _load_menu_root()
    command = _find_node(root, "602:821")
    assert command is not None
    assert command.vector_asset_key is not None
    assert not layout_fact_checkbox_control(command)


def test_user_reviews_row_emits_command_glyph_not_checkbox() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:806")
    assert row is not None
    dart = render_node_body(row, uses_svg=True, theme_variant="material")
    assert "command_602_821" in dart
    assert "_GeneratedToggleCheckbox" not in dart


def test_log_out_row_preserves_full_cover_surface() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:788")
    assert row is not None
    dart = render_node_body(row, uses_svg=True, theme_variant="material")
    assert "0xFFF6F6F6" in dart
    assert "width: 327.0" in dart
    assert "height: 78.0" in dart
    assert "figma-602_789" in dart


def test_withdrawal_history_row_emits_foreground_glyph() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:825")
    assert row is not None
    dart = render_node_body(row, uses_svg=True, theme_variant="material")
    assert "ellipse_1_602_828" in dart
    assert "vector_602_832" in dart


def test_trailing_chevron_component_uses_action_slot_extent() -> None:
    root = _load_menu_root()
    chevron_host = _find_node(root, "602:774")
    assert chevron_host is not None
    dart = _render_svg_picture(chevron_host, "assets/icons/chevron-right_602_775.svg")
    assert "width: 30.0, height: 30.0" in dart
    assert "width: 5.0, height: 10.0" not in dart


def test_log_out_download_glyph_uses_slot_extent() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:788")
    assert row is not None
    dart = render_node_body(row, uses_svg=True, theme_variant="material")
    assert "download_602_802.svg', width: 24.0, height: 24.0" in dart
    assert "width: 1.6, height: 12.0" not in dart


def test_log_out_trailing_icon_slot_uses_button_action_not_back_nav() -> None:
    root = _load_menu_root()
    slot = _find_node(root, "602:795")
    assert slot is not None
    dart = render_node_body(slot, uses_svg=True, theme_variant="material")
    assert "back-nav" not in dart
    assert "button-action" in dart


def test_number_of_orders_receipt_glyph_uses_24_extent() -> None:
    root = _load_menu_root()
    row = _find_node(root, "602:836")
    assert row is not None
    dart = render_node_body(row, uses_svg=True, theme_variant="material")
    assert "receipt-outline_602_847.svg', width: 24.0, height: 24.0" in dart
    assert "width: 48.0, height: 48.0" not in dart.split("receipt-outline_602_847")[1][:80]
