"""Tests for OpenCode repair write prompt assembly."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.prompt_context import build_write_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_repair_noop_budget,
)


def test_build_write_step_user_prompt_includes_plan_and_acdp(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    chain = ReasoningChain()
    plan = {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
            }
        ]
    }
    chain.append("plan", plan)
    prompt = build_write_step_user_prompt(
        "repair",
        feature="login",
        board="forensic",
        worktree=worktree,
        debug_mirror=debug_mirror,
        chain=chain,
        run_context={"case_mode": "FORENSIC", "planStepOrders": [1]},
        l6_bindings={"worktree": worktree.as_posix(), "feature": "login"},
        plan=plan,
    )
    assert "planStepOrders" in prompt
    assert "<L2:ROLE>" in prompt
    assert "implement the law patch" in prompt


def test_build_write_step_user_prompt_includes_continuation_summary(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    chain = ReasoningChain()
    plan = {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
            }
        ]
    }
    prompt = build_write_step_user_prompt(
        "repair",
        feature="login",
        board="forensic",
        worktree=worktree,
        debug_mirror=debug_mirror,
        chain=chain,
        run_context={
            "case_mode": "FORENSIC",
            "planStepOrders": [1],
            "repair_continuation_summary": "Maximum steps reached. Patch flex_sizing.py next.",
        },
        l6_bindings={"worktree": worktree.as_posix(), "feature": "login"},
        plan=plan,
    )
    assert "Continuation (mandatory)" in prompt
    assert "prior_repair_summary" in prompt
    assert "flex_sizing.py" in prompt


def test_apply_repair_noop_budget_uses_separate_counter() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_noop_retries=2, max_diagnose_refinements_per_root=0)
    assert apply_repair_noop_budget(state, loops) == RouteDecision.PLAN_REVISE
    assert state.repair_noop_retries == 1
    assert state.diagnose_refinements == 0
    assert apply_repair_noop_budget(state, loops) == RouteDecision.PLAN_REVISE
    assert apply_repair_noop_budget(state, loops) == RouteDecision.STOP_HUMAN
