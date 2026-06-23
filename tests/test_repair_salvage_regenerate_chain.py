"""Integration tests for salvage → regenerate chain wiring."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.dev.opencode.checkpoint import resolve_resume_phase_entry
from figma_flutter_agent.dev.opencode.gates import GateResult
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    (path / "README.md").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


@pytest.mark.asyncio
async def test_resume_blocked_plan_routes_to_check_after_salvage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass
    from figma_flutter_agent.dev.opencode.pipeline.orchestrator import run_repair_pipeline
    from figma_flutter_agent.dev.opencode.run_gate import RunGateResult
    from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

    worktree = tmp_path / "wt"
    worktree.mkdir()
    _init_git_repo(worktree)
    row = worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "flex_policy" / "row.py"
    row.parent.mkdir(parents=True)
    row.write_text("# edit\n", encoding="utf-8")

    state_dir = worktree / ".repair" / "state"
    state_dir.mkdir(parents=True)
    debug_mirror = worktree / ".repair" / "debug" / "limbo" / "login"
    debug_mirror.mkdir(parents=True)
    (debug_mirror / "raw.json").write_text("{}", encoding="utf-8")

    chain = ReasoningChain()
    chain.append("plan", {"step": "plan", "blocked": True, "steps": []})
    chain.append("repair", {"step": "repair", "salvaged": True, "noop": False})
    chain.save(state_dir / "reasoning_chain.json")
    from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint

    append_checkpoint(state_dir, step="repair", loop_round=1)
    (state_dir / "loop_budget.json").write_text(
        json.dumps({"correction_cycle": 1, "outer_round": 1}),
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
        verdict=FailureClass.CANDIDATE_ONLY,
        case_mode="SCREEN",
        agent_board="screen",
        pipeline_run_id="run-1",
        candidate_build_run_id="run-1",
        committed_build_run_id="run-1",
        served_build_run_id="run-1",
        writeback="committed",
        served_probe_present=True,
        candidate_available=True,
        manifest_path=gate_root / "run_manifest.json",
        allowed_questions=(),
        forbidden_questions=(),
    )

    regen_calls: list[dict[str, object]] = []

    async def _fake_regen(**kwargs: object) -> object:
        regen_calls.append(kwargs)
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
        "figma_flutter_agent.dev.opencode.repair_salvage.run_repair_gates",
        lambda worktree, touched_paths=None: GateResult(
            passed=True,
            ruff_ok=True,
            pytest_ok=True,
            ruff_output="",
            pytest_output="",
            touched_paths=tuple(touched_paths or ()),
            skipped=False,
        ),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_regenerate_after_compiler_repair",
        _fake_regen,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_check_gate",
        lambda *args, **kwargs: type(
            "R",
            (),
            {
                "passed": False,
                "payload": {"passed": False, "failure_class": "PATCH_RUNTIME"},
                "failure_class": FailureClass.PATCH_RUNTIME,
                "route": "diagnose.refine",
            },
        )(),
    )

    phase, _ = resolve_resume_phase_entry(state_dir)
    assert phase in {"plan", "check", "repair"}

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

    assert regen_calls
    assert outcome.chain is not None
