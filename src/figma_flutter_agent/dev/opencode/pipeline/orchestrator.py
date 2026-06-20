"""OpenCode repair pipeline orchestrator with outer correction loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.debug.paths import screen_debug_safe_project
from figma_flutter_agent.dev.opencode.capture_gate import run_capture_gate
from figma_flutter_agent.dev.opencode.check import compiler_repair_verified, run_check_gate
from figma_flutter_agent.dev.opencode.checkpoint import append_checkpoint
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.dev.opencode.fix_runner import run_fix_attempt
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.pipeline.phases import (
    build_pivot,
    outcome_payload,
    read_step,
    require_next_round,
    require_step,
    run_context_from_gate,
    run_fix_write,
    run_repair_write,
    validate_plan,
)
from figma_flutter_agent.dev.opencode.pipeline.types import OpenCodeRepairClient, PipelineOutcome
from figma_flutter_agent.dev.opencode.prompt_context import build_read_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.regenerate_mirror import run_regenerate_after_compiler_repair
from figma_flutter_agent.dev.opencode.repair_log import bind_repair_observability, repair_logger
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_budget,
    entry_step_for,
    resolve_from_check,
    resolve_from_review,
)
from figma_flutter_agent.dev.opencode.run_gate import evaluate_run_gate
from figma_flutter_agent.dev.opencode.step_gate import (
    StepGate,
    resolve_round_gate,
    resolve_step_gate,
)
from figma_flutter_agent.dev.opencode.step_runner import OpenRouterStepRunner, StepRunner
from figma_flutter_agent.dev.opencode.summarize_router import (
    apply_review_overrides,
    route_summarize,
)
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.dev.opencode.workspace import prepare_workspace
from figma_flutter_agent.observability import new_run_id

_MAX_OUTER_ROUNDS = 8


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
    round_gate: StepGate | None = None,
) -> PipelineOutcome:
    """Execute full repair pipeline for one screen."""
    gate = evaluate_run_gate(project_dir, feature)
    outcome = PipelineOutcome(gate=gate, workspace=None)
    step_gate = resolve_step_gate(
        confirm_next_step=settings.agent.debug_pipeline.interactive.confirm_next_step,
        command=command,
        explicit=step_gate,
    )
    round_gate = resolve_round_gate(
        confirm_next_round=settings.agent.debug_pipeline.interactive.confirm_next_round,
        command=command,
        explicit=round_gate,
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
    run_id = trace.trace_id if trace is not None else new_run_id()
    project_label = screen_debug_safe_project(project_dir)

    with bind_repair_observability(
        run_id=run_id,
        feature=feature,
        project=project_label,
        command=command,
        settings=settings,
    ):
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
                repair_logger().warning(
                    "Repair pipeline stopped at run_gate verdict={}",
                    gate.verdict.value,
                )
                return outcome

            workspace = prepare_workspace(project_dir=project_dir, feature=feature, gate=gate)
            outcome.workspace = workspace
            repair_logger().info(
                "Repair workspace ready case_id={} worktree={}",
                workspace.case_id,
                workspace.worktree.as_posix(),
            )
            if opencode_client is not None:
                opencode_client.bind_worktree(workspace.worktree.as_posix())

            chain = ReasoningChain()
            outcome.chain = chain
            chain_path = workspace.state_dir / "reasoning_chain.json"
            loop_state = LoopBudgetState()
            loops_config = settings.agent.debug_pipeline.loops
            run_context = run_context_from_gate(gate)
            run_context["loop_budget"] = loop_state.snapshot()
            run_context["pivot"] = None
            board = gate.agent_board
            pipeline_policy = settings.agent.debug_pipeline
            step_runner = runner or OpenRouterStepRunner(
                settings,
                state_dir=workspace.state_dir,
                trace=trace,
            )

            def _read_user_prompt(step: str) -> str:
                return build_read_step_user_prompt(
                    step,  # type: ignore[arg-type]
                    feature=feature,
                    board=board,
                    worktree=workspace.worktree,
                    debug_mirror=workspace.debug_mirror,
                    chain=chain,
                )

            figma_png: bytes | None = None
            figma_path = workspace.debug_mirror / "figma.png"
            if figma_path.is_file() and board == "screen":
                figma_png = figma_path.read_bytes()

            phase_entry = "recognise"
            plan: dict[str, Any] = {}
            repair_payload: dict[str, Any] | None = None
            check_passed = False
            capture_passed = False

            while loop_state.outer_round < _MAX_OUTER_ROUNDS:
                loop_state.outer_round += 1
                outcome.loop_rounds = loop_state.outer_round
                if not await require_next_round(
                    round_gate,
                    loop_state.outer_round,
                    outcome,
                    preview={"hint": f"(entry={phase_entry})"},
                ):
                    chain.save(chain_path)
                    return outcome
                run_context["loop_budget"] = loop_state.snapshot()
                skip_to_check = phase_entry == "check"
                ran_repair_this_iteration = False

                if not skip_to_check:
                    if phase_entry == "recognise":
                        for step in ("recognise", "inspect", "diagnose"):
                            if not await require_step(step_gate, step, outcome):
                                chain.save(chain_path)
                                return outcome
                            payload = read_step(
                                step_runner,
                                step,  # type: ignore[arg-type]
                                board=board,
                                run_context=run_context,
                                chain=chain,
                                state_dir=workspace.state_dir,
                                user_prompt=_read_user_prompt(step),
                                loop_round=loop_state.outer_round,
                                figma_png=figma_png if step == "recognise" else None,
                            )
                            if step == "diagnose" and payload.get("blocked"):
                                outcome.stopped = True
                                outcome.stop_reason = "diagnose_blocked"
                                chain.save(chain_path)
                                return outcome
                        phase_entry = "plan"

                    if phase_entry == "diagnose":
                        if not await require_step(step_gate, "diagnose", outcome):
                            chain.save(chain_path)
                            return outcome
                        diagnose = read_step(
                            step_runner,
                            "diagnose",
                            board=board,
                            run_context=run_context,
                            chain=chain,
                            state_dir=workspace.state_dir,
                            user_prompt=_read_user_prompt("diagnose"),
                            loop_round=loop_state.outer_round,
                        )
                        if diagnose.get("blocked"):
                            outcome.stopped = True
                            outcome.stop_reason = "diagnose_blocked"
                            chain.save(chain_path)
                            return outcome
                        phase_entry = "plan"

                    if phase_entry == "plan":
                        if not await require_step(step_gate, "plan", outcome):
                            chain.save(chain_path)
                            return outcome
                        plan = read_step(
                            step_runner,
                            "plan",
                            board=board,
                            run_context=run_context,
                            chain=chain,
                            state_dir=workspace.state_dir,
                            user_prompt=_read_user_prompt("plan"),
                            loop_round=loop_state.outer_round,
                        )
                        validate_plan(plan)
                        phase_entry = "repair"

                    if phase_entry == "repair":
                        repair_payload = await run_repair_write(
                            workspace=workspace,
                            feature=feature,
                            plan=plan,
                            pipeline_policy=pipeline_policy,
                            opencode_client=opencode_client,
                            skip_opencode_repair=skip_opencode_repair,
                            step_gate=step_gate,
                            outcome=outcome,
                            trace=trace,
                            loop_round=loop_state.outer_round,
                            board=board,
                        )
                        if repair_payload is None:
                            chain.save(chain_path)
                            return outcome
                        chain.append("repair", repair_payload)
                        ran_repair_this_iteration = True
                        phase_entry = "check"

                mirror_regenerated = False
                if (
                    ran_repair_this_iteration
                    and compiler_repair_verified(repair_payload, plan if plan else None)
                    and pipeline_policy.regenerate_after_compiler_repair
                ):
                    regen = await run_regenerate_after_compiler_repair(
                        workspace=workspace,
                        settings=settings,
                        project_dir=project_dir,
                        feature=feature,
                    )
                    chain.append("regenerate", regen.payload)
                    append_checkpoint(
                        workspace.state_dir,
                        step="regenerate",
                        loop_round=loop_state.outer_round,
                    )
                    if trace is not None:
                        trace.record_step(
                            "regenerate",
                            regen.payload,
                            status="ok" if regen.passed else "blocked",
                        )
                    if not regen.passed:
                        outcome.stopped = True
                        outcome.stop_reason = "regenerate_failed"
                        chain.save(chain_path)
                        return outcome
                    mirror_regenerated = True

                if not await require_step(step_gate, "check", outcome):
                    chain.save(chain_path)
                    return outcome

                check = run_check_gate(
                    workspace.debug_mirror,
                    state_dir=workspace.state_dir,
                    repair_payload=repair_payload,
                    plan_payload=plan if plan else None,
                    allow_stale_mirror_bypass=(
                        not mirror_regenerated
                        and not pipeline_policy.regenerate_after_compiler_repair
                    ),
                )
                chain.append("check", check.payload)
                append_checkpoint(workspace.state_dir, step="check", loop_round=loop_state.outer_round)
                if trace is not None:
                    trace.record_step(
                        "check",
                        check.payload,
                        status="ok" if check.passed else "blocked",
                        meta={"route": check.route},
                    )

                fix_attempts = 0
                max_fix = loops_config.max_fix_attempts
                route_decision = resolve_from_check(check.payload)

                while not check.passed and route_decision == RouteDecision.FIX_ATTEMPT and fix_attempts < max_fix:
                    fix_attempts += 1
                    fix_step = f"fix_{fix_attempts}"
                    if not await require_step(
                        step_gate,
                        fix_step,
                        outcome,
                        preview={"hint": f"(attempt {fix_attempts}/{max_fix})"},
                    ):
                        chain.save(chain_path)
                        return outcome

                    fix_summary, scope_error = await run_fix_write(
                        workspace=workspace,
                        feature=feature,
                        check_payload=check.payload,
                        fix_attempt=fix_attempts,
                        pipeline_policy=pipeline_policy,
                        opencode_client=opencode_client,
                        skip_opencode_repair=skip_opencode_repair,
                        loop_round=loop_state.outer_round,
                        board=board,
                        trace=trace,
                    )
                    if scope_error is not None:
                        outcome.stopped = True
                        outcome.stop_reason = "SCOPE_DRIFT"
                        chain.save(chain_path)
                        return outcome

                    fix = run_fix_attempt(
                        state_dir=workspace.state_dir,
                        check_payload=check.payload,
                        attempt=fix_attempts,
                        max_attempts=max_fix,
                        opencode_summary=fix_summary,
                    )
                    chain.append(f"fix_{fix_attempts}", fix.payload)
                    if trace is not None:
                        trace.record_step(f"fix_{fix_attempts}", fix.payload)

                    check = run_check_gate(
                        workspace.debug_mirror,
                        state_dir=workspace.state_dir,
                        repair_payload=repair_payload,
                        plan_payload=plan if plan else None,
                        allow_stale_mirror_bypass=False,
                    )
                    chain.append(f"check_{fix_attempts}", check.payload)
                    append_checkpoint(
                        workspace.state_dir,
                        step=f"check_{fix_attempts}",
                        loop_round=loop_state.outer_round,
                    )
                    route_decision = resolve_from_check(check.payload)

                root_hash = str(check.payload.get("same_root_hash") or "")
                loop_state.record_root_hash(root_hash, improved=check.passed)
                check_passed = check.passed

                if not check.passed:
                    route_decision = apply_budget(resolve_from_check(check.payload), loop_state, loops_config)
                    if route_decision == RouteDecision.STOP_HUMAN:
                        outcome.stopped = True
                        outcome.stop_reason = "budget_exhausted"
                        chain.save(chain_path)
                        return outcome
                    if route_decision in {
                        RouteDecision.DIAGNOSE_REFINE,
                        RouteDecision.PLAN_REVISE,
                        RouteDecision.REPAIR_RETRY,
                    }:
                        run_context["pivot"] = build_pivot(
                            refine_reason=str(check.payload.get("failure_class") or "CHECK_FAILED"),
                            chain=chain,
                            same_root_hash=root_hash,
                            failed_evidence=list(check.payload.get("evidence") or []),
                        )
                        phase_entry = entry_step_for(route_decision)
                        continue
                    outcome.stopped = True
                    outcome.stop_reason = str(check.payload.get("failure_class") or "check_failed")
                    chain.save(chain_path)
                    return outcome

                if not await require_step(step_gate, "capture", outcome):
                    chain.save(chain_path)
                    return outcome
                capture = run_capture_gate(
                    workspace.debug_mirror,
                    state_dir=workspace.state_dir,
                    served_run_id=gate.served_build_run_id,
                    committed_run_id=gate.committed_build_run_id,
                )
                chain.append("capture", capture.payload)
                append_checkpoint(workspace.state_dir, step="capture", loop_round=loop_state.outer_round)
                capture_passed = capture.passed
                if trace is not None:
                    trace.record_step(
                        "capture",
                        capture.payload,
                        status="ok" if capture.passed else "blocked",
                    )

                if not await require_step(step_gate, "review", outcome):
                    chain.save(chain_path)
                    return outcome
                review = read_step(
                    step_runner,
                    "review",
                    board=board,
                    run_context=run_context,
                    chain=chain,
                    state_dir=workspace.state_dir,
                    user_prompt=_read_user_prompt("review"),
                    loop_round=loop_state.outer_round,
                )
                review = apply_review_overrides(
                    review,
                    check_passed=check_passed,
                    capture_passed=capture_passed,
                    case_mode=gate.case_mode,
                )
                append_checkpoint(workspace.state_dir, step="review", loop_round=loop_state.outer_round)

                if str(review.get("decision", "")).upper() == "LOOP":
                    route_decision = apply_budget(resolve_from_review(review), loop_state, loops_config)
                    if route_decision == RouteDecision.STOP_HUMAN:
                        outcome.stopped = True
                        outcome.stop_reason = "budget_exhausted"
                        chain.save(chain_path)
                        return outcome
                    run_context["pivot"] = build_pivot(
                        refine_reason=str(review.get("reason_code") or "REVIEW_LOOP"),
                        chain=chain,
                        same_root_hash=root_hash,
                        failed_evidence=[f"review:{review.get('reason_code')}"],
                    )
                    phase_entry = entry_step_for(route_decision)
                    continue

                task_completed = (
                    str(review.get("decision", "")).upper() == "CONTINUE"
                    and check_passed
                    and (capture_passed or gate.case_mode == "FORENSIC")
                )
                if not await require_step(step_gate, "summarize", outcome):
                    chain.save(chain_path)
                    return outcome
                summarize = route_summarize(
                    review,
                    state_dir=workspace.state_dir,
                    repair_root=workspace.repair_root,
                    task_completed=task_completed,
                )
                chain.append("summarize", summarize.payload)
                append_checkpoint(workspace.state_dir, step="summarize", loop_round=loop_state.outer_round)
                if trace is not None:
                    trace.record_step("summarize", summarize.payload)
                chain.save(chain_path)
                repair_logger().info(
                    "Repair pipeline finished feature={} verdict={} task_completed={} rounds={} trace={}",
                    feature,
                    gate.verdict.value,
                    task_completed,
                    loop_state.outer_round,
                    trace.root_dir.as_posix() if trace is not None else "-",
                )
                return outcome

            outcome.stopped = True
            outcome.stop_reason = "max_outer_rounds"
            chain.save(chain_path)
            repair_logger().warning("Repair pipeline stopped reason=max_outer_rounds")
            return outcome
        finally:
            if trace is not None:
                trace.finish(
                    outcome=outcome_payload(outcome),
                    chain=outcome.chain.steps if outcome.chain is not None else None,
                )
            if outcome.stopped:
                repair_logger().warning(
                    "Repair pipeline exit stopped={} reason={}",
                    outcome.stopped,
                    outcome.stop_reason,
                )
