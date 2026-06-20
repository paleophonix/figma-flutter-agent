"""Eval tests for repair pipeline routing expectations."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.dev.opencode.failure_class import FailureClass, classify_check_route
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    resolve_from_check,
    resolve_from_review,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_stale_capture_rollback_route() -> None:
    case = _load("stale_capture_rollback")
    route = classify_check_route(FailureClass(case["failure_class"]))
    assert route == case["expected_route"]


def test_patch_code_emit_route() -> None:
    case = _load("patch_code_emit")
    decision = resolve_from_check(case["check_payload"])
    assert decision == RouteDecision(case["expected_decision"])


def test_capture_visual_mismatch_review_loop() -> None:
    case = _load("capture_visual_mismatch")
    decision = resolve_from_review(case["review_payload"])
    assert decision == RouteDecision.DIAGNOSE_REFINE


def test_scope_drift_stop_reason() -> None:
    case = _load("scope_drift")
    assert case["expected_stop_reason"] == "SCOPE_DRIFT"


def test_review_loop_refine_route() -> None:
    case = _load("review_loop_refine")
    decision = resolve_from_review(case["review_payload"])
    assert decision == RouteDecision.DIAGNOSE_REFINE
