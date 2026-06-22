"""Tests for repair noop vs incomplete orchestrator routing."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_repair_noop_budget,
    apply_repair_retry_budget,
    route_after_repair_noop,
)


def _compiler_plan() -> dict:
    return {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/generator/layout/widgets/flex_sizing.py"],
            }
        ],
    }


def test_route_after_incomplete_repair_retries_not_plan_revise() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_retries_per_plan=3)
    repair = {"noop": True, "incomplete": True, "noop_reason": "steps_exhausted"}
    assert route_after_repair_noop(repair, _compiler_plan(), state, loops) == (
        RouteDecision.REPAIR_RETRY
    )
    assert state.repair_retries == 1
    assert state.repair_noop_retries == 0


def test_route_after_noop_with_compiler_plan_retries() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_retries_per_plan=2)
    repair = {"noop": True, "incomplete": False, "noop_reason": "no_compiler_edits"}
    assert route_after_repair_noop(repair, _compiler_plan(), state, loops) == (
        RouteDecision.REPAIR_RETRY
    )


def test_route_after_noop_without_compiler_targets_revise_plan() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_noop_retries=2)
    repair = {"noop": True, "incomplete": False}
    plan = {"steps": [{"order": 1, "actionKind": "REPORT_ONLY"}]}
    assert route_after_repair_noop(repair, plan, state, loops) == RouteDecision.PLAN_REVISE
    assert state.repair_noop_retries == 1


def test_apply_repair_retry_budget_stops_when_exhausted() -> None:
    state = LoopBudgetState(repair_retries=2)
    loops = DebugPipelineLoopsConfig(max_repair_retries_per_plan=2)
    assert apply_repair_retry_budget(state, loops) == RouteDecision.STOP_HUMAN


def test_apply_repair_noop_budget_still_increments_noop_counter() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_noop_retries=1)
    assert apply_repair_noop_budget(state, loops) == RouteDecision.PLAN_REVISE
    assert apply_repair_noop_budget(state, loops) == RouteDecision.STOP_HUMAN
