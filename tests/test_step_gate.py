"""Tests for repair pipeline step confirmation gates."""

from __future__ import annotations

import json

import pytest

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.debug.run_meta import write_run_meta
from figma_flutter_agent.dev.opencode.pipeline import run_repair_pipeline
from figma_flutter_agent.dev.opencode.step_gate import (
    AutoApproveStepGate,
    resolve_round_gate,
    resolve_step_gate,
)


@pytest.mark.asyncio
async def test_auto_approve_gate() -> None:
    gate = AutoApproveStepGate()
    assert await gate.approve("plan") is True


@pytest.mark.asyncio
async def test_resolve_step_gate_wizard_only() -> None:
    assert resolve_step_gate(confirm_next_step=True, command="wizard_debug") is not None
    assert resolve_step_gate(confirm_next_step=True, command="headless") is None
    assert resolve_step_gate(confirm_next_step=False, command="wizard_debug") is None


@pytest.mark.asyncio
async def test_resolve_round_gate_wizard_only() -> None:
    assert resolve_round_gate(confirm_next_round=True, command="wizard_debug") is not None
    assert resolve_round_gate(confirm_next_round=True, command="headless") is None
    assert resolve_round_gate(confirm_next_round=False, command="wizard_debug") is None


class _DenyGate:
    async def approve(self, step: str, *, preview: dict | None = None) -> bool:
        _ = step, preview
        return False


@pytest.mark.asyncio
async def test_pipeline_stops_when_step_gate_denies(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.trace.agent_repo_root",
        lambda: tmp_path,
    )
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "screen.dart").write_text("// FFA_RUN_ID: run_abc\n", encoding="utf-8")
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

    settings = load_settings()
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        skip_opencode_repair=True,
        step_gate=_DenyGate(),
    )
    assert outcome.stopped is True
    assert outcome.stop_reason == "user_declined_recognise"
