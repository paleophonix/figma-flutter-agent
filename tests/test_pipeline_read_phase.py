"""Tests for pipeline with mock step runner."""

from __future__ import annotations

import json

import pytest

from figma_flutter_agent.config import load_settings
from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.debug.run_meta import write_run_meta
from figma_flutter_agent.dev.opencode.pipeline import run_repair_pipeline


class _MockRunner:
    def run_read_step(
        self,
        step,
        *,
        board,
        run_context,
        chain,
        user_prompt,
        figma_png=None,
        flutter_render_png=None,
        outer_round=1,
    ):
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
                        "tests": ["tests/test_debug_pipeline_models.py"],
                        "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                    },
                ],
            },
            "review": {
                "step": "review",
                "decision": "CONTINUE",
                "reason_code": "REVIEW_OK",
                "route": "summarize",
            },
            "summarize": {
                "step": "summarize",
                "ticket_summary": "RU ticket body",
                "dev_summary": "EN dev body",
            },
        }
        return payloads[step]


@pytest.mark.asyncio
async def test_pipeline_mock_runner_completes(tmp_path, monkeypatch) -> None:
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

    from figma_flutter_agent.dev.opencode.capture_gate import CaptureGateResult
    from figma_flutter_agent.dev.opencode.check import CheckResult
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_check_gate",
        lambda *_args, **_kwargs: CheckResult(
            passed=True,
            failure_class=FailureClass.FRESH_OK,
            route="capture",
            payload={"step": "check", "passed": True, "failure_class": "FRESH_OK"},
        ),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_capture_gate",
        lambda *_args, **_kwargs: CaptureGateResult(
            passed=True,
            kind="verified",
            payload={"step": "capture", "passed": True},
        ),
    )

    settings = load_settings()
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=_MockRunner(),
        skip_opencode_repair=True,
        command="headless",
    )
    assert outcome.workspace is not None
    assert (outcome.workspace.state_dir / "summarize.json").is_file()
