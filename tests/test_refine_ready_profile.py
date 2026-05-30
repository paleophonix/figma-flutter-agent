"""Refine-ready and fidelity signoff helpers."""

from __future__ import annotations

from figma_flutter_agent.config import Settings, apply_refine_ready_profile
from figma_flutter_agent.dev.doctor import run_doctor


def test_apply_refine_ready_profile_enables_refine_and_geometry() -> None:
    settings = Settings()
    updated = apply_refine_ready_profile(settings)
    generation = updated.agent.generation
    assert generation.llm_visual_refine is True
    assert generation.runtime_geometry_gate is True
    assert generation.runtime_geometry_use_tier_thresholds is True
    assert generation.llm_visual_refine_threshold == 0.05


def test_doctor_includes_fidelity_checks() -> None:
    rows = run_doctor()
    names = {row.name for row in rows}
    assert "fidelity_geometry_gate" in names
    assert "fidelity_fixture_screens" in names
