"""Tests for repair capture proof policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.dev.opencode.capture_policy import (
    capture_verify_failure_is_terminal,
    prepare_repair_capture_resume,
    repair_proof_capture_enabled,
)
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


def test_capture_verify_terminal_reasons() -> None:
    assert capture_verify_failure_is_terminal({"reason_code": "CAPTURE_DISABLED"})
    assert capture_verify_failure_is_terminal({"reason_code": "REPAIR_CAPTURE_DISABLED"})
    assert not capture_verify_failure_is_terminal({"reason_code": "FLUTTER_CAPTURE_BLOCKED"})


def test_prepare_repair_capture_resume_clears_produce_budget(tmp_path: Path) -> None:
    state = LoopBudgetState()
    state.capture_produce_attempts = 2
    state.root_hash_counts["sha256:deadbeef"] = 3
    state.last_root_hash = "sha256:deadbeef"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "capture_verify.json").write_text(
        '{"reason_code": "CAPTURE_DISABLED"}',
        encoding="utf-8",
    )
    run_context: dict[str, object] = {}
    prepare_repair_capture_resume(
        phase_entry="check",
        chain_steps={
            "check": {
                "passed": False,
                "failure_class": FailureClass.CAPTURE_ARTIFACT_MISSING.value,
            }
        },
        state_dir=state_dir,
        loop_state=state,
        run_context=run_context,
    )
    assert state.capture_produce_attempts == 0
    assert state.root_hash_counts == {}
    assert run_context["_force_capture_verify"] is True


@pytest.mark.asyncio
async def test_debug_capture_runs_when_repair_proof_enabled(tmp_path: Path) -> None:
    from unittest.mock import patch

    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.debug.capture import run_project_debug_capture
    from figma_flutter_agent.preview_capture import CaptureMode
    from figma_flutter_agent.validation.golden_capture.result import GoldenCaptureResult

    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    settings = Settings()
    settings.agent.dev.debug_capture = False
    settings.agent.debug_pipeline.check_flutter_capture_verify = True
    settings.agent.runtime.default_capture_mode = CaptureMode.ORACLE.value

    capture_result = GoldenCaptureResult(png=b"flutter")
    with patch(
        "figma_flutter_agent.debug.capture.capture_planned_in_warm_sandbox",
        return_value=capture_result,
    ):
        outcome = await run_project_debug_capture(
            project_dir=project,
            feature_name="login",
            settings=settings,
            planned_files={"lib/generated/login_layout.dart": "class X {}"},
            clean_tree=None,
        )
    assert outcome is not None
