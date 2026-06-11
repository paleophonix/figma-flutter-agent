"""Production profile fidelity gates (EPIC 4.5)."""

from __future__ import annotations

from figma_flutter_agent.config import Settings, apply_production_profile


def test_production_profile_enables_strict_fidelity() -> None:
    settings = apply_production_profile(Settings())
    assert settings.agent.semantics.strict_fidelity is True
