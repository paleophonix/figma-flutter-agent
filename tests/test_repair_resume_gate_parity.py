"""Tests for RepairResumeRunGateParityLaw."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.pipeline.orchestrator import run_repair_pipeline
from figma_flutter_agent.dev.opencode.run_gate import (
    RunGateResult,
    gate_blocks_pipeline,
    gate_blocks_new_run,
    resume_safe_gate_verdicts,
)


def _gate(verdict: FailureClass, tmp_path: Path) -> RunGateResult:
    root = tmp_path / "screen"
    root.mkdir(parents=True)
    return RunGateResult(
        feature="login",
        screen_root=root,
        verdict=verdict,
        case_mode="FORENSIC",
        agent_board="forensic",
        pipeline_run_id="run-1",
        candidate_build_run_id="run-1",
        committed_build_run_id="run-1",
        served_build_run_id="unknown",
        writeback="skipped",
        served_probe_present=False,
        candidate_available=False,
        manifest_path=root / "run_manifest.json",
        allowed_questions=(),
        forbidden_questions=(),
    )


def test_gate_blocks_new_run_includes_no_serve() -> None:
    assert gate_blocks_new_run(FailureClass.NO_SERVE) is True
    assert gate_blocks_new_run(FailureClass.FRESH_OK) is False


def test_gate_blocks_pipeline_allows_no_serve_on_resume() -> None:
    assert gate_blocks_pipeline(verdict=FailureClass.NO_SERVE, resume=False) is True
    assert gate_blocks_pipeline(verdict=FailureClass.NO_SERVE, resume=True) is False
    assert gate_blocks_pipeline(verdict=FailureClass.UNKNOWN_BLOCKED, resume=True) is True


def test_resume_safe_verdicts() -> None:
    assert FailureClass.NO_SERVE in resume_safe_gate_verdicts()


@pytest.mark.asyncio
async def test_orchestrator_resumes_on_no_serve_with_existing_workspace(
    tmp_path: Path,
) -> None:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

    worktree = tmp_path / "wt"
    worktree.mkdir()
    state_dir = worktree / ".repair" / "state"
    state_dir.mkdir(parents=True)
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=worktree / ".repair" / "manifest.json",
    )
    gate = _gate(FailureClass.NO_SERVE, tmp_path)

    with patch(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.evaluate_run_gate",
        return_value=gate,
    ), patch(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.resolve_step_gate",
        return_value=None,
    ), patch(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.resolve_round_gate",
        return_value=None,
    ):
        outcome = await run_repair_pipeline(
            settings=load_settings(),
            project_dir=tmp_path / "project",
            feature="login",
            existing_workspace=workspace,
            resume=True,
            skip_opencode_repair=True,
        )

    assert outcome.stop_reason != FailureClass.NO_SERVE.value
    assert outcome.workspace is workspace
