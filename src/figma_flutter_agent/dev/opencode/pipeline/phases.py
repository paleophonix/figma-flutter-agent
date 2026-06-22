"""Repair pipeline phase helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config.debug_pipeline import DebugPipelineStep
from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint
from figma_flutter_agent.dev.opencode.gates import (
    run_repair_gates,
    skipped_repair_gate_result,
)
from figma_flutter_agent.dev.opencode.l6_context import build_l6_bindings
from figma_flutter_agent.dev.opencode.opencode_policy import prompt_options_for_write_step
from figma_flutter_agent.dev.opencode.opencode_response import (
    detect_repair_incomplete,
    detect_repair_steps_exhausted,
    extract_opencode_assistant_text,
    extract_opencode_prompt_error,
    truncate_agent_summary,
)
from figma_flutter_agent.dev.opencode.pipeline.types import OpenCodeRepairClient, PipelineOutcome
from figma_flutter_agent.dev.opencode.plan_routing import assign_repair_plan_step_orders
from figma_flutter_agent.dev.opencode.plan_validate import normalize_plan_test_paths
from figma_flutter_agent.dev.opencode.prompt_context import build_write_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repair_log import emit_repair_progress, log_repair_step
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    allowed_paths_for_step,
    capture_worktree_touch_baseline,
    collect_repair_gate_paths,
    collect_plan_target_files,
    diff_snapshot,
    diff_touched_paths,
    diff_touched_since_baseline,
    paths_from_opencode_session_diff,
    snapshot_tree_hashes,
    validate_scope,
)
from figma_flutter_agent.dev.opencode.step_gate import StepGate
from figma_flutter_agent.dev.opencode.step_runner import StepRunner, write_step_state
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace
from figma_flutter_agent.errors import FigmaFlutterError


def run_context_from_gate(gate: Any) -> dict[str, Any]:
    """Build run_context payload for prompt assembly."""
    manifest = gate.to_manifest_dict()
    return {
        "case_mode": gate.case_mode,
        "agent_board": gate.agent_board,
        "run_manifest": manifest,
        "capture_passport": manifest.get("capture_passport") or {},
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
    flutter_render_png: bytes | None = None,
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
            flutter_render_png=flutter_render_png,
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


_FULL_CYCLE_PHASE_ENTRIES = frozenset({"recognise", "inspect", "diagnose"})


def _opencode_progress_callback(step: str):
    """Return a callback that forwards OpenCode live progress to the wizard sink."""
    return lambda line: emit_repair_progress(step, line)


async def require_next_round(
    round_gate: StepGate | None,
    round_number: int,
    outcome: PipelineOutcome,
    *,
    phase_entry: str,
    preview: dict[str, Any] | None = None,
) -> bool:
    """Return False when interactive gate denies the next full correction cycle.

    Plan/repair/check re-entries (for example ``plan.revise`` after ``repair_noop``)
    are not gated — only recognise/inspect/diagnose starts ask for confirmation.
    """
    if round_gate is None:
        return True
    if phase_entry not in _FULL_CYCLE_PHASE_ENTRIES:
        return True
    if round_number <= 1:
        return True
    step = f"cycle_{round_number}"
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
    if refine_reason == "REPAIR_INCOMPLETE":
        required_behavior = (
            "OpenCode exhausted agent.steps during analysis. Implement the planned patch "
            "now — at most one target-file read, then edit plan targetFiles and tests."
        )
    elif refine_reason == "REPAIR_NOOP":
        required_behavior = (
            "Retry repair on the existing plan compiler targetFiles before rewriting plan."
        )
    else:
        required_behavior = (
            "Do not repeat the same law unless you add new evidence or narrow the owning layer."
        )
    return {
        "refine_reason": refine_reason,
        "previous_law_ids": law_ids,
        "failed_evidence": failed_evidence or [],
        "same_root_hash": same_root_hash,
        "required_behavior": required_behavior,
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
    chain: ReasoningChain,
    run_context: dict[str, Any],
    project_label: str,
) -> dict[str, Any] | None:
    """Run OpenCode repair, scope enforcement, and quality gates."""
    normalize_plan_test_paths(plan)
    loop_budget = run_context.get("loop_budget")
    if isinstance(loop_budget, dict):
        repair_attempt_index = int(loop_budget.get("repair_noop_retries") or 0) + int(
            loop_budget.get("repair_retries") or 0
        )
    else:
        repair_attempt_index = 0
    repair_prompt = prompt_options_for_write_step(
        pipeline_policy,
        step="repair",
        board=board,
        attempt_index=repair_attempt_index,
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

    plan_step_orders = assign_repair_plan_step_orders(run_context, plan)
    if not plan_step_orders:
        repair_payload = {
            "step": "repair",
            "skipped": False,
            "blocked": True,
            "blocked_reason": "No CODE_CHANGE plan steps available for repair pass",
            "planStepOrders": [],
            "filesTouched": [],
            "noop": True,
        }
        write_step_state(workspace.state_dir, "repair", repair_payload)
        append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
        outcome.stopped = True
        outcome.stop_reason = "repair_no_plan_steps"
        return repair_payload

    log_repair_step("repair", status="started", loop_round=loop_round)
    touch_baseline = capture_worktree_touch_baseline(
        workspace.worktree,
        workspace.state_dir,
    )
    reasoning = chain.compact_json_for_step("repair", run_context.get("pivot"))
    l6_bindings = build_l6_bindings(
        step="repair",
        board=board,
        workspace=workspace,
        feature=feature,
        project_label=project_label,
        run_context=run_context,
        reasoning_chain_json=reasoning,
        chain=chain,
        plan=plan,
    )
    repair_user_text = build_write_step_user_prompt(
        "repair",
        feature=feature,
        board=board,
        worktree=workspace.worktree,
        debug_mirror=workspace.debug_mirror,
        chain=chain,
        run_context=run_context,
        l6_bindings=l6_bindings,
        plan=plan,
    )
    session_id = await opencode_client.create_session(title=f"repair-{feature}")
    repair_started = time.perf_counter()
    emit_repair_progress(
        "repair",
        f"OpenCode {repair_prompt['model']} · session {session_id}",
    )
    try:
        repair_response = await opencode_client.prompt_message(
            session_id,
            text=repair_user_text,
            agent=repair_prompt["agent"],
            model=repair_prompt["model"],
            reasoning_effort=repair_prompt["reasoning_effort"],
            on_progress=_opencode_progress_callback("repair"),
            progress_step="repair",
        )
    except FigmaFlutterError as exc:
        await opencode_client.abort_session(session_id)
        repair_payload = {
            "step": "repair",
            "skipped": False,
            "session_id": session_id,
            "agent": repair_prompt["agent"],
            "model": repair_prompt["model"],
            "reasoning_effort": repair_prompt["reasoning_effort"],
            "provider_error": str(exc),
            "filesTouched": [],
            "noop": False,
            "timed_out": "timed out" in str(exc).lower(),
        }
        write_step_state(workspace.state_dir, "repair", repair_payload)
        append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
        outcome.stopped = True
        outcome.stop_reason = (
            "opencode_prompt_timeout"
            if repair_payload.get("timed_out")
            else "opencode_provider_error"
        )
        if trace is not None:
            trace.record_opencode(
                "repair",
                output=repair_payload,
                response={},
                duration_ms=(time.perf_counter() - repair_started) * 1000.0,
                meta={
                    "agent": repair_prompt["agent"],
                    "model": repair_prompt["model"],
                    "reasoning_effort": repair_prompt["reasoning_effort"],
                },
                user_prompt=repair_user_text,
                is_error=True,
                error_message=str(exc),
            )
        return repair_payload

    provider_error = extract_opencode_prompt_error(repair_response)
    if provider_error:
        repair_payload = {
            "step": "repair",
            "skipped": False,
            "session_id": session_id,
            "agent": repair_prompt["agent"],
            "model": repair_prompt["model"],
            "reasoning_effort": repair_prompt["reasoning_effort"],
            "provider_error": provider_error,
            "filesTouched": [],
            "noop": False,
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
                is_error=True,
                error_message=provider_error,
            )
        write_step_state(workspace.state_dir, "repair", repair_payload)
        append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
        outcome.stopped = True
        outcome.stop_reason = "opencode_provider_error"
        return repair_payload

    session_diff_entries: list[dict[str, Any]] = []
    try:
        session_diff_entries = await opencode_client.session_diff(session_id)
    except Exception:
        logger.exception("OpenCode session diff failed for repair session {}", session_id)

    step_delta_set = set(diff_touched_since_baseline(workspace.worktree, touch_baseline))
    if session_diff_entries:
        step_delta_set.update(paths_from_opencode_session_diff(session_diff_entries))
    step_delta = sorted(step_delta_set)
    scope = validate_scope(
        "repair",
        touched_paths=step_delta,
        allowed_paths=allowed_paths_for_step(
            "repair",
            worktree=workspace.worktree,
            plan_payload=plan,
        ),
    )
    plan_targets = collect_plan_target_files(plan)
    compiler_targets = {p for p in plan_targets if p.startswith("src/figma_flutter_agent/")}
    compiler_edits = compiler_targets.intersection(step_delta_set)
    repair_noop = bool(compiler_targets) and not compiler_edits
    assistant_text = extract_opencode_assistant_text(repair_response)
    repair_incomplete = repair_noop and detect_repair_incomplete(
        repair_response,
        assistant_text,
    )
    noop_reason: str | None = None
    if repair_noop:
        noop_reason = "steps_exhausted" if repair_incomplete else "no_compiler_edits"

    if not scope.passed:
        outcome.stopped = True
        outcome.stop_reason = "SCOPE_DRIFT"
        repair_payload = {
            "step": "repair",
            "skipped": False,
            "session_id": session_id,
            "scope": {
                "passed": False,
                "reason_code": scope.reason_code,
                "violations": list(scope.violations),
            },
            "filesTouched": list(step_delta),
            "noop": repair_noop,
        }
        write_step_state(workspace.state_dir, "repair", repair_payload)
        append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
        return repair_payload

    gate_paths = collect_repair_gate_paths(
        plan,
        worktree=workspace.worktree,
        git_touched=step_delta,
    )
    if compiler_edits:
        gate_result = run_repair_gates(workspace.worktree, touched_paths=gate_paths)
    else:
        gate_result = skipped_repair_gate_result(touched_paths=tuple(gate_paths))

    repair_payload = {
        "step": "repair",
        "skipped": False,
        "session_id": session_id,
        "agent": repair_prompt["agent"],
        "model": repair_prompt["model"],
        "reasoning_effort": repair_prompt["reasoning_effort"],
        "planStepOrders": plan_step_orders,
        "filesTouched": list(step_delta),
        "scope": {
            "passed": scope.passed,
            "reason_code": scope.reason_code,
            "violations": list(scope.violations),
        },
        "gates": {
            "ruff": gate_result.ruff_ok,
            "pytest": gate_result.pytest_ok,
            "passed": gate_result.passed,
            "skipped": gate_result.skipped,
            "touched_paths": list(gate_result.touched_paths),
        },
        "noop": repair_noop,
        "incomplete": repair_incomplete,
        "noop_reason": noop_reason,
        "agent_summary": truncate_agent_summary(assistant_text) if assistant_text else "",
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

    if repair_noop:
        repair_payload["noop"] = True
        write_step_state(workspace.state_dir, "repair", repair_payload)
        append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
        return repair_payload
    if not gate_result.passed:
        outcome.stopped = True
        outcome.stop_reason = "repair_gates_failed"
        return None
    write_step_state(workspace.state_dir, "repair", repair_payload)
    append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
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
        attempt_index=max(fix_attempt - 1, 0),
    )
    fix_summary = ""
    fix_response: dict[str, Any] = {}
    if skip_opencode_repair or opencode_client is None:
        return fix_summary, None

    planned_root = workspace.worktree / ".repair" / "candidate" / "planned_files"
    before_snapshot = snapshot_tree_hashes(planned_root)
    touch_baseline = capture_worktree_touch_baseline(workspace.worktree, workspace.state_dir)

    fix_user_text = (
        f"Emit-layer fix attempt {fix_attempt}. "
        "Patch only .repair/candidate/planned_files per fix skill. "
        f"Check summary: {json.dumps(check_payload, ensure_ascii=False)[:2000]}"
    )
    fix_session_id = await opencode_client.create_session(title=f"fix-{feature}-{fix_attempt}")
    fix_started = time.perf_counter()
    emit_repair_progress(
        f"fix_{fix_attempt}",
        f"OpenCode {fix_prompt['model']} · session {fix_session_id}",
    )
    fix_response = await opencode_client.prompt_message(
        fix_session_id,
        text=fix_user_text,
        agent=fix_prompt["agent"],
        model=fix_prompt["model"],
        reasoning_effort=fix_prompt["reasoning_effort"],
        on_progress=_opencode_progress_callback(f"fix_{fix_attempt}"),
        progress_step=f"fix_{fix_attempt}",
    )
    provider_error = extract_opencode_prompt_error(fix_response)
    if provider_error:
        if trace is not None:
            trace.record_opencode(
                f"fix_{fix_attempt}",
                output={"provider_error": provider_error, "step": f"fix_{fix_attempt}"},
                response=fix_response,
                duration_ms=(time.perf_counter() - fix_started) * 1000.0,
                meta={
                    "agent": fix_prompt["agent"],
                    "model": fix_prompt["model"],
                    "reasoning_effort": fix_prompt["reasoning_effort"],
                },
                user_prompt=fix_user_text,
                is_error=True,
                error_message=provider_error,
            )
        return fix_summary, {"provider_error": provider_error}

    parts = fix_response.get("parts") or []
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            fix_summary = str(part.get("text") or "")
            break

    touched = diff_snapshot(
        before_snapshot,
        snapshot_tree_hashes(planned_root),
        prefix=".repair/candidate/planned_files",
    )
    git_drift = [
        path
        for path in diff_touched_since_baseline(workspace.worktree, touch_baseline)
        if not path.startswith(".repair/candidate/planned_files")
    ]
    touched = sorted(set(touched) | set(git_drift))
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
