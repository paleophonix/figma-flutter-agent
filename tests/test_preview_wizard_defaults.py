"""Wizard defaults for fast preview capture."""

from __future__ import annotations

from figma_flutter_agent.config import Settings
from figma_flutter_agent.config.profiles import apply_interactive_preview_profile
from figma_flutter_agent.preview import CaptureMode, resolve_capture_mode
from figma_flutter_agent.wizard.menus import _view_menu_options
from figma_flutter_agent.wizard.prompts import _menu_command


def test_view_menu_command_prefixes() -> None:
    options = _view_menu_options()
    commands = {_menu_command(option) for option in options if " — " in option}
    assert commands >= {"chrome", "preview", "renders", "full-review", "full-renders"}


def test_wizard_default_capture_mode_is_preview() -> None:
    settings = apply_interactive_preview_profile(Settings())
    assert settings.agent.runtime.default_capture_mode == CaptureMode.PREVIEW.value
    assert resolve_capture_mode(settings) is CaptureMode.PREVIEW


def test_resolve_capture_mode_oracle_from_config() -> None:
    base = Settings()
    settings = base.model_copy(
        update={
            "agent": base.agent.model_copy(
                update={
                    "runtime": base.agent.runtime.model_copy(
                        update={"default_capture_mode": CaptureMode.ORACLE.value},
                    ),
                },
            ),
        },
    )
    assert resolve_capture_mode(settings) is CaptureMode.ORACLE


def test_wizard_view_menu_lists_capture_and_chrome_combos() -> None:
    options = _view_menu_options()
    assert any(option.startswith("chrome —") for option in options)
    assert any("capture PNG only" in option for option in options)
    assert any(option.startswith("renders —") for option in options)
    assert any(option.startswith("full-review —") for option in options)
    assert any(option.startswith("full-renders —") for option in options)
