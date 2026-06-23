"""Route resolution and budget-aware dispatch for the repair pipeline."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.dev.opencode.failure_class import FailureClass, classify_check_route
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    collect_plan_target_files,
    plan_has_actionable_compiler_targets,
)

_COMPILER_PREFIX = "src/figma_flutter_agent/"

_GATE_PYTEST_PATH_NOT_FOUND = re.compile(
    r"file or directory not found:",
    re.IGNORECASE,
)


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def repair_touched_compiler_plan_targets(
    repair_payload: dict[str, Any],
    plan_payload: dict[str, Any],
) -> bool:
    """Return whether repair ``filesTouched`` intersects plan CODE_CHANGE compiler targets."""
    plan_targets = {
        path
        for path in collect_plan_target_files(plan_payload)
        if path.startswith(_COMPILER_PREFIX)
    }
    if not plan_targets:
        return False
    touched_raw = repair_payload.get("filesTouched") or []
    if not isinstance(touched_raw, list):
        return False
    touched = {_normalize_repo_path(str(entry)) for entry in touched_raw if entry}
    return bool(plan_targets.intersection(touched))


class RouteDecision(StrEnum):
    """Executable orchestrator transitions."""

    CONTINUE_CAPTURE = "continue_capture"
    FIX_ATTEMPT = "fix_attempt"
    DIAGNOSE_REFINE = "diagnose.refine"
    REPAIR_RETRY = "repair.retry"
    PLAN_REVISE = "plan.revise"
    CHECK_RETRY = "check.retry"
    CAPTURE_VERIFY = "capture.verify"
    FORENSIC = "forensic"
    SUMMARIZE = "summarize"
    STOP_HUMAN = "stop_human"


_ROUTE_STRINGS: dict[str, RouteDecision] = {
    "capture": RouteDecision.CONTINUE_CAPTURE,
    "fix": RouteDecision.FIX_ATTEMPT,
    "diagnose.refine": RouteDecision.DIAGNOSE_REFINE,
    "repair.retry": RouteDecision.REPAIR_RETRY,
    "plan.revise": RouteDecision.PLAN_REVISE,
    "check.retry": RouteDecision.CHECK_RETRY,
    "capture.verify": RouteDecision.CAPTURE_VERIFY,
    "forensic": RouteDecision.FORENSIC,
    "summarize": RouteDecision.SUMMARIZE,
    "stop": RouteDecision.STOP_HUMAN,
}


def route_string_for(decision: RouteDecision) -> str:
    """Return canonical route string for a decision."""
    if decision == RouteDecision.CONTINUE_CAPTURE:
        return "capture"
    return decision.value


def resolve_from_check(check_payload: dict[str, Any]) -> RouteDecision:
    """Map check gate output to an orchestrator route."""
    if check_payload.get("passed"):
        return RouteDecision.CONTINUE_CAPTURE
    failure_raw = str(check_payload.get("failure_class") or "")
    try:
        failure = FailureClass(failure_raw)
    except ValueError:
        failure = FailureClass.UNKNOWN_BLOCKED
    route = classify_check_route(failure)
    return _ROUTE_STRINGS.get(route, RouteDecision.STOP_HUMAN)


def resolve_from_review(review_payload: dict[str, Any]) -> RouteDecision:
    """Map review output to an orchestrator route."""
    decision = str(review_payload.get("decision") or "STOP").upper()
    route = str(review_payload.get("route") or "").strip()
    if decision == "CONTINUE":
        return RouteDecision.SUMMARIZE
    if decision == "STOP":
        return RouteDecision.SUMMARIZE
    if decision == "LOOP":
        if route in _ROUTE_STRINGS:
            return _ROUTE_STRINGS[route]
        return RouteDecision.DIAGNOSE_REFINE
    return RouteDecision.STOP_HUMAN


def apply_repair_retry_budget(
    state: LoopBudgetState,
    loops: DebugPipelineLoopsConfig,
) -> RouteDecision:
    """Budget repair.retry micro-loops (continuation or higher effort)."""
    if state.budget_exceeded("repair.retry", loops):
        return RouteDecision.STOP_HUMAN
    state.increment_for_route("repair.retry")
    return RouteDecision.REPAIR_RETRY


def apply_repair_noop_budget(
    state: LoopBudgetState,
    loops: DebugPipelineLoopsConfig,
) -> RouteDecision:
    """Budget repair noop → plan.revise micro-loops separately from diagnose.refine."""
    if state.budget_exceeded("repair.noop", loops):
        return RouteDecision.STOP_HUMAN
    state.increment_for_route("repair.noop")
    return RouteDecision.PLAN_REVISE


def repair_scope_drift_payload(repair_payload: dict[str, Any]) -> bool:
    """Return True when repair ended with a scope drift violation."""
    scope = repair_payload.get("scope")
    if not isinstance(scope, dict):
        return False
    return scope.get("reason_code") == "SCOPE_DRIFT" and not scope.get("passed")


def repair_gate_failure_payload(repair_payload: dict[str, Any]) -> bool:
    """Return True when repair compiler edits failed ruff/pytest gates."""
    if not repair_payload.get("gates_failed"):
        return False
    gates = repair_payload.get("gates")
    if not isinstance(gates, dict):
        return True
    return not gates.get("passed", True)


def repair_gate_failure_is_terminal(repair_payload: dict[str, Any]) -> bool:
    """Return True when gate failure is infra/config (missing pytest paths), not code.

    ``RepairGateInvalidPathLaw``: pytest must not target plan-hallucinated paths that
    were never created on disk — retrying OpenCode cannot fix a missing file path.
    """
    if not repair_gate_failure_payload(repair_payload):
        return False
    gates = repair_payload.get("gates")
    if not isinstance(gates, dict):
        return False
    pytest_out = str(gates.get("pytest_output") or "")
    return bool(_GATE_PYTEST_PATH_NOT_FOUND.search(pytest_out))


def route_after_repair_gate_failure(
    repair_payload: dict[str, Any],
    plan_payload: dict[str, Any],
    state: LoopBudgetState,
    loops: DebugPipelineLoopsConfig,
) -> RouteDecision:
    """Choose repair.retry vs stop after ruff/pytest gate failure.

    ``RepairGateFailureRetryPolicyLaw``: compiler edits that fail scoped gates
    should retry repair with gate output in the pivot, not an immediate hard stop.
    """
    if repair_gate_failure_is_terminal(repair_payload):
        return RouteDecision.STOP_HUMAN
    if repair_touched_compiler_plan_targets(repair_payload, plan_payload):
        return apply_repair_retry_budget(state, loops)
    if plan_has_actionable_compiler_targets(plan_payload):
        return apply_repair_noop_budget(state, loops)
    return apply_repair_retry_budget(state, loops)


def route_after_repair_scope_drift(
    repair_payload: dict[str, Any],
    plan_payload: dict[str, Any],
    state: LoopBudgetState,
    loops: DebugPipelineLoopsConfig,
) -> RouteDecision:
    """Choose repair.retry vs plan.revise after scope drift.

    ``RepairScopeDriftRetryPolicyLaw``: when the agent edited in-scope compiler
    targets but also drifted, retry repair with a pivot. When nothing in plan
    scope was touched, revise the plan targets instead of a blind retry.
    """
    if repair_touched_compiler_plan_targets(repair_payload, plan_payload):
        return apply_repair_retry_budget(state, loops)
    if plan_has_actionable_compiler_targets(plan_payload):
        return apply_repair_noop_budget(state, loops)
    return apply_repair_noop_budget(state, loops)


def route_after_repair_noop(
    repair_payload: dict[str, Any],
    plan_payload: dict[str, Any],
    state: LoopBudgetState,
    loops: DebugPipelineLoopsConfig,
) -> RouteDecision:
    """Choose repair.retry vs plan.revise after a noop repair pass.

    ``RepairNoopRetryPolicyLaw``: read-only recon or noop without compiler edits on
    plan targets must revise the plan (wrong layer / stale targets), not blind
    ``repair.retry``. Retry only when the session touched at least one plan compiler
    target but still failed scope or gates.
    """
    if repair_touched_compiler_plan_targets(repair_payload, plan_payload):
        return apply_repair_retry_budget(state, loops)
    if plan_has_actionable_compiler_targets(plan_payload):
        return apply_repair_noop_budget(state, loops)
    return apply_repair_noop_budget(state, loops)


def apply_budget(
    decision: RouteDecision,
    state: LoopBudgetState,
    loops: DebugPipelineLoopsConfig,
) -> RouteDecision:
    """Enforce loop budgets; downgrade to STOP_HUMAN when exhausted."""
    if decision in {
        RouteDecision.SUMMARIZE,
        RouteDecision.CONTINUE_CAPTURE,
        RouteDecision.FORENSIC,
    }:
        return decision
    route = route_string_for(decision)
    if state.budget_exceeded(route, loops):
        return RouteDecision.STOP_HUMAN
    state.increment_for_route(route)
    return decision


def entry_step_for(decision: RouteDecision) -> str:
    """Return pipeline entry step for an outer-loop dispatch."""
    mapping = {
        RouteDecision.DIAGNOSE_REFINE: "diagnose",
        RouteDecision.PLAN_REVISE: "plan",
        RouteDecision.REPAIR_RETRY: "repair",
        RouteDecision.FIX_ATTEMPT: "check",
        RouteDecision.CHECK_RETRY: "check",
        RouteDecision.CAPTURE_VERIFY: "check",
    }
    return mapping.get(decision, "recognise")
