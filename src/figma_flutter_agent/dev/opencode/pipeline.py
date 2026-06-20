"""OpenCode repair pipeline orchestrator (M0–M6)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.dev.opencode.capture_gate import run_capture_gate
from figma_flutter_agent.dev.opencode.check import run_check_gate
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.fix_runner import run_fix_attempt
from figma_flutter_agent.dev.opencode.gates import run_repair_gates
from figma_flutter_agent.dev.opencode.opencode_policy import prompt_options_for_write_step
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.run_gate import RunGateResult, evaluate_run_gate
from figma_flutter_agent.dev.opencode.step_gate import StepGate, resolve_step_gate
from figma_flutter_agent.dev.opencode.step_runner import (
    OpenRouterStepRunner,
    StepRunner,
    write_step_state,
)
from figma_flutter_agent.dev.opencode.summarize_router import (
    apply_review_overrides,
    route_summarize,
)
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace, prepare_workspace
from figma_flutter_agent.errors import FigmaFlutterError


class OpenCodeRepairClient(Protocol):
    """Minimal OpenCode client for repair build step."""

    def bind_worktree(self, directory: str | None) -> None: ...

    async def create_session(self, *, title: str) -> str: ...

    async def prompt_message(
        self,
        session_id: str,
        *,
        text: str,
        agent: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]: ...


@dataclass
class PipelineOutcome:
    """Final pipeline run outcome."""

    gate: RunGateResult
    workspace: RepairWorkspace | None
    chain: ReasoningChain = field(default_factory=ReasoningChain)
    stopped: bool = False
    stop_reason: str = ""
    summarize_blocked: bool = False
    trace_dir: Path | None = None


def _run_context(gate: RunGateResult) -> dict[str, Any]:
    return {
        "case_mode": gate.case_mode,
        "agent_board": gate.agent_board,
        "run_manifest": gate.to_manifest_dict(),
        "allowed_questions": list(gate.allowed_questions),
        "forbidden_questions": list(gate.forbidden_questions),
    }


def _outcome_payload(outcome: PipelineOutcome) -> dict[str, Any]:
    return {
        "stopped": outcome.stopped,
        "stop_reason": outcome.stop_reason,
        "summarize_blocked": outcome.summarize_blocked,
        "gate_verdict": outcome.gate.verdict.value,
        "case_mode": outcome.gate.case_mode,
        "agent_board": outcome.gate.agent_board,
    }


def _read_step(
    runner: StepRunner,
    step: DebugPipelineStep,
    *,
    board: str,
    run_context: dict[str, Any],
    chain: ReasoningChain,
    state_dir: Path,
    user_prompt: str,
    figma_png: bytes | None = None,
) -> dict[str, Any]:
    payload = runner.run_read_step(
        step,
        board=board,
        run_context=run_context,
        chain=chain,
        user_prompt=user_prompt,
        figma_png=figma_png,
    )
    write_step_state(state_dir, step, payload)
    chain.append(step, payload)
    return payload


def _validate_plan(payload: dict[str, Any]) -> None:
    steps = payload.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise FigmaFlutterError("plan blocked: no steps")
    for item in steps:
        if not isinstance(item, dict):
            raise FigmaFlutterError("plan step must be object")
        if not item.get("lawId"):
            raise FigmaFlutterError("plan step missing lawId")
        if not item.get("tests"):
            raise FigmaFlutterError("plan step missing tests[]")


async def _require_step(
    step_gate: StepGate | None,
    step: str,
    outcome: PipelineOutcome,
    *,
    preview: dict[str, Any] | None = None,
) -> bool:
    if step_gate is None:
        return True
    if await step_gate.approve(step, preview=preview):
        return True
    outcome.stopped = True
    outcome.stop_reason = f"user_declined_{step}"
    return False


async def run_repair_pipeline(
    *,
    settings: Settings,
    project_dir: Path,
    feature: str,
    runner: StepRunner | None = None,
    opencode_client: OpenCodeRepairClient | None = None,
    skip_opencode_repair: bool = False,
    command: str = "wizard_debug",
    step_gate: StepGate | None = None,
) -> PipelineOutcome:
    """Execute full repair pipeline for one screen."""
    gate = evaluate_run_gate(project_dir, feature)
    outcome = PipelineOutcome(gate=gate, workspace=None)
    step_gate = resolve_step_gate(
        confirm_next_step=settings.agent.debug_pipeline.interactive.confirm_next_step,
        command=command,
        explicit=step_gate,
    )
    trace = RepairTraceRecorder.maybe_start(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        command=command,
        extra_manifest={
            "case_mode": gate.case_mode,
            "agent_board": gate.agent_board,
            "gate_verdict": gate.verdict.value,
        },
    )
    if trace is not None:
        outcome.trace_dir = trace.root_dir
        trace.record_step(
            "run_gate",
            gate.to_manifest_dict(),
            meta={"verdict": gate.verdict.value, "case_mode": gate.case_mode},
        )

    try:
        if gate.verdict in {FailureClass.NO_SERVE, FailureClass.UNKNOWN_BLOCKED}:
            outcome.stopped = True
            outcome.stop_reason = gate.verdict.value
            return outcome

        workspace = prepare_workspace(project_dir=project_dir, feature=feature, gate=gate)
        outcome.workspace = workspace
        if opencode_client is not None:
            opencode_client.bind_worktree(workspace.worktree.as_posix())
        chain = ReasoningChain()
        outcome.chain = chain
        chain_path = workspace.state_dir / "reasoning_chain.json"
        run_context = _run_context(gate)
        board = gate.agent_board
        step_runner = runner or OpenRouterStepRunner(
            settings,
            state_dir=workspace.state_dir,
            trace=trace,
        )

        figma_png: bytes | None = None
        figma_path = workspace.debug_mirror / "figma.png"
        if figma_path.is_file() and board == "screen":
            figma_png = figma_path.read_bytes()

        user_stub = (
            f"Repair case for feature {feature}. Use debug mirror at "
            f"{workspace.debug_mirror.relative_to(workspace.worktree).as_posix()}"
        )

        for step in ("recognise", "inspect", "diagnose"):
            if not await _require_step(step_gate, step, outcome):
                chain.save(chain_path)
                return outcome
            diagnose = _read_step(
                step_runner,
                step,  # type: ignore[arg-type]
                board=board,
                run_context=run_context,
                chain=chain,
                state_dir=workspace.state_dir,
                user_prompt=user_stub,
                figma_png=figma_png if step == "recognise" else None,
            )
            if step == "diagnose" and diagnose.get("blocked"):
                outcome.stopped = True
                outcome.stop_reason = "diagnose_blocked"
                chain.save(chain_path)
                return outcome

        if not await _require_step(step_gate, "plan", outcome):
            chain.save(chain_path)
            return outcome
        plan = _read_step(
            step_runner,
            "plan",
            board=board,
            run_context=run_context,
            chain=chain,
            state_dir=workspace.state_dir,
            user_prompt=user_stub,
        )
        _validate_plan(plan)

        pipeline_policy = settings.agent.debug_pipeline
        repair_prompt = prompt_options_for_write_step(pipeline_policy, step="repair")
        fix_prompt = prompt_options_for_write_step(pipeline_policy, step="fix")

        repair_payload: dict[str, Any] = {
            "step": "repair",
            "skipped": True,
            "notes": "OpenCode repair skipped",
        }
        if not skip_opencode_repair and opencode_client is not None:
            if not await _require_step(step_gate, "repair", outcome):
                chain.save(chain_path)
                return outcome
            repair_user_text = (
                "Execute repair plan in sandbox. Edit only src/figma_flutter_agent."
            )
            session_id = await opencode_client.create_session(title=f"repair-{feature}")
            repair_started = time.perf_counter()
            repair_response = await opencode_client.prompt_message(
                session_id,
                text=repair_user_text,
                agent=repair_prompt["agent"],
                model=repair_prompt["model"],
                reasoning_effort=repair_prompt["reasoning_effort"],
            )
            gate_result = run_repair_gates(workspace.worktree)
            repair_payload = {
                "step": "repair",
                "skipped": False,
                "session_id": session_id,
                "agent": repair_prompt["agent"],
                "model": repair_prompt["model"],
                "reasoning_effort": repair_prompt["reasoning_effort"],
                "gates": {"ruff": gate_result.ruff_ok, "pytest": gate_result.pytest_ok},
            }
            if trace is not None:
                trace.record_opencode(
                    "repair",
                    output=repair_payload,
                    response=repair_response,
                    duration_ms=(time.perf_counter() - repair_started) * 1000.0,
                    meta={
                        "agent": repair_prompt["agent"],
                        "model": repair_prompt["model"],
                        "reasoning_effort": repair_prompt["reasoning_effort"],
                    },
                    user_prompt=repair_user_text,
                )
        elif trace is not None:
            trace.record_step("repair", repair_payload, status="skipped")
        write_step_state(workspace.state_dir, "repair", repair_payload)
        chain.append("repair", repair_payload)

        if not await _require_step(step_gate, "check", outcome):
            chain.save(chain_path)
            return outcome
        check = run_check_gate(workspace.debug_mirror, state_dir=workspace.state_dir)
        chain.append("check", check.payload)
        if trace is not None:
            trace.record_step(
                "check",
                check.payload,
                status="ok" if check.passed else "blocked",
                meta={"route": check.route},
            )

        fix_attempts = 0
        max_fix = settings.agent.debug_pipeline.loops.max_fix_attempts
        while not check.passed and fix_attempts < max_fix:
            fix_attempts += 1
            fix_step = f"fix_{fix_attempts}"
            if not await _require_step(
                step_gate,
                fix_step,
                outcome,
                preview={"hint": f"(attempt {fix_attempts}/{max_fix})"},
            ):
                chain.save(chain_path)
                return outcome
            fix_summary = ""
            fix_response: dict[str, Any] = {}
            if not skip_opencode_repair and opencode_client is not None:
                fix_user_text = (
                    f"Emit-layer fix attempt {fix_attempts}. "
                    "Patch only .repair/candidate/planned_files per fix skill. "
                    f"Check summary: {json.dumps(check.payload, ensure_ascii=False)[:2000]}"
                )
                fix_session_id = await opencode_client.create_session(
                    title=f"fix-{feature}-{fix_attempts}",
                )
                fix_started = time.perf_counter()
                fix_response = await opencode_client.prompt_message(
                    fix_session_id,
                    text=fix_user_text,
                    agent=fix_prompt["agent"],
                    model=fix_prompt["model"],
                    reasoning_effort=fix_prompt["reasoning_effort"],
                )
                parts = fix_response.get("parts") or []
                for part in parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        fix_summary = str(part.get("text") or "")
                        break
                fix_payload_pending = {
                    "step": "fix",
                    "attempt": fix_attempts,
                    "session_id": fix_session_id,
                }
                if trace is not None:
                    trace.record_opencode(
                        f"fix_{fix_attempts}",
                        output=fix_payload_pending,
                        response=fix_response,
                        duration_ms=(time.perf_counter() - fix_started) * 1000.0,
                        meta={
                            "agent": fix_prompt["agent"],
                            "model": fix_prompt["model"],
                            "attempt": fix_attempts,
                        },
                        user_prompt=fix_user_text,
                    )
            fix = run_fix_attempt(
                state_dir=workspace.state_dir,
                check_payload=check.payload,
                attempt=fix_attempts,
                max_attempts=max_fix,
                opencode_summary=fix_summary,
            )
            chain.append("fix", fix.payload)
            if trace is not None and skip_opencode_repair:
                trace.record_step(f"fix_{fix_attempts}", fix.payload, status="skipped")
            elif trace is not None and opencode_client is None:
                trace.record_step(f"fix_{fix_attempts}", fix.payload)
            check = run_check_gate(workspace.debug_mirror, state_dir=workspace.state_dir)
            chain.append("check", check.payload)
            if trace is not None:
                trace.record_step(
                    f"check_{fix_attempts}",
                    check.payload,
                    status="ok" if check.passed else "blocked",
                )

        if not await _require_step(step_gate, "capture", outcome):
            chain.save(chain_path)
            return outcome
        capture = run_capture_gate(
            workspace.debug_mirror,
            state_dir=workspace.state_dir,
            served_run_id=gate.served_build_run_id,
            committed_run_id=gate.committed_build_run_id,
        )
        chain.append("capture", capture.payload)
        if trace is not None:
            trace.record_step(
                "capture",
                capture.payload,
                status="ok" if capture.passed else "blocked",
            )

        if not await _require_step(step_gate, "review", outcome):
            chain.save(chain_path)
            return outcome
        review = _read_step(
            step_runner,
            "review",
            board=board,
            run_context=run_context,
            chain=chain,
            state_dir=workspace.state_dir,
            user_prompt=user_stub,
        )
        review = apply_review_overrides(
            review,
            check_passed=check.passed,
            capture_passed=capture.passed,
            case_mode=gate.case_mode,
        )
        write_step_state(workspace.state_dir, "review", review)
        chain.append("review", review)

        if str(review.get("decision", "")).upper() == "LOOP":
            outcome.stopped = True
            outcome.stop_reason = "review_loop"
            outcome.summarize_blocked = True
            chain.save(chain_path)
            return outcome

        task_completed = (
            str(review.get("decision", "")).upper() == "CONTINUE"
            and check.passed
            and (capture.passed or gate.case_mode == "FORENSIC")
        )
        if not await _require_step(step_gate, "summarize", outcome):
            chain.save(chain_path)
            return outcome
        summarize = route_summarize(
            review,
            state_dir=workspace.state_dir,
            repair_root=workspace.repair_root,
            task_completed=task_completed,
        )
        chain.append("summarize", summarize.payload)
        if trace is not None:
            trace.record_step("summarize", summarize.payload)
        chain.save(chain_path)
        logger.info(
            "Repair pipeline finished feature={} verdict={} task_completed={} trace={}",
            feature,
            gate.verdict.value,
            task_completed,
            trace.root_dir.as_posix() if trace is not None else "-",
        )
        return outcome
    finally:
        if trace is not None:
            trace.finish(
                outcome=_outcome_payload(outcome),
                chain=outcome.chain.steps,
            )
