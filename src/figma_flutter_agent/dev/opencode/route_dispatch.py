"""Route resolution and budget-aware dispatch for the repair pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.dev.opencode.failure_class import FailureClass, classify_check_route
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState


class RouteDecision(StrEnum):
    """Executable orchestrator transitions."""

    CONTINUE_CAPTURE = "continue_capture"
    FIX_ATTEMPT = "fix_attempt"
    DIAGNOSE_REFINE = "diagnose.refine"
    REPAIR_RETRY = "repair.retry"
    PLAN_REVISE = "plan.revise"
    CHECK_RETRY = "check.retry"
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
    }
    return mapping.get(decision, "recognise")
