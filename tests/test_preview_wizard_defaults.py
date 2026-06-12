"""Wizard defaults for fast preview capture."""

from __future__ import annotations

from figma_flutter_agent.config import Settings
from figma_flutter_agent.config.profiles import apply_interactive_preview_profile
from figma_flutter_agent.preview_capture import CaptureMode, resolve_capture_mode
from figma_flutter_agent.wizard.menus import _view_menu_options


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


def test_wizard_view_menu_prefers_flutter_preview_label() -> None:
    options = _view_menu_options()
    assert any("Flutter web PNG" in option for option in options)
    assert any("oracle" in option for option in options)
