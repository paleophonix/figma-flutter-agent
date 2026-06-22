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
                        "tests": ["tests/test_debug_pipeline_models.py"],
                        "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
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
        if step == "summarize":
            return {
                "step": "summarize",
                "ticket_summary": "RU ticket body",
                "dev_summary": "EN dev body",
            }
        msg = f"unexpected step {step}"
        raise AssertionError(msg)


def _prepare_screen(tmp_path: Path, *, capture_ok: bool = True) -> tuple[Path, str]:
    project = tmp_path / "demo_app"
    feature = "login"
    root = screen_root(project, feature)
    root.mkdir(parents=True)
    (root / "processed.json").write_text("{}", encoding="utf-8")
    (root / "figma.png").write_bytes(b"\x89PNG\r\n\x1a\n")
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
                            "actionKind": "CODE_CHANGE",
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
                },
                "summarize": {
                    "step": "summarize",
                    "dev_summary": "EN dev",
                    "ticket_summary": "RU ticket",
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

        async def session_diff(self, session_id: str) -> list:
            return []

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
                "touched_paths": ("tests/test_debug_pipeline_models.py",),
                "skipped": False,
            },
        )(),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.phases.diff_touched_since_baseline",
        lambda *_args, **_kwargs: ["src/figma_flutter_agent/stages/write.py"],
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


@pytest.mark.asyncio
async def test_review_override_persisted(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, feature = _prepare_screen(tmp_path, capture_ok=False)
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
                            "tests": ["tests/test_debug_pipeline_models.py"],
                            "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                        },
                    ],
                },
                "review": {
                    "step": "review",
                    "decision": "CONTINUE",
                    "reason_code": "REVIEW_OK",
                },
                "summarize": {"step": "summarize", "dev_summary": "dev", "ticket_summary": "ticket"},
            }
            return payloads[step]

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
            passed=False,
            kind="failed",
            payload={"step": "capture", "passed": False},
        ),
    )
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=_Runner(),
        skip_opencode_repair=True,
        command="headless",
    )
    assert outcome.workspace is not None
    review_path = outcome.workspace.state_dir / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["decision"] == "LOOP"
    assert review.get("overridden") is True
    assert outcome.chain is not None
    assert outcome.chain.steps["review"]["decision"] == "LOOP"


@pytest.mark.asyncio
async def test_fix_exhausted_routes_diagnose_refine(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, feature = _prepare_screen(tmp_path)
    settings = load_settings()
    loops = settings.agent.debug_pipeline.loops.model_copy(update={"max_fix_attempts": 1})
    monkeypatch.setattr(settings.agent.debug_pipeline, "loops", loops)

    class _Runner:
        diagnose_calls = 0

        def run_read_step(self, step, *, board, run_context, chain, user_prompt, figma_png=None, **kwargs):
            if step == "diagnose":
                self.diagnose_calls += 1
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
            }
            if step in payloads:
                return payloads[step]
            msg = f"unexpected step {step}"
            raise AssertionError(msg)

    runner = _Runner()

    from figma_flutter_agent.dev.opencode.check import CheckResult
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_check_gate",
        lambda *_args, **_kwargs: CheckResult(
            passed=False,
            failure_class=FailureClass.PATCH_CODE_EMIT,
            route="fix",
            payload={
                "step": "check",
                "passed": False,
                "failure_class": "PATCH_CODE_EMIT",
                "route": "fix",
                "evidence": ["dart-errors.json"],
            },
        ),
    )
    async def _mock_fix_write(**_kwargs):
        return ("noop fix", None)

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_fix_write",
        _mock_fix_write,
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
    assert outcome.loop_rounds >= 2


