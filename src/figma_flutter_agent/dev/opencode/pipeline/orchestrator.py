"""OpenCode repair pipeline orchestrator with outer correction loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.debug.paths import screen_debug_safe_project
from figma_flutter_agent.dev.opencode.build_identity import reevaluate_build_identity
from figma_flutter_agent.dev.opencode.capture_gate import run_capture_gate
from figma_flutter_agent.dev.opencode.capture_verify import run_capture_verify
from figma_flutter_agent.dev.opencode.check import compiler_repair_verified, run_check_gate
from figma_flutter_agent.dev.opencode.checkpoint import (
    append_checkpoint,
    resolve_resume_phase_entry,
    restore_loop_budget,
    save_loop_budget,
)
from figma_flutter_agent.dev.opencode.diagnose_validate import (
    diagnose_laws_missing,
    terminal_blocked_plan_for_empty_diagnose,
    validate_diagnose_output,
)
from figma_flutter_agent.dev.opencode.failure_class import FailureClass, same_root_hash
from figma_flutter_agent.dev.opencode.fix_runner import run_fix_attempt
from figma_flutter_agent.dev.opencode.l6_context import build_l6_bindings
from figma_flutter_agent.dev.opencode.loop_state import LoopBudgetState
from figma_flutter_agent.dev.opencode.pipeline.phases import (
    _FULL_CYCLE_PHASE_ENTRIES as FULL_CYCLE_PHASE_ENTRIES,
)
from figma_flutter_agent.dev.opencode.pipeline.phases import (
    build_pivot,
    outcome_payload,
    read_step,
    require_next_round,
    require_step,
    run_context_from_gate,
    run_fix_write,
    run_repair_write,
)
from figma_flutter_agent.dev.opencode.pipeline.types import OpenCodeRepairClient, PipelineOutcome
from figma_flutter_agent.dev.opencode.plan_validate import validate_plan
from figma_flutter_agent.dev.opencode.prompt_context import build_read_step_user_prompt
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.regenerate_mirror import run_regenerate_after_compiler_repair
from figma_flutter_agent.dev.opencode.repair_log import bind_repair_observability, repair_logger
from figma_flutter_agent.dev.opencode.repair_project_sandbox import (
    resolve_repair_flutter_project_dir,
)
from figma_flutter_agent.dev.opencode.route_dispatch import (
    RouteDecision,
    apply_budget,
    entry_step_for,
    repair_gate_failure_payload,
    repair_scope_drift_payload,
    resolve_from_check,
    resolve_from_review,
    route_after_repair_gate_failure,
    route_after_repair_noop,
    route_after_repair_scope_drift,
)
from figma_flutter_agent.dev.opencode.run_gate import evaluate_run_gate
from figma_flutter_agent.dev.opencode.scope_enforcement import revert_scope_violation_paths
from figma_flutter_agent.dev.opencode.step_gate import (
    StepGate,
    resolve_round_gate,
    resolve_step_gate,
)
from figma_flutter_agent.dev.opencode.step_runner import (
    OpenRouterStepRunner,
    StepRunner,
    write_step_state,
)
from figma_flutter_agent.dev.opencode.summarize_router import (
    apply_review_overrides,
    persist_review_state,
    route_summarize,
)
from figma_flutter_agent.dev.opencode.trace import RepairTraceRecorder
from figma_flutter_agent.dev.opencode.vision_bundle import build_vision_bundle
from figma_flutter_agent.dev.opencode.workspace import (
    RepairWorkspace,
    assign_worktree_trace_id,
    prepare_workspace,
)
from figma_flutter_agent.dev.opencode.worktree import prune_orphaned_worktrees
from figma_flutter_agent.dev.opencode.worktree_retention import apply_repair_worktree_retention
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability import new_run_id

_MAX_OUTER_ROUNDS = 8

_MID_CYCLE_CHECK_ROUTES = frozenset(
    {
        RouteDecision.PLAN_REVISE,
        RouteDecision.REPAIR_RETRY,
        RouteDecision.CHECK_RETRY,
    }
)


def _stage_worktree_salvage(
    workspace: RepairWorkspace,
    chain: ReasoningChain,
    plan: dict[str, Any],
    loop_round: int,
) -> dict[str, Any] | None:
    """Run salvage gates and persist a synthetic repair payload when eligible."""
    from figma_flutter_agent.dev.opencode.repair_salvage import (
        attempt_worktree_compiler_salvage,
    )

    salvage = attempt_worktree_compiler_salvage(
        workspace,
        plan_payload=plan,
        diagnose_payload=chain.steps.get("diagnose"),
    )
    if salvage is None:
        return None
    write_step_state(workspace.state_dir, "repair", salvage)
    chain.append("repair", salvage)
    append_checkpoint(workspace.state_dir, step="repair", loop_round=loop_round)
    repair_logger().info(
        "Repair worktree salvage staged filesTouched={}",
        salvage.get("filesTouched"),
    )
    return salvage


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
    existing_workspace: RepairWorkspace | None = None,
    resume: bool = False,
) -> PipelineOutcome:
    """Execute full repair pipeline for one screen."""
    gate = evaluate_run_gate(project_dir, feature)
    outcome = PipelineOutcome(gate=gate, workspace=None)
    project_label = screen_debug_safe_project(project_dir)
    gate_blocked = gate.verdict in {FailureClass.NO_SERVE, FailureClass.UNKNOWN_BLOCKED}
    worktree_trace_id: str | None = None
    workspace: RepairWorkspace | None = existing_workspace

    if not gate_blocked:
        if workspace is None:
            workspace = prepare_workspace(project_dir=project_dir, feature=feature, gate=gate)
        worktree_trace_id = assign_worktree_trace_id(workspace.manifest_path)
        outcome.workspace = workspace

    trace = RepairTraceRecorder.maybe_start(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        command=command,
        trace_id=worktree_trace_id,
        extra_manifest={
            "case_mode": gate.case_mode,
            "agent_board": gate.agent_board,
            "gate_verdict": gate.verdict.value,
            **(
                {
                    "case_id": workspace.case_id,
                    "resumed": resume,
                    "worktree": workspace.worktree.as_posix(),
                }
                if workspace is not None
                else {}
            ),
        },
    )
    run_id = worktree_trace_id or (trace.trace_id if trace is not None else new_run_id())
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

    with bind_repair_observability(
        run_id=run_id,
        feature=feature,
        project=project_label,
        command=command,
        settings=settings,
        emit_root_trace=not resume,
    ):
        if trace is not None:
            outcome.trace_dir = trace.root_dir
            trace.record_step(
                "run_gate",
                gate.to_manifest_dict(),
                meta={"verdict": gate.verdict.value, "case_mode": gate.case_mode},
            )

        try:
            if gate_blocked:
                outcome.stopped = True
                outcome.stop_reason = gate.verdict.value
                repair_logger().warning(
                    "Repair pipeline stopped at run_gate verdict={}",
                    gate.verdict.value,
                )
                return outcome

            assert workspace is not None
            repair_logger().info(
                "Repair workspace ready case_id={} worktree={} resume={} posthog_trace_id={}",
                workspace.case_id,
                workspace.worktree.as_posix(),
                resume,
                worktree_trace_id,
            )
            if opencode_client is not None:
                opencode_client.bind_worktree(workspace.worktree.as_posix())

            chain_path = workspace.state_dir / "reasoning_chain.json"
            loops_config = settings.agent.debug_pipeline.loops
            pipeline_policy = settings.agent.debug_pipeline
            if resume:
                chain = ReasoningChain.load(chain_path)
                phase_entry, _resume_loop_round = resolve_resume_phase_entry(workspace.state_dir)
                repair_step = chain.steps.get("repair")
                if isinstance(repair_step, dict) and repair_step.get("noop"):
                    loop_state = LoopBudgetState()
                    loop_state.correction_cycle = 1
                    loop_state.outer_round = 1
                else:
                    loop_state = restore_loop_budget(workspace.state_dir)
                    if loop_state.correction_cycle == 0:
                        loop_state.correction_cycle = 1
                        loop_state.outer_round = 1
                plan: dict[str, Any] = dict(chain.steps.get("plan") or {})
                repair_payload: dict[str, Any] | None = chain.steps.get("repair")
                check_passed = bool((chain.steps.get("check") or {}).get("passed"))
                capture_passed = bool((chain.steps.get("capture") or {}).get("passed"))
                if resume and plan.get("blocked"):
                    salvage = _stage_worktree_salvage(
                        workspace,
                        chain,
                        plan,
                        loop_state.correction_cycle,
                    )
                    if salvage is not None:
                        repair_payload = salvage
                        phase_entry = "check"
            else:
                loop_state = LoopBudgetState()
                chain = ReasoningChain()
                phase_entry = "recognise"
                plan = {}
                repair_payload = None
                check_passed = False
                capture_passed = False
            outcome.chain = chain
            run_context = run_context_from_gate(gate)
            run_context["case_mode"] = gate.case_mode
            run_context["initial_gate_verdict"] = gate.verdict.value
            run_context["require_flutter_capture_verify"] = (
                gate.verdict == FailureClass.CAPTURE_FAILED
                and pipeline_policy.check_flutter_capture_verify
            )
            run_context["loop_budget"] = loop_state.snapshot()
            run_context["pivot"] = None
            board = gate.agent_board
            effective_case_mode = gate.case_mode
            effective_committed_run_id = gate.committed_build_run_id
            effective_served_run_id = gate.served_build_run_id
            regen_payload: dict[str, Any] | None = None
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
                    run_context=run_context,
                )

            def _prepare_read_context(
                step: str,
                *,
                plan_payload: dict[str, Any] | None = None,
            ) -> None:
                reasoning = chain.compact_json_for_step(
                    step,
                    run_context.get("pivot"),
                )
                run_context["_l6_bindings"] = build_l6_bindings(
                    step=step,
                    board=board,
                    workspace=workspace,
                    feature=feature,
                    project_label=project_label,
                    run_context=run_context,
                    reasoning_chain_json=reasoning,
                    chain=chain,
                    plan=plan_payload,
                )

            def _invoke_read_step(
                step: str,
                *,
                figma_png_bytes: bytes | None = None,
                flutter_render_png_bytes: bytes | None = None,
            ) -> dict[str, Any]:
                _prepare_read_context(
                    step,
                    plan_payload=plan if step == "repair" else None,
                )
                return read_step(
                    step_runner,
                    step,  # type: ignore[arg-type]
                    board=board,
                    run_context=run_context,
                    chain=chain,
                    state_dir=workspace.state_dir,
                    user_prompt=_read_user_prompt(step),
                    loop_round=loop_state.correction_cycle,
                    chain_path=chain_path,
                    figma_png=figma_png_bytes,
                    flutter_render_png=flutter_render_png_bytes,
                )

            def _route_after_diagnose(diagnose: dict[str, Any]) -> bool:
                """Validate diagnose output and set ``phase_entry``. Return False to exit."""
                nonlocal phase_entry, advance_correction_cycle
                if diagnose.get("blocked"):
                    outcome.stopped = True
                    outcome.stop_reason = "diagnose_blocked"
                    return False
                try:
                    validate_diagnose_output(diagnose, chain)
                except FigmaFlutterError as exc:
                    error_text = str(exc)
                    run_context["diagnose_validation_error"] = error_text
                    repair_logger().warning("Diagnose validation failed error={}", exc)
                    route = apply_budget(
                        RouteDecision.DIAGNOSE_REFINE,
                        loop_state,
                        loops_config,
                    )
                    if route == RouteDecision.STOP_HUMAN:
                        outcome.stopped = True
                        outcome.stop_reason = "diagnose_empty_laws"
                        plan_payload = terminal_blocked_plan_for_empty_diagnose(
                            diagnose=diagnose,
                            validation_error=error_text,
                        )
                        chain.append("plan", plan_payload)
                        write_step_state(workspace.state_dir, "plan", plan_payload)
                        append_checkpoint(
                            workspace.state_dir,
                            step="plan",
                            loop_round=loop_state.correction_cycle,
                        )
                        return False
                    chain.steps.pop("diagnose", None)
                    phase_entry = "diagnose"
                    advance_correction_cycle = False
                    return True
                run_context.pop("diagnose_validation_error", None)
                phase_entry = "plan"
                return True

            figma_png: bytes | None = None
            flutter_render_png: bytes | None = None
            figma_path = workspace.debug_mirror / "figma.png"
            if figma_path.is_file() and board == "screen":
                figma_png = figma_path.read_bytes()
            for render_name in ("flutter_render.png", "capture.png"):
                render_path = workspace.debug_mirror / render_name
                if render_path.is_file():
                    flutter_render_png = render_path.read_bytes()
                    break

            advance_correction_cycle = True
            while loop_state.correction_cycle < _MAX_OUTER_ROUNDS:
                if advance_correction_cycle:
                    if phase_entry in FULL_CYCLE_PHASE_ENTRIES:
                        loop_state.correction_cycle += 1
                        loop_state.outer_round = loop_state.correction_cycle
                        outcome.loop_rounds = loop_state.correction_cycle
                        if not await require_next_round(
                            round_gate,
                            loop_state.correction_cycle,
                            outcome,
                            phase_entry=phase_entry,
                            preview={"hint": f"(entry={phase_entry})"},
                        ):
                            chain.save(chain_path)
                            return outcome
                    elif loop_state.correction_cycle == 0:
                        loop_state.correction_cycle = 1
                        loop_state.outer_round = 1
                        outcome.loop_rounds = 1
                    advance_correction_cycle = False

                loop_state.orchestrator_steps += 1
                if loop_state.orchestrator_steps > loops_config.max_total_orchestrator_steps:
                    outcome.stopped = True
                    outcome.stop_reason = "max_orchestrator_steps"
                    chain.save(chain_path)
                    return outcome

                run_context["loop_budget"] = loop_state.snapshot()
                loop_round = loop_state.correction_cycle
                skip_to_check = phase_entry == "check"
                ran_repair_this_iteration = False
                salvage_pending = run_context.pop("_salvage_repair_payload", None)
                if salvage_pending is not None:
                    repair_payload = salvage_pending
                    ran_repair_this_iteration = True
                    skip_to_check = True

                if not skip_to_check:
                    if phase_entry == "recognise":
                        require_flutter_render = bool(
                            run_context.get("require_flutter_capture_verify")
                        )
                        run_context["vision_bundle"] = build_vision_bundle(
                            debug_mirror=workspace.debug_mirror,
                            repair_root=workspace.repair_root,
                            case_mode=gate.case_mode,
                            require_flutter_render=require_flutter_render,
                        )
                        if gate.case_mode == "SCREEN" and not run_context["vision_bundle"].get(
                            "complete"
                        ):
                            recognise_degraded = {
                                "step": "recognise",
                                "degraded": True,
                                "degraded_to": "FORENSIC",
                                "blocked_reason": run_context["vision_bundle"].get(
                                    "blockedReason"
                                ),
                            }
                            write_step_state(
                                workspace.state_dir,
                                "recognise",
                                recognise_degraded,
                            )
                            chain.append("recognise", recognise_degraded)
                            append_checkpoint(
                                workspace.state_dir,
                                step="recognise",
                                loop_round=loop_state.correction_cycle,
                            )
                            run_context["case_mode"] = "FORENSIC"
                            board = "forensic"
                        diagnose_retry = False
                        for step in ("recognise", "inspect", "diagnose"):
                            if not await require_step(step_gate, step, outcome):
                                chain.save(chain_path)
                                return outcome
                            payload = _invoke_read_step(
                                step,
                                figma_png_bytes=figma_png if step == "recognise" else None,
                                flutter_render_png_bytes=(
                                    flutter_render_png if step == "recognise" else None
                                ),
                            )
                            if step == "diagnose":
                                if not _route_after_diagnose(payload):
                                    chain.save(chain_path)
                                    return outcome
                                if phase_entry == "diagnose":
                                    diagnose_retry = True
                                    break
                        if diagnose_retry:
                            continue

                    if phase_entry == "inspect":
                        run_context["vision_bundle"] = build_vision_bundle(
                            debug_mirror=workspace.debug_mirror,
                            repair_root=workspace.repair_root,
                            case_mode=str(run_context.get("case_mode") or gate.case_mode),
                            require_flutter_render=bool(
                                run_context.get("require_flutter_capture_verify")
                            ),
                        )
                        diagnose_retry = False
                        for step in ("inspect", "diagnose"):
                            if not await require_step(step_gate, step, outcome):
                                chain.save(chain_path)
                                return outcome
                            payload = _invoke_read_step(step)
                            if step == "diagnose":
                                if not _route_after_diagnose(payload):
                                    chain.save(chain_path)
                                    return outcome
                                if phase_entry == "diagnose":
                                    diagnose_retry = True
                                    break
                        if diagnose_retry:
                            continue

                    if phase_entry == "diagnose":
                        if not await require_step(step_gate, "diagnose", outcome):
                            chain.save(chain_path)
                            return outcome
                        diagnose = _invoke_read_step("diagnose")
                        if not _route_after_diagnose(diagnose):
                            chain.save(chain_path)
                            return outcome
                        if phase_entry == "diagnose":
                            continue

                    if phase_entry == "plan":
                        diagnose_step = chain.steps.get("diagnose") or {}
                        if diagnose_laws_missing(diagnose_step, chain):
                            error_text = str(
                                run_context.get("diagnose_validation_error")
                                or "diagnose produced no laws after inspect compiler anchors"
                            )
                            plan = terminal_blocked_plan_for_empty_diagnose(
                                diagnose=diagnose_step,
                                validation_error=error_text,
                            )
                            chain.append("plan", plan)
                            write_step_state(workspace.state_dir, "plan", plan)
                            append_checkpoint(
                                workspace.state_dir,
                                step="plan",
                                loop_round=loop_state.correction_cycle,
                            )
                            outcome.stopped = True
                            outcome.stop_reason = "diagnose_empty_laws"
                            chain.save(chain_path)
                            return outcome
                        if not await require_step(step_gate, "plan", outcome):
                            chain.save(chain_path)
                            return outcome
                        plan_validated = False
                        for attempt in range(3):
                            loop_state.plan_validation_attempts += 1
                            if attempt:
                                chain.steps.pop("plan", None)
                            try:
                                plan = _invoke_read_step("plan")
                            except FigmaFlutterError as exc:
                                run_context["plan_validation_error"] = str(exc)
                                repair_logger().warning(
                                    "Plan structured output failed attempt={} error={}",
                                    attempt + 1,
                                    exc,
                                )
                                continue
                            try:
                                validate_plan(
                                    plan,
                                    worktree=workspace.worktree,
                                    diagnose_payload=chain.steps.get("diagnose"),
                                )
                            except FigmaFlutterError as exc:
                                run_context["plan_validation_error"] = str(exc)
                                repair_logger().warning(
                                    "Plan validation failed attempt={} error={}",
                                    attempt + 1,
                                    exc,
                                )
                                continue
                            write_step_state(workspace.state_dir, "plan", plan)
                            chain.append("plan", plan)
                            chain.save(chain_path)
                            plan_validated = True
                            run_context.pop("plan_validation_error", None)
                            break
                        if not plan_validated:
                            route = apply_budget(
                                RouteDecision.DIAGNOSE_REFINE,
                                loop_state,
                                loops_config,
                            )
                            if route == RouteDecision.STOP_HUMAN:
                                outcome.stopped = True
                                outcome.stop_reason = "plan_invalid_targets"
                                chain.save(chain_path)
                                return outcome
                            plan_root = same_root_hash(
                                failure_class="plan_invalid_targets",
                                normalized_stage="plan",
                            )
                            run_context["pivot"] = build_pivot(
                                refine_reason=str(
                                    run_context.get("plan_validation_error")
                                    or "plan_invalid_targets"
                                ),
                                chain=chain,
                                same_root_hash=plan_root,
                                failed_evidence=["plan:validation_failed"],
                            )
                            phase_entry = "diagnose"
                            save_loop_budget(workspace.state_dir, loop_state)
                            advance_correction_cycle = True
                            continue
                        if plan.get("blocked"):
                            salvage = _stage_worktree_salvage(
                                workspace,
                                chain,
                                plan,
                                loop_state.correction_cycle,
                            )
                            if salvage is not None:
                                repair_payload = salvage
                                run_context["_salvage_repair_payload"] = salvage
                                phase_entry = "check"
                                save_loop_budget(workspace.state_dir, loop_state)
                                advance_correction_cycle = False
                                continue
                            outcome.stopped = True
                            outcome.stop_reason = "plan_blocked"
                            chain.save(chain_path)
                            return outcome
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
                            loop_round=loop_state.correction_cycle,
                            board=board,
                            chain=chain,
                            run_context=run_context,
                            project_label=project_label,
                        )
                        if repair_payload is None:
                            chain.save(chain_path)
                            return outcome
                        if outcome.stopped or repair_payload.get("provider_error"):
                            chain.append("repair", repair_payload)
                            chain.save(chain_path)
                            return outcome
                        if repair_scope_drift_payload(repair_payload):
                            chain.append("repair", repair_payload)
                            scope_block = repair_payload.get("scope") or {}
                            violations = list(scope_block.get("violations") or [])
                            if violations and workspace is not None:
                                revert_scope_violation_paths(workspace.worktree, violations)
                            route_decision = route_after_repair_scope_drift(
                                repair_payload,
                                plan if plan else {},
                                loop_state,
                                loops_config,
                            )
                            if route_decision == RouteDecision.STOP_HUMAN:
                                outcome.stopped = True
                                outcome.stop_reason = "SCOPE_DRIFT"
                                chain.save(chain_path)
                                return outcome
                            failed_evidence = [
                                "repair: scope drift — edits outside plan targetFiles",
                                *[f"scope_violation: {path}" for path in violations[:6]],
                            ]
                            run_context["pivot"] = build_pivot(
                                refine_reason="SCOPE_DRIFT",
                                chain=chain,
                                same_root_hash="",
                                failed_evidence=failed_evidence,
                            )
                            if route_decision == RouteDecision.REPAIR_RETRY:
                                phase_entry = "repair"
                            else:
                                phase_entry = "plan"
                            save_loop_budget(workspace.state_dir, loop_state)
                            advance_correction_cycle = False
                            continue
                        if repair_gate_failure_payload(repair_payload):
                            chain.append("repair", repair_payload)
                            gates_block = repair_payload.get("gates") or {}
                            route_decision = route_after_repair_gate_failure(
                                repair_payload,
                                plan if plan else {},
                                loop_state,
                                loops_config,
                            )
                            if route_decision == RouteDecision.STOP_HUMAN:
                                outcome.stopped = True
                                outcome.stop_reason = "repair_gates_failed"
                                chain.save(chain_path)
                                return outcome
                            failed_evidence = [
                                "repair: scoped ruff/pytest gates failed after compiler edits",
                            ]
                            if not gates_block.get("ruff"):
                                ruff_tail = str(gates_block.get("ruff_output") or "").strip()
                                if ruff_tail:
                                    failed_evidence.append(f"ruff: {ruff_tail[:500]}")
                            if not gates_block.get("pytest"):
                                pytest_tail = str(gates_block.get("pytest_output") or "").strip()
                                if pytest_tail:
                                    failed_evidence.append(f"pytest: {pytest_tail[:500]}")
                            run_context["pivot"] = build_pivot(
                                refine_reason="REPAIR_GATES_FAILED",
                                chain=chain,
                                same_root_hash="",
                                failed_evidence=failed_evidence,
                            )
                            phase_entry = "repair"
                            save_loop_budget(workspace.state_dir, loop_state)
                            advance_correction_cycle = False
                            continue
                        if repair_payload.get("noop"):
                            salvage = _stage_worktree_salvage(
                                workspace,
                                chain,
                                plan if plan else {},
                                loop_state.correction_cycle,
                            )
                            if salvage is not None:
                                repair_payload = salvage
                                run_context["_salvage_repair_payload"] = salvage
                                phase_entry = "check"
                                save_loop_budget(workspace.state_dir, loop_state)
                                advance_correction_cycle = False
                                continue
                            chain.append("repair", repair_payload)
                            route_decision = route_after_repair_noop(
                                repair_payload,
                                plan if plan else {},
                                loop_state,
                                loops_config,
                            )
                            if route_decision == RouteDecision.STOP_HUMAN:
                                outcome.stopped = True
                                outcome.stop_reason = (
                                    "repair_incomplete"
                                    if repair_payload.get("incomplete")
                                    else "repair_noop"
                                )
                                chain.save(chain_path)
                                return outcome
                            incomplete = bool(repair_payload.get("incomplete"))
                            refine_reason = "REPAIR_INCOMPLETE" if incomplete else "REPAIR_NOOP"
                            summary = str(repair_payload.get("agent_summary") or "").strip()
                            if summary:
                                run_context["repair_continuation_summary"] = summary
                            failed_evidence = [
                                (
                                    "repair: OpenCode step budget exhausted before compiler edits"
                                    if incomplete
                                    else "repair: OpenCode did not edit plan compiler targetFiles"
                                ),
                            ]
                            if summary:
                                failed_evidence.append(
                                    f"repair_summary: {summary[:500]}",
                                )
                            run_context["pivot"] = build_pivot(
                                refine_reason=refine_reason,
                                chain=chain,
                                same_root_hash="",
                                failed_evidence=failed_evidence,
                            )
                            if route_decision == RouteDecision.REPAIR_RETRY:
                                phase_entry = "repair"
                            else:
                                phase_entry = "plan"
                                run_context.pop("repair_continuation_summary", None)
                            save_loop_budget(workspace.state_dir, loop_state)
                            advance_correction_cycle = False
                            continue
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
                        plan_payload=plan if plan else None,
                    )
                    chain.append("regenerate", regen.payload)
                    append_checkpoint(
                        workspace.state_dir,
                        step="regenerate",
                        loop_round=loop_state.correction_cycle,
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
                    regen_payload = regen.payload
                    identity = reevaluate_build_identity(
                        workspace.debug_mirror,
                        project_dir=project_dir,
                        feature=feature,
                        initial_gate=gate,
                        regenerate_payload=regen_payload,
                    )
                    effective_committed_run_id = identity.committed_run_id
                    effective_served_run_id = identity.served_run_id
                    if identity.refreshed_from_regenerate:
                        effective_case_mode = identity.case_mode
                        board = identity.agent_board
                        run_context["case_mode"] = effective_case_mode

                require_flutter_capture = bool(run_context.get("require_flutter_capture_verify"))
                if (
                    require_flutter_capture
                    and settings.agent.dev.debug_capture
                    and ran_repair_this_iteration
                    and not mirror_regenerated
                ):
                    capture_verify = await run_capture_verify(
                        workspace=workspace,
                        settings=settings,
                        project_dir=resolve_repair_flutter_project_dir(workspace, project_dir),
                        feature=feature,
                    )
                    chain.append("capture_verify", capture_verify.payload)
                    append_checkpoint(
                        workspace.state_dir,
                        step="capture_verify",
                        loop_round=loop_state.correction_cycle,
                    )
                    if trace is not None:
                        trace.record_step(
                            "capture_verify",
                            capture_verify.payload,
                            status="ok" if capture_verify.passed else "blocked",
                        )

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
                    require_flutter_capture=require_flutter_capture,
                )
                chain.append("check", check.payload)
                append_checkpoint(workspace.state_dir, step="check", loop_round=loop_round)
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
                if (
                    not pipeline_policy.fix_enabled
                    and route_decision == RouteDecision.FIX_ATTEMPT
                ):
                    outcome.stopped = True
                    outcome.stop_reason = "fix_disabled"
                    chain.save(chain_path)
                    return outcome
                fix_budget_stopped = False

                while (
                    not check.passed
                    and route_decision == RouteDecision.FIX_ATTEMPT
                    and fix_attempts < max_fix
                    and pipeline_policy.fix_enabled
                ):
                    budget_decision = apply_budget(
                        RouteDecision.FIX_ATTEMPT,
                        loop_state,
                        loops_config,
                    )
                    if budget_decision == RouteDecision.STOP_HUMAN:
                        fix_budget_stopped = True
                        break
                    fix_attempts += 1
                    loop_state.check_after_fix += 1
                    if loop_state.check_after_fix > loops_config.max_check_after_fix:
                        fix_budget_stopped = True
                        break
                    run_context["fix_attempt"] = fix_attempts
                    run_context["max_fix_attempts"] = max_fix
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
                        loop_round=loop_state.correction_cycle,
                        board=board,
                        trace=trace,
                    )
                    if scope_error is not None:
                        outcome.stopped = True
                        outcome.stop_reason = (
                            "opencode_provider_error"
                            if scope_error.get("provider_error")
                            else "SCOPE_DRIFT"
                        )
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
                        require_flutter_capture=require_flutter_capture,
                    )
                    chain.append(f"check_{fix_attempts}", check.payload)
                    append_checkpoint(
                        workspace.state_dir,
                        step=f"check_{fix_attempts}",
                        loop_round=loop_state.correction_cycle,
                    )
                    route_decision = resolve_from_check(check.payload)

                root_hash = str(check.payload.get("same_root_hash") or "")
                check_passed = check.passed

                if not check.passed:
                    budget_blocked = False
                    if fix_budget_stopped:
                        route_decision = RouteDecision.STOP_HUMAN
                        budget_blocked = True
                    elif route_decision == RouteDecision.FIX_ATTEMPT and fix_attempts >= max_fix:
                        route_decision = RouteDecision.DIAGNOSE_REFINE
                        run_context["pivot"] = build_pivot(
                            refine_reason="FIX_EXHAUSTED",
                            chain=chain,
                            same_root_hash=root_hash,
                            failed_evidence=list(check.payload.get("evidence") or []),
                        )
                    if route_decision != RouteDecision.STOP_HUMAN and not fix_budget_stopped:
                        loop_state.record_root_hash(root_hash, improved=False)
                        pre_budget = route_decision
                        route_decision = apply_budget(
                            route_decision,
                            loop_state,
                            loops_config,
                        )
                        budget_blocked = (
                            route_decision == RouteDecision.STOP_HUMAN
                            and pre_budget != RouteDecision.STOP_HUMAN
                        )
                    else:
                        loop_state.record_root_hash(root_hash, improved=False)
                    if route_decision == RouteDecision.STOP_HUMAN:
                        outcome.stopped = True
                        outcome.stop_reason = (
                            "budget_exhausted"
                            if budget_blocked
                            else str(check.payload.get("failure_class") or "check_failed")
                        )
                        save_loop_budget(workspace.state_dir, loop_state)
                        chain.save(chain_path)
                        return outcome
                    if route_decision == RouteDecision.FORENSIC:
                        outcome.stopped = True
                        outcome.stop_reason = "reroute_forensic_required"
                        chain.save(chain_path)
                        return outcome
                    if route_decision in {
                        RouteDecision.DIAGNOSE_REFINE,
                        RouteDecision.PLAN_REVISE,
                        RouteDecision.REPAIR_RETRY,
                        RouteDecision.CHECK_RETRY,
                    }:
                        pivot = run_context.get("pivot") or {}
                        if (
                            route_decision != RouteDecision.CHECK_RETRY
                            and pivot.get("refine_reason") != "FIX_EXHAUSTED"
                        ):
                            run_context["pivot"] = build_pivot(
                                refine_reason=str(
                                    check.payload.get("failure_class") or "CHECK_FAILED"
                                ),
                                chain=chain,
                                same_root_hash=root_hash,
                                failed_evidence=list(check.payload.get("evidence") or []),
                            )
                        phase_entry = entry_step_for(route_decision)
                        save_loop_budget(workspace.state_dir, loop_state)
                        if route_decision in _MID_CYCLE_CHECK_ROUTES:
                            advance_correction_cycle = False
                            continue
                        advance_correction_cycle = True
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
                    served_run_id=effective_served_run_id,
                    committed_run_id=effective_committed_run_id,
                    require_pixel_diff=effective_case_mode == "SCREEN",
                )
                chain.append("capture", capture.payload)
                append_checkpoint(workspace.state_dir, step="capture", loop_round=loop_round)
                capture_passed = capture.passed
                capture_closure_required = (
                    effective_case_mode == "SCREEN"
                    or gate.verdict == FailureClass.CAPTURE_FAILED
                )
                run_context["capture_closure_required"] = capture_closure_required
                improved = check_passed and (not capture_closure_required or capture_passed)
                capture_root_hash = str(capture.payload.get("same_root_hash") or root_hash)
                loop_state.record_root_hash(capture_root_hash, improved=improved)
                if trace is not None:
                    trace.record_step(
                        "capture",
                        capture.payload,
                        status="ok" if capture.passed else "blocked",
                    )

                if not await require_step(step_gate, "review", outcome):
                    chain.save(chain_path)
                    return outcome
                review = _invoke_read_step("review")
                review = apply_review_overrides(
                    review,
                    check_passed=check_passed,
                    capture_passed=capture_passed,
                    case_mode=effective_case_mode,
                    initial_gate_verdict=gate.verdict.value,
                )
                persist_review_state(
                    review,
                    state_dir=workspace.state_dir,
                    chain=chain,
                    loop_round=loop_state.correction_cycle,
                )

                if str(review.get("decision", "")).upper() == "LOOP":
                    review_root = same_root_hash(
                        failure_class=str(review.get("reason_code") or "REVIEW_LOOP"),
                        law_id=str(review.get("law_id") or review.get("lawId") or ""),
                        normalized_stage=str(review.get("route") or "review"),
                    )
                    loop_state.record_root_hash(review_root, improved=False)
                    route_decision = apply_budget(
                        resolve_from_review(review), loop_state, loops_config
                    )
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
                    save_loop_budget(workspace.state_dir, loop_state)
                    advance_correction_cycle = True
                    continue

                task_completed = (
                    str(review.get("decision", "")).upper() == "CONTINUE"
                    and check_passed
                    and (not capture_closure_required or capture_passed)
                )
                if not await require_step(step_gate, "summarize", outcome):
                    chain.save(chain_path)
                    return outcome
                summarize_agent = _invoke_read_step("summarize")
                summarize = route_summarize(
                    review,
                    state_dir=workspace.state_dir,
                    repair_root=workspace.repair_root,
                    task_completed=task_completed,
                    agent_payload=summarize_agent,
                )
                chain.append("summarize", summarize.payload)
                append_checkpoint(workspace.state_dir, step="summarize", loop_round=loop_round)
                if trace is not None:
                    trace.record_step("summarize", summarize.payload)
                outcome.task_completed = task_completed
                chain.save(chain_path)
                repair_logger().info(
                    "Repair pipeline finished feature={} verdict={} task_completed={} rounds={} trace={}",
                    feature,
                    gate.verdict.value,
                    task_completed,
                    loop_state.correction_cycle,
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
            worktree_policy = settings.agent.debug_pipeline.worktrees
            keep_current = (
                frozenset({outcome.workspace.worktree})
                if outcome.workspace is not None
                else frozenset()
            )
            apply_repair_worktree_retention(
                agent_repo_root(),
                retain_latest=worktree_policy.retain_latest,
                keep=keep_current,
                min_age_minutes=worktree_policy.min_age_minutes,
                retain_failed=worktree_policy.retain_failed,
                retain_stop_reasons=tuple(worktree_policy.retain_stop_reasons),
                outcome_stopped=outcome.stopped,
                outcome_stop_reason=outcome.stop_reason,
            )
            if worktree_policy.prune_orphans_after_run:
                prune_orphaned_worktrees(agent_repo_root())
