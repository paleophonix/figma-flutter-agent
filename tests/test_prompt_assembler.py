"""Tests for prompt assembler."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.prompt_assembler import assemble_step_prompt


def test_assemble_diagnose_includes_acdp_layers() -> None:
    prompt = assemble_step_prompt(
        "diagnose",
        board="screen",
        run_context={"case_mode": "SCREEN"},
        reasoning_chain_json="{}",
    )
    assert "<L1:PURPOSE>" in prompt
    assert "<L6:ENVIRONMENT>" in prompt
