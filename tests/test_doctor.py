"""Tests for figma-flutter doctor."""

from __future__ import annotations

from figma_flutter_agent.dev.doctor import run_doctor


def test_doctor_returns_core_checks() -> None:
    rows = run_doctor()
    names = {row.name for row in rows}
    assert "poetry" in names
    assert "ast_sidecar" in names
    assert "docker" in names
    assert "golden_image" in names
    assert "agent_config" in names
    assert "llm_provider" in names
    assert "llm_api_key" in names
    assert "fidelity_geometry_gate" in names
