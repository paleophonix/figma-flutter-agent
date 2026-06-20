"""Tests for repair pipeline disk traces."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig, DebugPipelineTraceConfig
from figma_flutter_agent.config.models import AgentYamlConfig
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.trace import (
    RepairTraceRecorder,
    _digest_text,
    trace_run_folder_name,
)

_FOLDER_RE = re.compile(r"^\d{4}-\d{4}-[a-f0-9]{12}$")


def test_trace_run_folder_name_short_stamp() -> None:
    name = trace_run_folder_name(stamp="0620-1530", trace_id="abc123def456")
    assert name == "0620-1530-abc123def456"


def test_digest_text_stable() -> None:
    assert _digest_text("hello") == _digest_text("hello")
    assert len(_digest_text("hello")) == 16


def test_recorder_writes_manifest_and_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.trace.agent_repo_root",
        lambda: tmp_path,
    )
    agent = AgentYamlConfig(
        debug_pipeline=DebugPipelineConfig(
            trace=DebugPipelineTraceConfig(posthog=False, store_prompts="hash"),
        ),
    )
    settings = Settings(agent=agent)
    project_dir = tmp_path / "demo_app"
    project_dir.mkdir()

    recorder = RepairTraceRecorder.maybe_start(
        settings=settings,
        project_dir=project_dir,
        feature="login_version_1",
    )
    assert recorder is not None
    assert _FOLDER_RE.match(recorder.root_dir.name)
    assert recorder.root_dir.parent.name == "login_version_1"

    recorder.record_step(
        "recognise",
        {"step": "recognise", "ok": True},
        duration_ms=12.5,
        system_prompt="sys",
        user_prompt="user",
        meta={"model": "deepseek/deepseek-v4-pro"},
    )
    recorder.finish(outcome={"stopped": False}, chain={"recognise": {"ok": True}})

    manifest = json.loads((recorder.root_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["feature"] == "login_version_1"
    assert re.fullmatch(r"\d{4}-\d{4}", manifest["folder_stamp"])
    step_dirs = list((recorder.root_dir / "steps").iterdir())
    assert len(step_dirs) == 1
    prompt = json.loads((step_dirs[0] / "prompt.json").read_text(encoding="utf-8"))
    assert prompt["system_sha256_16"] == _digest_text("sys")
    assert (recorder.root_dir / "chain.json").is_file()


def test_recorder_disabled_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.trace.agent_repo_root",
        lambda: tmp_path,
    )
    agent = AgentYamlConfig(
        debug_pipeline=DebugPipelineConfig(trace=DebugPipelineTraceConfig(enabled=False)),
    )
    settings = Settings(agent=agent)
    project_dir = tmp_path / "demo_app"
    project_dir.mkdir()
    assert (
        RepairTraceRecorder.maybe_start(
            settings=settings,
            project_dir=project_dir,
            feature="x",
        )
        is None
    )
