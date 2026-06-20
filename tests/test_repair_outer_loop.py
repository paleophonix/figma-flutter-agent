"""Adversarial tests for repair pipeline outer loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.config.debug_pipeline import DebugPipelineLoopsConfig
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.debug.run_meta import write_run_meta
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.pipeline import run_repair_pipeline
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_budget,
    resolve_from_review,
)


class _LoopOnceRunner:
    """Return LOOP on first review, CONTINUE on second."""

    def __init__(self) -> None:
        self.review_calls = 0
        self.diagnose_calls = 0

    def run_read_step(self, step, *, board, run_context, chain, user_prompt, figma_png=None, **kwargs):
        if step == "recognise":
            return {"step": "recognise", "symptoms": [{"id": "s1"}]}
        if step == "inspect":
            return {"step": "inspect", "entities": [{"id": "e1"}]}
        if step == "diagnose":
            self.diagnose_calls += 1
            return {"step": "diagnose", "laws": [{"id": "law_a"}], "blocked": False}
        if step == "plan":
            return {
                "step": "plan",
                "steps": [
                    {
                        "order": 1,
                        "lawId": "law_a",
                        "tests": ["tests/test_x.py"],
                        "targetFiles": ["src/figma_flutter_agent/x.py"],
                    },
                ],
            }
        if step == "review":
            self.review_calls += 1
            if self.review_calls == 1:
                return {
                    "step": "review",
                    "decision": "LOOP",
                    "reason_code": "CAPTURE_GATE_FAILED",
                    "route": "diagnose.refine",
                }
            return {
                "step": "review",
                "decision": "CONTINUE",
                "reason_code": "REVIEW_OK",
                "route": "summarize",
            }
        msg = f"unexpected step {step}"
        raise AssertionError(msg)


def _prepare_screen(tmp_path: Path, *, capture_ok: bool = True) -> tuple[Path, str]:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "screen.dart").write_text("// FFA_RUN_ID: run_abc\n", encoding="utf-8")
    ratio = 0.01 if capture_ok else 0.9
    (root / "capture.json").write_text(
        json.dumps({"captured_run_id": "run_abc", "changedRatio": ratio}),
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
async def test_review_loop_reenters_diagnose(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, feature = _prepare_screen(tmp_path, capture_ok=True)
    runner = _LoopOnceRunner()
    settings = load_settings()
    loops = settings.agent.debug_pipeline.loops.model_copy(
        update={"max_diagnose_refinements_per_root": 2},
    )
    monkeypatch.setattr(
        settings.agent.debug_pipeline,
        "loops",
        loops,
    )
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=runner,
        skip_opencode_repair=True,
        command="headless",
    )
    assert runner.diagnose_calls >= 2
    assert runner.review_calls >= 2
    assert not outcome.stopped
    assert outcome.stop_reason != "review_loop"


def test_same_root_hash_budget_stops_human() -> None:
    state = LoopBudgetState()
    loops = DebugPipelineLoopsConfig(same_root_hash_repeat_without_improvement=2)
    state.record_root_hash("sha256:abc", improved=False)
    state.record_root_hash("sha256:abc", improved=False)
    assert state.same_root_exhausted(loops)
    decision = apply_budget(RouteDecision.DIAGNOSE_REFINE, state, loops)
    assert decision == RouteDecision.STOP_HUMAN


def test_resolve_review_loop_route() -> None:
    decision = resolve_from_review(
        {"decision": "LOOP", "route": "diagnose.refine", "reason_code": "X"},
    )
    assert decision == RouteDecision.DIAGNOSE_REFINE


@pytest.mark.asyncio
async def test_repair_gates_failure_stops_before_summarize(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
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
                            "tests": ["tests/test_x.py"],
                            "targetFiles": ["src/figma_flutter_agent/x.py"],
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

    class _FailingOpenCode:
        def bind_worktree(self, directory: str | None) -> None:
            return None

        async def create_session(self, *, title: str) -> str:
            return "sess"

        async def prompt_message(self, session_id: str, *, text: str, **kwargs) -> dict:
            return {"parts": [{"type": "text", "text": "done"}]}

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.phases.run_repair_gates",
        lambda *_args, **_kwargs: type(
            "Gate",
            (),
            {
                "passed": False,
                "ruff_ok": False,
                "pytest_ok": True,
                "ruff_output": "",
                "pytest_output": "",
                "touched_paths": ("tests/test_x.py",),
            },
        )(),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.phases.diff_touched_paths",
        lambda *_args, **_kwargs: ["src/figma_flutter_agent/x.py"],
    )

    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=_Runner(),
        opencode_client=_FailingOpenCode(),
        skip_opencode_repair=False,
        command="headless",
    )
    assert outcome.stopped
    assert outcome.stop_reason == "repair_gates_failed"
