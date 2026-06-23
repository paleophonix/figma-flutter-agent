"""Tests for post-regenerate capture verify and root-hash budget reset."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_budget,
)


def test_root_hash_budget_resets_after_regenerate_success() -> None:
    """RepairLoopBudgetResetAfterRegenerateLaw: fresh proof clears stale repeats."""
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(same_root_hash_repeat_without_improvement=2)
    root = "sha256:e49ac53876b483a4"
    state.record_root_hash(root, improved=False)
    state.record_root_hash(root, improved=False)
    assert state.same_root_exhausted(loops)

    state.root_hash_counts.clear()
    state.last_root_hash = ""
    state.last_root_improved = False

    assert not state.same_root_exhausted(loops)
    decision = apply_budget(RouteDecision.DIAGNOSE_REFINE, state, loops)
    assert decision == RouteDecision.DIAGNOSE_REFINE


@pytest.mark.asyncio
async def test_capture_verify_runs_after_mirror_regenerated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RepairPostRegenerateCaptureVerifyLaw: pinned capture runs after regen refresh."""
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass
    from figma_flutter_agent.dev.opencode.pipeline.orchestrator import run_repair_pipeline
    from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
    from figma_flutter_agent.dev.opencode.run_gate import RunGateResult
    from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

    worktree = tmp_path / "wt"
    worktree.mkdir()
    state_dir = worktree / ".repair" / "state"
    state_dir.mkdir(parents=True)
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    (debug_mirror / "raw.json").write_text("{}", encoding="utf-8")
    (debug_mirror / "last.log").write_text(
        "--- dart analyze (generated) @ 2026-01-01 ---\nexit_code=0\n",
        encoding="utf-8",
    )

    chain = ReasoningChain()
    chain.append(
        "plan",
        {
            "step": "plan",
            "blocked": False,
            "steps": [
                {
                    "order": 1,
                    "actionKind": "CODE_CHANGE",
                    "lawId": "law_row",
                    "targetFiles": [
                        "src/figma_flutter_agent/generator/layout/flex_policy/row.py"
                    ],
                    "tests": ["tests/test_flex_emitter.py"],
                }
            ],
        },
    )
    chain.append(
        "repair",
        {
            "step": "repair",
            "skipped": False,
            "salvaged": True,
            "filesTouched": [
                "src/figma_flutter_agent/generator/layout/flex_policy/row.py"
            ],
            "gates": {"passed": True, "ruff": True, "pytest": True},
            "scope": {"passed": True},
        },
    )
    chain.save(state_dir / "reasoning_chain.json")
    append_checkpoint(state_dir, step="repair", loop_round=1)
    (state_dir / "loop_budget.json").write_text(
        json.dumps(
            {
                "correction_cycle": 1,
                "outer_round": 1,
                "same_root_repeats": {"sha256:e49ac53876b483a4": 2},
            }
        ),
        encoding="utf-8",
    )

    workspace = RepairWorkspace(
        case_id="case",
        worktree=worktree,
        repair_root=worktree / ".repair",
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=worktree / ".repair" / "manifest.json",
    )

    gate_root = tmp_path / "screen"
    gate_root.mkdir()
    gate = RunGateResult(
        feature="login",
        screen_root=gate_root,
        verdict=FailureClass.CAPTURE_FAILED,
        case_mode="FORENSIC",
        agent_board="forensic",
        pipeline_run_id="run-1",
        candidate_build_run_id="run-1",
        committed_build_run_id="run-1",
        served_build_run_id=None,
        writeback="committed",
        served_probe_present=False,
        candidate_available=True,
        manifest_path=gate_root / "run_manifest.json",
        allowed_questions=(),
        forbidden_questions=(),
    )

    capture_calls: list[str] = []

    async def _fake_capture_verify(**kwargs: object) -> object:
        _ = kwargs
        capture_calls.append("called")
        from figma_flutter_agent.dev.opencode.capture_verify import CaptureVerifyResult

        return CaptureVerifyResult(
            passed=False,
            payload={"step": "capture_verify", "passed": False},
        )

    async def _fake_regen(**kwargs: object) -> object:
        _ = kwargs
        from figma_flutter_agent.dev.opencode.regenerate_mirror import RegenerateResult

        return RegenerateResult(
            passed=True,
            payload={
                "passed": True,
                "run_id": "regen-1",
                "mirror_source_dir": str(
                    (worktree / ".debug" / "flutter_project" / "login").as_posix()
                ),
            },
        )

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_regenerate_after_compiler_repair",
        _fake_regen,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_capture_verify",
        _fake_capture_verify,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_check_gate",
        lambda *args, **kwargs: type(
            "R",
            (),
            {
                "passed": False,
                "payload": {
                    "passed": False,
                    "failure_class": "PATCH_RUNTIME",
                    "route": "diagnose.refine",
                    "same_root_hash": "sha256:e49ac53876b483a4",
                },
                "failure_class": FailureClass.PATCH_RUNTIME,
                "route": "diagnose.refine",
            },
        )(),
    )

    settings = load_settings()
    settings.agent.dev.debug_capture = False
    settings.agent.debug_pipeline.check_flutter_capture_verify = True
    settings.agent.debug_pipeline.trace.enabled = False
    settings.agent.debug_pipeline.trace.disk = False

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.resolve_repair_flutter_project_dir",
        lambda workspace, source: tmp_path / "flutter_stub",
    )

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
            settings=settings,
            project_dir=tmp_path / "project",
            feature="login",
            existing_workspace=workspace,
            resume=True,
            skip_opencode_repair=True,
        )

    assert capture_calls == ["called"]
    assert outcome.chain is not None
    budget = json.loads((state_dir / "loop_budget.json").read_text(encoding="utf-8"))
    repeats = budget.get("same_root_repeats") or {}
    assert repeats.get("sha256:e49ac53876b483a4", 0) < 2
