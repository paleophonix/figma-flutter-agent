"""Tests for persisted interactive wizard preferences."""

from pathlib import Path

from figma_flutter_agent.dev.wizard_prefs import (
    load_wizard_prefs,
    save_wizard_prefs,
    wizard_prefs_path,
)


def test_wizard_prefs_round_trip(tmp_path: Path) -> None:
    save_wizard_prefs(tmp_path, active_screen="sign_up_and_sign_in")
    prefs = load_wizard_prefs(tmp_path)
    assert prefs.active_screen == "sign_up_and_sign_in"
    assert wizard_prefs_path(tmp_path).is_file()


def test_wizard_prefs_clear_active_screen(tmp_path: Path) -> None:
    save_wizard_prefs(tmp_path, active_screen="home")
    save_wizard_prefs(tmp_path, active_screen=None)
    prefs = load_wizard_prefs(tmp_path)
    assert prefs.active_screen is None
    assert wizard_prefs_path(tmp_path).read_text(encoding="utf-8").strip() in {"", "{}"}


def test_wizard_prefs_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert load_wizard_prefs(tmp_path).active_screen is None
