"""Signoff profile enables runtime RenderFlex overflow gate."""

from __future__ import annotations

from figma_flutter_agent.config import apply_signoff_profile
from figma_flutter_agent.config.settings import Settings


def test_signoff_profile_enables_renderflex_overflow_gate() -> None:
    settings = apply_signoff_profile(Settings())
    assert settings.agent.generation.runtime_fail_renderflex_overflow is True
