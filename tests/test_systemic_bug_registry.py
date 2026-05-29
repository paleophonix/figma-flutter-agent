"""Tests for the systemic LLM bug registry in prompts."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts import (
    SYSTEMIC_BUG_RULES,
    build_repair_system_prompt,
    build_system_prompt,
    build_systemic_bug_registry_l3,
    build_visual_refine_system_prompt,
)


def test_systemic_bug_rules_non_empty_and_unique() -> None:
    assert len(SYSTEMIC_BUG_RULES) >= 10
    assert len(SYSTEMIC_BUG_RULES) == len(set(SYSTEMIC_BUG_RULES))


def test_registry_includes_known_guardrails() -> None:
    block = build_systemic_bug_registry_l3()
    assert "Key? key = null" in block
    assert "super.key" in block
    assert "AppTypography" in block
    assert "Color(0xFF000000)" in block
    assert "fontSize" in block
    assert "Positioned" in block
    assert "Flex(fit" in block


def test_generate_repair_refine_prompts_include_registry() -> None:
    registry = build_systemic_bug_registry_l3()
    assert registry in build_system_prompt()
    assert registry in build_system_prompt(use_screen_ir=True)
    assert registry in build_repair_system_prompt()
    assert registry in build_visual_refine_system_prompt()
