"""Tests for post-repair check gate and repair noop detection."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.debug.paths import RAW_JSON, screen_root
from figma_flutter_agent.debug.run_meta import write_run_meta
from figma_flutter_agent.dev.opencode.check import compiler_repair_verified, run_check_gate
from figma_flutter_agent.dev.opencode.pipeline import run_repair_pipeline
from figma_flutter_agent.dev.opencode.regenerate_mirror import (
    refresh_debug_mirror,
    run_regenerate_after_compiler_repair,
)
from figma_flutter_agent.dev.opencode.run_gate import evaluate_run_gate
from figma_flutter_agent.dev.opencode.workspace import prepare_workspace
from figma_flutter_agent.pipeline.result import PipelineResult


def test_compiler_repair_verified_requires_plan_target_touch() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                "tests": ["tests/test_write_gate.py"],
            },
        ],
    }
    repair_ok = {
        "skipped": False,
        "filesTouched": ["src/figma_flutter_agent/stages/write.py"],
        "gates": {"passed": True},
    }
    repair_wrong_file = {
        "skipped": False,
        "filesTouched": ["tests/test_write_gate.py"],
        "gates": {"passed": True},
    }
    assert compiler_repair_verified(repair_ok, plan)
    assert not compiler_repair_verified(repair_wrong_file, plan)


def test_run_check_gate_passes_on_compiler_repair_proof(tmp_path: Path) -> None:
    mirror = tmp_path / "debug" / "limbo" / "login"
    mirror.mkdir(parents=True)
    (mirror / "dart-errors.json").write_text(
        json.dumps([{"message": "uri_does_not_exist"}]),
        encoding="utf-8",
    )
    state = tmp_path / "state"
    state.mkdir()
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                "tests": ["tests/test_write_gate.py"],
            },
        ],
    }
    repair = {
        "skipped": False,
        "filesTouched": ["src/figma_flutter_agent/stages/write.py"],
        "gates": {"passed": True},
    }
    result = run_check_gate(
        mirror,
        state_dir=state,
        repair_payload=repair,
        plan_payload=plan,
        allow_stale_mirror_bypass=True,
    )
    assert result.passed
    assert result.payload.get("verifiedBy") == "repair_gates"
    assert result.payload.get("mirrorStale") is True


def test_run_check_gate_reads_stale_mirror_without_repair_proof(tmp_path: Path) -> None:
    mirror = tmp_path / "debug" / "limbo" / "login"
    mirror.mkdir(parents=True)
    (mirror / "dart-errors.json").write_text(
        json.dumps([{"message": "uri_does_not_exist"}]),
        encoding="utf-8",
    )
    state = tmp_path / "state"
    state.mkdir()
    result = run_check_gate(mirror, state_dir=state)
    assert not result.passed
    assert result.route == "fix"


def _prepare_screen(tmp_path: Path) -> tuple[Path, str]:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "screen.dart").write_text("// FFA_RUN_ID: run_abc\n", encoding="utf-8")
    (root / "dart-errors.json").write_text(
        json.dumps([{"message": "uri_does_not_exist"}]),
        encoding="utf-8",
    )
    (root / "capture.json").write_text(
        json.dumps({"captured_run_id": "run_abc", "changedRatio": 0.01}),
        encoding="utf-8",
    )
    write_run_meta(
        project,
        feature,
        pipeline_run_id="run_abc",
        writeback="committed",
        written_files=["lib/x.dart"],
        committed_build_run_id="run_abc",
    )
    return project, feature


@pytest.mark.asyncio
async def test_repair_noop_stops_before_fix_theater(tmp_path: Path) -> None:
    project, feature = _prepare_screen(tmp_path)
    settings = load_settings()

    class _Runner:
        def run_read_step(self, step, *, board, run_context, chain, user_prompt, figma_png=None, **kwargs):
            payloads = {
                "recognise": {"step": "recognise", "symptoms": [{"id": "s1"}]},
                "inspect": {"step": "inspect", "entities": [{"id": "e1"}]},
                "diagnose": {"step": "diagnose", "laws": [{"id": "law_a"}], "blocked": False},
                "plan": {
                    "step": "plan",
                    "steps": [
                        {
                            "order": 1,
                            "lawId": "law_a",
                            "actionKind": "CODE_CHANGE",
                            "tests": ["tests/test_write_gate.py"],
                            "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                        },
                    ],
                },
                "review": {
                    "step": "review",
                    "decision": "CONTINUE",
                    "reason_code": "REVIEW_OK",
                },
            }
            return payloads[step]

    class _NoopOpenCode:
        def bind_worktree(self, directory: str | None) -> None:
            return None

        async def create_session(self, *, title: str) -> str:
            return "sess"

        async def prompt_message(self, session_id: str, *, text: str, **kwargs) -> dict:
            return {"parts": [{"type": "text", "text": "done"}]}

    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=_Runner(),
        opencode_client=_NoopOpenCode(),
        skip_opencode_repair=False,
        command="headless",
    )
    assert outcome.stopped
    assert outcome.stop_reason == "repair_noop"


@pytest.mark.asyncio
async def test_regenerate_refreshes_mirror_before_check(tmp_path: Path, monkeypatch) -> None:
    project, feature = _prepare_screen(tmp_path)
    (screen_root(project, feature) / RAW_JSON).write_text('{"id": "1:2"}', encoding="utf-8")
    (screen_root(project, feature) / "llm_validated.json").write_text("{}", encoding="utf-8")

    gate = evaluate_run_gate(project, feature)
    workspace = prepare_workspace(project_dir=project, feature=feature, gate=gate)
    workspace.debug_mirror.mkdir(parents=True, exist_ok=True)
    shutil.copy2(screen_root(project, feature) / RAW_JSON, workspace.debug_mirror / RAW_JSON)
    shutil.copy2(
        screen_root(project, feature) / "llm_validated.json",
        workspace.debug_mirror / "llm_validated.json",
    )

    async def _fake_pipeline(*_args, **_kwargs):
        root = screen_root(project, feature)
        (root / "dart-errors.json").write_text("[]", encoding="utf-8")
        return PipelineResult(clean_tree={}, tokens={}, run_id="regen_run")  # type: ignore[arg-type]

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.regenerate_mirror.run_pipeline",
        _fake_pipeline,
    )
    settings = load_settings()
    result = await run_regenerate_after_compiler_repair(
        workspace=workspace,
        settings=settings,
        project_dir=project,
        feature=feature,
    )
    assert result.passed
    mirror_errors = json.loads((workspace.debug_mirror / "dart-errors.json").read_text())
    assert mirror_errors == []


@pytest.mark.asyncio
async def test_pipeline_regenerates_after_compiler_repair(tmp_path: Path, monkeypatch) -> None:
    project, feature = _prepare_screen(tmp_path)
    (screen_root(project, feature) / RAW_JSON).write_text('{"id": "1:2"}', encoding="utf-8")
    settings = load_settings()

    class _Runner:
        def run_read_step(self, step, *, board, run_context, chain, user_prompt, figma_png=None, **kwargs):
            payloads = {
                "recognise": {"step": "recognise", "symptoms": [{"id": "s1"}]},
                "inspect": {"step": "inspect", "entities": [{"id": "e1"}]},
                "diagnose": {"step": "diagnose", "laws": [{"id": "law_a"}], "blocked": False},
                "plan": {
                    "step": "plan",
                    "steps": [
                        {
                            "order": 1,
                            "lawId": "law_a",
                            "actionKind": "CODE_CHANGE",
                            "tests": ["tests/test_write_gate.py"],
                            "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                        },
                    ],
                },
                "review": {
                    "step": "review",
                    "decision": "CONTINUE",
                    "reason_code": "REVIEW_OK",
                },
            }
            return payloads[step]

    class _RepairOpenCode:
        def bind_worktree(self, directory: str | None) -> None:
            return None

        async def create_session(self, *, title: str) -> str:
            return "sess"

        async def prompt_message(self, session_id: str, *, text: str, **kwargs) -> dict:
            return {"parts": [{"type": "text", "text": "done"}]}

    async def _fake_regen(*, workspace, settings, project_dir, feature):
        root = screen_root(project_dir, feature)
        (root / "dart-errors.json").write_text("[]", encoding="utf-8")
        refresh_debug_mirror(workspace=workspace, project_dir=project_dir, feature=feature)
        return type(
            "Regen",
            (),
            {
                "passed": True,
                "payload": {"step": "regenerate", "passed": True},
            },
        )()

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.phases.diff_touched_paths",
        lambda *_args, **_kwargs: ["src/figma_flutter_agent/stages/write.py"],
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.phases.run_repair_gates",
        lambda *_args, **_kwargs: type(
            "Gate",
            (),
            {
                "passed": True,
                "ruff_ok": True,
                "pytest_ok": True,
                "ruff_output": "",
                "pytest_output": "",
                "touched_paths": ("tests/test_write_gate.py",),
            },
        )(),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_regenerate_after_compiler_repair",
        _fake_regen,
    )

    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=_Runner(),
        opencode_client=_RepairOpenCode(),
        skip_opencode_repair=False,
        command="headless",
    )
    assert not outcome.stopped
    assert outcome.chain is not None
    assert outcome.chain.steps.get("regenerate", {}).get("passed") is True
    assert outcome.chain.steps.get("check", {}).get("passed") is True
