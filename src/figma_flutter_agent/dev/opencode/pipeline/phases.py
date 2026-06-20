"""Repair pipeline phase helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint
from figma_flutter_agent.dev.opencode.gates import run_repair_gates
from figma_flutter_agent.dev.opencode.opencode_policy import prompt_options_for_write_step
from figma_flutter_agent.dev.opencode.pipeline.types import OpenCodeRepairClient, PipelineOutcome
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repair_log import log_repair_step
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    allowed_paths_for_step,
    collect_plan_gate_paths,
    collect_plan_target_files,
    diff_touched_paths,
    validate_scope,
)
from figma_flutter_agent.dev.opencode.step_gate import StepGate
from figma_flutter_agent.dev.opencode.step_runner import StepRunner, write_step_state
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace
from figma_flutter_agent.errors import FigmaFlutterError


def run_context_from_gate(gate: Any) -> dict[str, Any]:
    """Build run_context payload for prompt assembly."""
    return {
        "case_mode": gate.case_mode,
        "agent_board": gate.agent_board,
        "run_manifest": gate.to_manifest_dict(),
        "allowed_questions": list(gate.allowed_questions),
        "forbidden_questions": list(gate.forbidden_questions),
    }


def outcome_payload(outcome: PipelineOutcome) -> dict[str, Any]:
    """Serialize pipeline outcome for trace finish."""
    return {
        "stopped": outcome.stopped,
        "stop_reason": outcome.stop_reason,
        "summarize_blocked": outcome.summarize_blocked,
        "gate_verdict": outcome.gate.verdict.value,
        "case_mode": outcome.gate.case_mode,
        "agent_board": outcome.gate.agent_board,
        "loop_rounds": outcome.loop_rounds,
    }


def read_step(
    runner: StepRunner,
    step: DebugPipelineStep,
    *,
    board: str,
    run_context: dict[str, Any],
    chain: ReasoningChain,
    state_dir: Path,
    user_prompt: str,
    loop_round: int,
    figma_png: bytes | None = None,
) -> dict[str, Any]:
    """Execute one read step and persist state."""
    started = time.perf_counter()
    log_repair_step(step, status="started", loop_round=loop_round)
    try:
        payload = runner.run_read_step(
            step,
            board=board,
            run_context=run_context,
            chain=chain,
            user_prompt=user_prompt,
            figma_png=figma_png,
            outer_round=loop_round,
        )
    except Exception:
        log_repair_step(
            step,
            status="error",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            loop_round=loop_round,
        )
        raise
    write_step_state(state_dir, step, payload)
    chain.append(step, payload)
    append_checkpoint(state_dir, step=step, loop_round=loop_round)
    log_repair_step(
        step,
        status="completed",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        loop_round=loop_round,
    )
    return payload


def validate_plan(payload: dict[str, Any]) -> None:
    """Validate plan step shape."""
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


async def require_next_round(
    round_gate: StepGate | None,
    round_number: int,
    outcome: PipelineOutcome,
    *,
    preview: dict[str, Any] | None = None,
) -> bool:
    """Return False when interactive round gate denies the next outer loop."""
    if round_number <= 1 or round_gate is None:
        return True
    step = f"round_{round_number}"
    if await round_gate.approve(step, preview=preview):
        return True
    outcome.stopped = True
    outcome.stop_reason = f"user_declined_{step}"
    return False


async def require_step(
    step_gate: StepGate | None,
    step: str,
    outcome: PipelineOutcome,
    *,
    preview: dict[str, Any] | None = None,
) -> bool:
    """Return False when interactive step gate denies execution."""
    if step_gate is None:
        return True
    if await step_gate.approve(step, preview=preview):
        return True
    outcome.stopped = True
    outcome.stop_reason = f"user_declined_{step}"
    return False


def build_pivot(
    *,
    refine_reason: str,
    chain: ReasoningChain,
    same_root_hash: str = "",
    failed_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Build forced-reflection pivot context for refine routes."""
    diagnose = chain.steps.get("diagnose", {})
    laws = diagnose.get("laws") if isinstance(diagnose, dict) else []
    law_ids: list[str] = []
    if isinstance(laws, list):
        for item in laws:
            if isinstance(item, dict) and item.get("id"):
                law_ids.append(str(item["id"]))
    return {
        "refine_reason": refine_reason,
        "previous_law_ids": law_ids,
        "failed_evidence": failed_evidence or [],
        "same_root_hash": same_root_hash,
        "required_behavior": (
            "Do not repeat the same law unless you add new evidence or narrow the owning layer."
        ),
    }


