"""Tests for repair pipeline checkpoints."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint, load_resume_context


def test_append_checkpoint_writes_jsonl(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    append_checkpoint(state_dir, step="diagnose", loop_round=2, extra={"route": "diagnose.refine"})
    lines = (state_dir / "checkpoints.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["step"] == "diagnose"
    assert record["loop_round"] == 2


def test_load_resume_context_from_chain(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "reasoning_chain.json").write_text('{"steps": {"plan": {}}}', encoding="utf-8")
    ctx = load_resume_context(state_dir)
    assert ctx is not None
    assert "reasoning_chain" in ctx


def test_load_last_checkpoint_returns_final_line(tmp_path: Path) -> None:
    from figma_flutter_agent.dev.opencode.checkpoint import load_last_checkpoint

    state_dir = tmp_path / "state"
    append_checkpoint(state_dir, step="plan", loop_round=1)
    append_checkpoint(state_dir, step="repair", loop_round=1)
    last = load_last_checkpoint(state_dir)
    assert last is not None
    assert last["step"] == "repair"


def test_restore_loop_budget_restores_extended_counters(tmp_path: Path) -> None:
    from figma_flutter_agent.dev.opencode.checkpoint import restore_loop_budget, save_loop_budget
    from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState

    state_dir = tmp_path / "state"
    state = LoopBudgetState(
        diagnose_bootstrap=2,
        plan_validation_attempts=3,
        orchestrator_steps=11,
        check_after_fix=1,
    )
    save_loop_budget(state_dir, state)
    restored = restore_loop_budget(state_dir)
    assert restored.diagnose_bootstrap == 2
    assert restored.plan_validation_attempts == 3
    assert restored.orchestrator_steps == 11
    assert restored.check_after_fix == 1


def test_summarize_checkpoint_resumes_at_check(tmp_path: Path) -> None:
    from figma_flutter_agent.dev.opencode.checkpoint import resolve_resume_phase_entry
    from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    chain = ReasoningChain()
    chain.append("summarize", {"step": "summarize", "passed": True})
    chain.save(state_dir / "reasoning_chain.json")
    append_checkpoint(state_dir, step="summarize", loop_round=2)
    phase, loop_round = resolve_resume_phase_entry(state_dir)
    assert phase == "check"
    assert loop_round == 2
