"""Unit tests for epistemic role prompts."""

from __future__ import annotations

from control_panel.repair.roles import EPISTEMIC_ROLES, ROLE_AGENT_MAP, role_prompt_slice


def test_all_roles_have_agents() -> None:
    for role in EPISTEMIC_ROLES:
        assert role in ROLE_AGENT_MAP
        assert ROLE_AGENT_MAP[role].startswith("diagnose-")


def test_role_prompt_includes_ticket() -> None:
    prompt = role_prompt_slice("skeptic", '{"symptom_summary":"x"}')
    assert "Skeptic" in prompt
    assert "symptom_summary" in prompt
