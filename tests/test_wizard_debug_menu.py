"""Tests for wizard debug menu wiring."""

from __future__ import annotations

from figma_flutter_agent.wizard.menus import _run_menu_options, _wizard_menu_options


def test_main_menu_item_eight_is_debug() -> None:
    options = _wizard_menu_options()
    assert len(options) >= 9
    assert options[8].startswith("debug —")


def test_debug_submenu_reuses_run_options() -> None:
    run_options = _run_menu_options()
    assert run_options[0].startswith("ir-offline —")
    assert run_options[1].startswith("full —")
    assert run_options[2].startswith("offline —")
    assert run_options[-1].startswith("return —")
