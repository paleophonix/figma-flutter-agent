"""Tests for repair capture proof policy."""

from __future__ import annotations

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.dev.opencode.capture_policy import repair_proof_capture_enabled
from figma_flutter_agent.dev.opencode.failure_class import FailureClass, classify_check_route
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_budget,
    resolve_from_check,
)


def test_repair_proof_capture_enabled_when_pipeline_verify_on() -> None:
    """RepairProofCaptureLaw: pipeline verify overrides dev.debug_capture=false."""
    settings = load_settings()
    settings.agent.dev.debug_capture = False
    settings.agent.debug_pipeline.check_flutter_capture_verify = True
    assert repair_proof_capture_enabled(settings)


def test_repair_proof_capture_disabled_when_both_off() -> None:
    settings = load_settings()
    settings.agent.dev.debug_capture = False
    settings.agent.debug_pipeline.check_flutter_capture_verify = False
    assert not repair_proof_capture_enabled(settings)


def test_capture_artifact_missing_routes_to_capture_verify() -> None:
    decision = resolve_from_check(
        {
            "passed": False,
            "failure_class": FailureClass.CAPTURE_ARTIFACT_MISSING.value,
        }
    )
    assert decision == RouteDecision.CAPTURE_VERIFY
    assert classify_check_route(FailureClass.CAPTURE_ARTIFACT_MISSING) == "capture.verify"


def test_capture_verify_budget_uses_produce_counter() -> None:
    """CaptureMissingBudgetLaw: produce route has its own retry budget."""
    from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig

    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(max_toolchain_retries=2)
    decision = apply_budget(RouteDecision.CAPTURE_VERIFY, state, loops)
    assert decision == RouteDecision.CAPTURE_VERIFY
    assert state.capture_produce_attempts == 1
    assert state.toolchain_retries == 0
