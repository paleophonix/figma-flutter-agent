"""Tests for stateful repair system-prompt escalation."""

from __future__ import annotations

from figma_flutter_agent.llm.repair_scope import RepairEnvironmentContext
from figma_flutter_agent.stages.repair_prompt_escalation import RepairPromptEscalator


def _env() -> RepairEnvironmentContext:
    return RepairEnvironmentContext(
        analyze_errors="- error - x",
        code="1: class Demo {}",
        semantic_hint="null",
        failed_attempts_history="(no prior failed patches in this run)",
        unchanged_widget_names="(none)",
    )


def test_escalation_level_maps_four_attempts() -> None:
    escalator = RepairPromptEscalator(
        target_file="lib/features/sign_in/sign_in_screen.dart",
        max_attempts=4,
    )
    assert escalator.escalation_level(1) == 1
    assert escalator.escalation_level(2) == 2
    assert escalator.escalation_level(3) == 3
    assert escalator.escalation_level(4) == 4


def test_level_one_uses_standard_apr() -> None:
    escalator = RepairPromptEscalator(
        target_file="lib/features/demo/demo_screen.dart",
        max_attempts=4,
    )
    prompt = escalator.generate_system_prompt(attempt=1, env_context=_env())
    assert "<L2:ROLE>" in prompt
    assert "Automated Program Repair" in prompt or "APR" in prompt
    assert "Metacognitive Code-Review Supervisor" not in prompt


def test_level_three_requires_surgical_unified_diff() -> None:
    escalator = RepairPromptEscalator(
        target_file="lib/features/sign_in/sign_in_screen.dart",
        max_attempts=4,
    )
    prompt = escalator.generate_system_prompt(attempt=3, env_context=_env())
    assert "SURGICAL UNIFIED DIFF" in prompt
    assert "full-file bodies" in prompt
    assert "SEARCH/REPLACE" in prompt
    assert "write_string" not in prompt


def test_level_two_uses_metacognitive_supervisor_frame() -> None:
    escalator = RepairPromptEscalator(
        target_file="lib/features/sign_in/sign_in_screen.dart",
        max_attempts=4,
    )
    prompt = escalator.generate_system_prompt(attempt=2, env_context=_env())
    assert "Metacognitive Code-Review Supervisor" in prompt
    assert "LEVEL 2" in prompt
    assert "lib/widgets/" in prompt