async def run_repair_write(
    *,
    workspace: RepairWorkspace,
    feature: str,
    plan: dict[str, Any],
    pipeline_policy: Any,
    opencode_client: OpenCodeRepairClient | None,
    skip_opencode_repair: bool,
    step_gate: StepGate | None,
    outcome: PipelineOutcome,
    trace: RepairTraceRecorder | None,
    loop_round: int,
    board: str = "forensic",
) -> dict[str, Any] | None:
    """Run OpenCode repair, scope enforcement, and quality gates."""
    repair_prompt = prompt_options_for_write_step(
        pipeline_policy,
        step="repair",
        board=board,
    )
    repair_payload: dict[str, Any] = {
        "step": "repair",
        "skipped": True,
        "notes": "OpenCode repair skipped",
    }
    if skip_opencode_repair or opencode_client is None:
        if trace is not None:
            trace.record_step("repair", repair_payload, status="skipped")
        write_step_state(workspace.state_dir, "repair", repair_payload)
        append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
        return repair_payload

    if not await require_step(step_gate, "repair", outcome):
        return None

    repair_user_text = "Execute repair plan in sandbox. Edit only src/figma_flutter_agent."
    session_id = await opencode_client.create_session(title=f"repair-{feature}")
    repair_started = time.perf_counter()
    repair_response = await opencode_client.prompt_message(
        session_id,
        text=repair_user_text,
        agent=repair_prompt["agent"],
        model=repair_prompt["model"],
        reasoning_effort=repair_prompt["reasoning_effort"],
    )

    touched = diff_touched_paths(workspace.worktree)
    allowed = allowed_paths_for_step("repair", worktree=workspace.worktree, plan_payload=plan)
    scope = validate_scope("repair", touched_paths=touched, allowed_paths=allowed)
    plan_targets = collect_plan_target_files(plan)
    compiler_targets = {p for p in plan_targets if p.startswith("src/figma_flutter_agent/")}
    touched_set = set(scope.touched_paths)
    repair_noop = bool(compiler_targets) and not compiler_targets.intersection(touched_set)

    gate_paths = collect_plan_gate_paths(plan)
    gate_result = run_repair_gates(workspace.worktree, touched_paths=gate_paths)

    repair_payload = {
        "step": "repair",
        "skipped": False,
        "session_id": session_id,
        "agent": repair_prompt["agent"],
        "model": repair_prompt["model"],
        "reasoning_effort": repair_prompt["reasoning_effort"],
        "filesTouched": list(scope.touched_paths),
        "scope": {
            "passed": scope.passed,
            "reason_code": scope.reason_code,
            "violations": list(scope.violations),
        },
        "gates": {
            "ruff": gate_result.ruff_ok,
            "pytest": gate_result.pytest_ok,
            "passed": gate_result.passed,
            "touched_paths": list(gate_result.touched_paths),
        },
        "noop": repair_noop,
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

    write_step_state(workspace.state_dir, "repair", repair_payload)
    append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)

    if repair_noop:
        outcome.stopped = True
        outcome.stop_reason = "repair_noop"
        return None
    if not scope.passed:
        outcome.stopped = True
        outcome.stop_reason = "SCOPE_DRIFT"
        return None
    if not gate_result.passed:
        outcome.stopped = True
        outcome.stop_reason = "repair_gates_failed"
        return None
    return repair_payload


async def run_fix_write(
    *,
    workspace: RepairWorkspace,
    feature: str,
    check_payload: dict[str, Any],
    fix_attempt: int,
    pipeline_policy: Any,
    opencode_client: OpenCodeRepairClient | None,
    skip_opencode_repair: bool,
    loop_round: int,
    board: str = "forensic",
    trace: RepairTraceRecorder | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Run OpenCode fix step with scope enforcement."""
    fix_prompt = prompt_options_for_write_step(
        pipeline_policy,
        step="fix",
        board=board,
    )
    fix_summary = ""
    fix_response: dict[str, Any] = {}
    if skip_opencode_repair or opencode_client is None:
        return fix_summary, None

    fix_user_text = (
        f"Emit-layer fix attempt {fix_attempt}. "
        "Patch only .repair/candidate/planned_files per fix skill. "
        f"Check summary: {json.dumps(check_payload, ensure_ascii=False)[:2000]}"
    )
    fix_session_id = await opencode_client.create_session(title=f"fix-{feature}-{fix_attempt}")
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

    touched = diff_touched_paths(workspace.worktree)
    allowed = allowed_paths_for_step("fix", worktree=workspace.worktree, plan_payload={})
    scope = validate_scope("fix", touched_paths=touched, allowed_paths=allowed)
    fix_payload = {
        "step": f"fix_{fix_attempt}",
        "session_id": fix_session_id,
        "filesTouched": list(scope.touched_paths),
        "scope": {
            "passed": scope.passed,
            "reason_code": scope.reason_code,
            "violations": list(scope.violations),
        },
    }
    if trace is not None:
        trace.record_opencode(
            f"fix_{fix_attempt}",
            output=fix_payload,
            response=fix_response,
            duration_ms=(time.perf_counter() - fix_started) * 1000.0,
            meta={
                "agent": fix_prompt["agent"],
                "model": fix_prompt["model"],
                "reasoning_effort": fix_prompt["reasoning_effort"],
            },
            user_prompt=fix_user_text,
        )
    append_checkpoint(
        workspace.state_dir,
        step=f"fix_{fix_attempt}",
        loop_round=loop_round,
        extra={"scope_passed": scope.passed},
    )
    if not scope.passed:
        return fix_summary, {
            "scope_failed": True,
            "reason_code": scope.reason_code,
            "violations": list(scope.violations),
        }
    return fix_summary, None
