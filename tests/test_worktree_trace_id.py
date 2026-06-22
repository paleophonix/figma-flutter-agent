"""Tests for worktree-scoped PostHog trace id persistence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig, DebugPipelineTraceConfig
from figma_flutter_agent.config.models import AgentYamlConfig
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.dev.opencode.workspace import (
    WORKTREE_TRACE_ID_KEY,
    assign_worktree_trace_id,
    load_worktree_trace_id,
    load_repair_workspace,
    prepare_workspace,
)
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult


def _gate(tmp_path: Path) -> RunGateResult:
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    root = tmp_path / "screen"
    root.mkdir(exist_ok=True)
    return RunGateResult(
        feature="login_version_1",
        verdict=FailureClass.CAPTURE_FAILED,
        case_mode="FORENSIC",
        agent_board="forensic",
        screen_root=root,
        pipeline_run_id="run-1",
        candidate_build_run_id="run-1",
        committed_build_run_id="run-1",
        served_build_run_id="run-1",
        writeback="committed",
        candidate_available=False,
        manifest_path=manifest,
        allowed_questions=(),
        forbidden_questions=(),
    )


def test_prepare_workspace_assigns_posthog_trace_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.workspace.agent_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.workspace.create_repair_worktree",
        lambda repo, case_id: (tmp_path / ".worktrees" / case_id).mkdir(parents=True) or tmp_path / ".worktrees" / case_id,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.workspace.allocate_repair_case_id",
        lambda *args, **kwargs: "0621-1200-limbo-login",
    )
    project = tmp_path / "limbo"
    feature = "login_version_1"
    (tmp_path / ".debug" / "limbo" / feature).mkdir(parents=True)
    workspace = prepare_workspace(project_dir=project, feature=feature, gate=_gate(tmp_path))
    trace_id = load_worktree_trace_id(workspace.manifest_path)
    assert trace_id
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    assert manifest[WORKTREE_TRACE_ID_KEY] == trace_id


def test_assign_worktree_trace_id_is_stable(tmp_path: Path) -> None:
    manifest_path = tmp_path / ".repair" / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"case_id": "x"}), encoding="utf-8")
    first = assign_worktree_trace_id(manifest_path, trace_id="trace-abc123456789")
    second = assign_worktree_trace_id(manifest_path, trace_id="trace-should-not-replace")
    assert first == "trace-abc123456789"
    assert second == "trace-abc123456789"


def test_maybe_start_reuses_worktree_trace_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.trace.agent_repo_root",
        lambda: tmp_path,
    )
    agent = AgentYamlConfig(
        debug_pipeline=DebugPipelineConfig(
            trace=DebugPipelineTraceConfig(posthog=False),
        ),
    )
    settings = Settings(agent=agent)
    project_dir = tmp_path / "limbo"
    project_dir.mkdir()
    recorder = RepairTraceRecorder.maybe_start(
        settings=settings,
        project_dir=project_dir,
        feature="login_version_1",
        trace_id="trace-deadbeef01",
    )
    assert recorder is not None
    assert recorder.trace_id == "trace-deadbeef01"
    manifest = json.loads((recorder.root_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["posthog_trace_id"] == "trace-deadbeef01"


def test_load_repair_workspace_reads_trace_id(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    repair_root = worktree / ".repair"
    manifest_path = repair_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "project": "limbo",
                "feature": "login",
                "posthog_trace_id": "trace-persisted1",
                "debug_mirror": ".repair/debug/limbo/login",
            }
        ),
        encoding="utf-8",
    )
    (repair_root / "debug" / "limbo" / "login").mkdir(parents=True)
    workspace = load_repair_workspace(worktree)
    assert load_worktree_trace_id(workspace.manifest_path) == "trace-persisted1"


@pytest.mark.asyncio
async def test_resume_reuses_worktree_trace_id_in_observability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figma_flutter_agent.dev.opencode.pipeline import run_repair_pipeline
    from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace

    project = tmp_path / "limbo"
    feature = "login"
    worktree = tmp_path / "wt"
    repair_root = worktree / ".repair"
    state_dir = repair_root / "state"
    debug_mirror = repair_root / "debug" / "limbo" / feature
    debug_mirror.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    (debug_mirror / "processed.json").write_text("{}", encoding="utf-8")
    (debug_mirror / "last.log").write_text("ok\n", encoding="utf-8")
    manifest_path = repair_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "project": "limbo",
                "feature": feature,
                "posthog_trace_id": "trace-resume-01",
                "debug_mirror": debug_mirror.relative_to(worktree).as_posix(),
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "reasoning_chain.json").write_text(
        json.dumps({"steps": {"repair": {"noop": True}}}),
        encoding="utf-8",
    )
    (state_dir / "checkpoints.jsonl").write_text(
        '{"step": "repair", "loop_round": 1}\n',
        encoding="utf-8",
    )
    workspace = RepairWorkspace(
        case_id="case-1",
        worktree=worktree,
        repair_root=repair_root,
        state_dir=state_dir,
        debug_mirror=debug_mirror,
        manifest_path=manifest_path,
    )

    agent = AgentYamlConfig(
        debug_pipeline=DebugPipelineConfig(
            trace=DebugPipelineTraceConfig(enabled=False, posthog=True),
        ),
    )
    settings = Settings.model_construct(
        agent=agent,
        posthog_api_key=SecretStr("phc_test"),
        posthog_host="https://us.i.posthog.com",
    )

    class _Runner:
        def run_read_step(self, step, **kwargs):
            if step == "plan":
                return {
                    "step": "plan",
                    "steps": [
                        {
                            "order": 1,
                            "actionKind": "CODE_CHANGE",
                            "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                            "tests": ["tests/test_debug_pipeline_models.py"],
                        }
                    ],
                }
            raise AssertionError(step)

    async def _noop_repair(**_kwargs):
        return {"noop": True, "step": "repair", "filesTouched": []}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_repair_write",
        _noop_repair,
    )

    with patch("figma_flutter_agent.dev.opencode.repair_log.capture_ai_trace") as mock_trace:
        await run_repair_pipeline(
            settings=settings,
            project_dir=project,
            feature=feature,
            runner=_Runner(),
            skip_opencode_repair=False,
            existing_workspace=workspace,
            resume=True,
            command="headless",
        )
        mock_trace.assert_not_called()