@pytest.mark.asyncio
async def test_repair_noop_does_not_advance_correction_cycle_for_fusion(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repair retry micro-loops must not bump Fusion escalation cycle."""
    project, feature = _prepare_screen(tmp_path)
    settings = load_settings()
    loops = settings.agent.debug_pipeline.loops.model_copy(
        update={
            "max_diagnose_refinements_per_root": 5,
            "max_repair_retries_per_plan": 1,
        },
    )
    monkeypatch.setattr(settings.agent.debug_pipeline, "loops", loops)

    class _Runner:
        plan_calls = 0
        fusion_rounds: list[int] = []

        def run_read_step(
            self,
            step,
            *,
            board,
            run_context,
            chain,
            user_prompt,
            figma_png=None,
            outer_round=1,
            **kwargs,
        ):
            if step == "plan":
                self.plan_calls += 1
                self.fusion_rounds.append(outer_round)
                return {
                    "step": "plan",
                    "steps": [
                        {
                            "order": 1,
                            "lawId": "law_a",
                            "tests": ["tests/test_debug_pipeline_models.py"],
                            "targetFiles": ["src/figma_flutter_agent/stages/write.py"],
                        },
                    ],
                }
            payloads = {
                "recognise": {"step": "recognise", "symptoms": [{"id": "s1"}]},
                "inspect": {"step": "inspect", "entities": [{"id": "e1"}]},
                "diagnose": {"step": "diagnose", "laws": [{"id": "law_a"}], "blocked": False},
            }
            if step in payloads:
                return payloads[step]
            msg = f"unexpected step {step}"
            raise AssertionError(msg)

    runner = _Runner()
    repair_calls = 0

    async def _incomplete_repair_write(**_kwargs):
        nonlocal repair_calls
        repair_calls += 1
        return {
            "noop": True,
            "incomplete": True,
            "noop_reason": "steps_exhausted",
            "agent_summary": "Maximum steps reached",
            "filesTouched": [],
            "step": "repair",
        }

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.pipeline.orchestrator.run_repair_write",
        _incomplete_repair_write,
    )

    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=runner,
        skip_opencode_repair=False,
        command="headless",
    )
    assert runner.plan_calls == 1
    assert repair_calls >= 2
    assert runner.fusion_rounds == [1]
    assert outcome.loop_rounds == 1
    assert outcome.stop_reason == "repair_incomplete"


def _mock_check_capture_pass(monkeypatch: pytest.MonkeyPatch) -> None:
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


@pytest.mark.asyncio
async def test_empty_diagnose_laws_retries_before_plan(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty laws[] with compiler inspect anchors must retry diagnose, not burn plan LLM."""
    project, feature = _prepare_screen(tmp_path)
    settings = load_settings()
    loops = settings.agent.debug_pipeline.loops.model_copy(
        update={"max_diagnose_refinements_per_root": 2},
    )
    monkeypatch.setattr(settings.agent.debug_pipeline, "loops", loops)
    _mock_check_capture_pass(monkeypatch)

    class _Runner:
        diagnose_calls = 0
        plan_calls = 0

        def run_read_step(
            self,
            step,
            *,
            board,
            run_context,
            chain,
            user_prompt,
            figma_png=None,
            **kwargs,
        ):
            if step == "recognise":
                return {
                    "step": "recognise",
                    "symptoms": [{"id": "s1"}],
                    "blocked": True,
                }
            if step == "inspect":
                return {
                    "step": "inspect",
                    "entities": [
                        {
                            "id": "e1",
                            "repoPaths": [
                                "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                            ],
                        }
                    ],
                }
            if step == "diagnose":
                self.diagnose_calls += 1
                if self.diagnose_calls == 1:
                    return {"step": "diagnose", "laws": [], "blocked": False}
                return {
                    "step": "diagnose",
                    "laws": [{"id": "law_flex_overflow"}],
                    "blocked": False,
                }
            if step == "plan":
                self.plan_calls += 1
                return {
                    "step": "plan",
                    "steps": [
                        {
                            "order": 1,
                            "lawId": "law_flex_overflow",
                            "tests": ["tests/test_debug_pipeline_models.py"],
                            "targetFiles": [
                                "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                            ],
                        },
                    ],
                }
            if step == "review":
                return {
                    "step": "review",
                    "decision": "CONTINUE",
                    "reason_code": "REVIEW_OK",
                    "route": "summarize",
                }
            if step == "summarize":
                return {
                    "step": "summarize",
                    "ticket_summary": "RU",
                    "dev_summary": "EN",
                }
            msg = f"unexpected step {step}"
            raise AssertionError(msg)

    runner = _Runner()
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=runner,
        skip_opencode_repair=True,
        command="headless",
    )
    assert runner.diagnose_calls == 2
    assert runner.plan_calls == 1
    assert not outcome.stopped


@pytest.mark.asyncio
async def test_empty_diagnose_laws_stops_without_plan_llm(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When diagnose refine budget is exhausted, stop with diagnose_empty_laws (no plan retries)."""
    project, feature = _prepare_screen(tmp_path)
    settings = load_settings()
    loops = settings.agent.debug_pipeline.loops.model_copy(
        update={"max_diagnose_refinements_per_root": 0},
    )
    monkeypatch.setattr(settings.agent.debug_pipeline, "loops", loops)

    class _Runner:
        plan_calls = 0

        def run_read_step(self, step, *, board, run_context, chain, user_prompt, figma_png=None, **kwargs):
            if step == "recognise":
                return {"step": "recognise", "symptoms": [{"id": "s1"}], "blocked": True}
            if step == "inspect":
                return {
                    "step": "inspect",
                    "entities": [
                        {
                            "id": "e1",
                            "repoPaths": [
                                "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                            ],
                        }
                    ],
                }
            if step == "diagnose":
                return {"step": "diagnose", "laws": [], "blocked": False}
            if step == "plan":
                self.plan_calls += 1
                raise AssertionError("plan LLM must not run when diagnose laws are empty")
            msg = f"unexpected step {step}"
            raise AssertionError(msg)

    runner = _Runner()
    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project,
        feature=feature,
        runner=runner,
        skip_opencode_repair=True,
        command="headless",
    )
    assert runner.plan_calls == 0
    assert outcome.stopped
    assert outcome.stop_reason == "diagnose_empty_laws"