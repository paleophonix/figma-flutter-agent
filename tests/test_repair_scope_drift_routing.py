"""Tests for repair scope drift retry routing."""

from __future__ import annotations

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    repair_gate_failure_is_terminal,
    repair_gate_failure_payload,
    repair_scope_drift_payload,
    route_after_repair_gate_failure,
    route_after_repair_scope_drift,
)


def _compiler_plan() -> dict:
    return {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "targetFiles": [
                    "src/figma_flutter_agent/stages/write.py",
                    "src/figma_flutter_agent/pipeline/run/commit.py",
                ],
            }
        ],
    }


def test_repair_scope_drift_payload_detects_scope_block() -> None:
    repair = {
        "scope": {"passed": False, "reason_code": "SCOPE_DRIFT", "violations": ["a.py"]},
    }
    assert repair_scope_drift_payload(repair) is True


def test_route_after_scope_drift_with_in_scope_edits_retries() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_retries_per_plan=2)
    repair = {
        "scope": {
            "passed": False,
            "reason_code": "SCOPE_DRIFT",
            "violations": ["src/figma_flutter_agent/pipeline/result.py"],
        },
        "filesTouched": [
            "src/figma_flutter_agent/stages/write.py",
            "src/figma_flutter_agent/pipeline/result.py",
        ],
    }
    assert route_after_repair_scope_drift(repair, _compiler_plan(), state, loops) == (
        RouteDecision.REPAIR_RETRY
    )
    assert state.repair_retries == 1


def test_route_after_scope_drift_without_plan_edits_revises_plan() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_noop_retries=2)
    repair = {
        "scope": {
            "passed": False,
            "reason_code": "SCOPE_DRIFT",
            "violations": ["src/figma_flutter_agent/pipeline/result.py"],
        },
        "filesTouched": ["src/figma_flutter_agent/pipeline/result.py"],
    }
    assert route_after_repair_scope_drift(repair, _compiler_plan(), state, loops) == (
        RouteDecision.PLAN_REVISE
    )
    assert state.repair_noop_retries == 1


def test_repair_gate_failure_payload_detects_failed_gates() -> None:
    repair = {
        "gates_failed": True,
        "gates": {"passed": False, "ruff": False, "pytest": True},
    }
    assert repair_gate_failure_payload(repair) is True


def test_route_after_gate_failure_with_compiler_edits_retries() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_retries_per_plan=2)
    repair = {
        "gates_failed": True,
        "gates": {"passed": False, "ruff": False, "pytest": False},
        "filesTouched": ["src/figma_flutter_agent/stages/write.py"],
    }
    assert route_after_repair_gate_failure(repair, _compiler_plan(), state, loops) == (
        RouteDecision.REPAIR_RETRY
    )
    assert state.repair_retries == 1


def test_repair_gate_failure_terminal_on_missing_pytest_path() -> None:
    repair = {
        "gates_failed": True,
        "gates": {
            "passed": False,
            "pytest": False,
            "pytest_output": "ERROR: file or directory not found: tests/missing.py",
        },
    }
    assert repair_gate_failure_is_terminal(repair) is True


def test_route_after_gate_failure_terminal_stops_without_retry() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_repair_retries_per_plan=2)
    repair = {
        "gates_failed": True,
        "gates": {
            "passed": False,
            "pytest": False,
            "pytest_output": "ERROR: file or directory not found: tests/missing.py",
        },
        "filesTouched": ["src/figma_flutter_agent/stages/write.py"],
    }
    assert route_after_repair_gate_failure(repair, _compiler_plan(), state, loops) == (
        RouteDecision.STOP_HUMAN
    )
    assert state.repair_retries == 0
