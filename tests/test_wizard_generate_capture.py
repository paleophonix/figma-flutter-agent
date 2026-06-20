"""Wizard generate capture override."""

from __future__ import annotations

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.wizard.capture_prompt import apply_wizard_debug_capture


def test_apply_wizard_debug_capture_overrides_without_mutating_source() -> None:
    settings = load_settings()
    original = settings.agent.dev.debug_capture
    toggled = not original

    updated = apply_wizard_debug_capture(settings, enabled=toggled)

    assert updated.agent.dev.debug_capture is toggled
    assert settings.agent.dev.debug_capture is original
