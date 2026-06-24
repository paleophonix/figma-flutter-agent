"""Repair job orchestration state machine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db.enums import RepairJobStatus, RepairStage
from control_panel.db.repair_store import RepairJob, RepairJobStore
from control_panel.db.store import JobStore
from control_panel.repair.context import synthesize_repair_ticket
from control_panel.repair.evaluation import DiagnoseOpinion, evaluate_diagnose_opinion
from control_panel.repair.gates import run_repair_gates
from control_panel.repair.gitlab_status import post_status_comment, post_ticket_comment
from control_panel.repair.opencode.client import OpenCodeClient
from control_panel.repair.opencode.parse import extract_text, parse_diagnose_opinion
from control_panel.repair.opencode.policy import (
    load_debug_pipeline_from_agent_repo,
    resolve_cp_prompt_kwargs,
)
from control_panel.repair.opencode.transport import SyncMessageTransport
from control_panel.repair.publish import run_repair_publish
from control_panel.repair.snapshot import copy_processed_snapshot
from control_panel.repair.ticket import render_ticket_markdown
from control_panel.repair.worktree import create_repair_worktree, destroy_repair_worktree
from control_panel.services.repair_events import update_repair_job_and_publish
from figma_flutter_agent.config.debug_pipeline import DebugPipelineConfig
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.debug.paths import screen_debug_safe_project
from figma_flutter_agent.dev.opencode.opencode_policy import build_opencode_overlay
from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.prometheus_metrics import track_repair_stage

_DIAGNOSE_PROMPT = (
    "Diagnose the repair ticket. Output JSON with keys: "
    "root_cause, confidence (0-1), recommended_law, escalate (bool).\n\n"
    "RepairTicket:\n{ticket_json}"
)


async def _set_stage(
    redis: Any,
    store: RepairJobStore,
    job_id: str,
    *,
    status: RepairJobStatus | None = None,
    stage: RepairStage,
    **fields: Any,
) -> RepairJob | None:
    payload: dict[str, Any] = {"stage": stage}
    if status is not None:
        payload["status"] = status
    payload.update(fields)
    return await update_repair_job_and_publish(redis, store, job_id, **payload)


def _opencode_client(settings: DiscordBotSettings, worktree: Path) -> OpenCodeClient:
    repair = settings.yaml.repair
    password = settings.opencode_server_password.get_secret_value()
    return OpenCodeClient(
        base_url=repair.opencode_base_url,
        password=password,
        worktree_directory=worktree.as_posix(),
    )


async def _run_opencode_stage(
    client: OpenCodeClient,
    transport: SyncMessageTransport,
    *,
    stage_key: str,
    job: RepairJob,
    pipeline: DebugPipelineConfig,
    cp_stage: str,
    stage_model: str,
    prompt: str,
) -> tuple[str, dict[str, str]]:
    """Create session, send prompt, return response text and updated session map."""
    prompt_kwargs = resolve_cp_prompt_kwargs(
        stage=cp_stage,
        stage_model=stage_model,
        pipeline=pipeline,
    )
    sessions = dict(job.opencode_session_ids)
    session_id = await client.create_session(title=f"repair-{job.id}-{stage_key}")
    sessions[stage_key] = session_id
    response = await transport.send(session_id, text=prompt, **prompt_kwargs)
    return extract_text(response), sessions


async def _run_diagnose(
    client: OpenCodeClient,
    transport: SyncMessageTransport,
    *,
    job: RepairJob,
    ticket_json: str,
    pipeline: DebugPipelineConfig,
    stage_model: str,
) -> tuple[DiagnoseOpinion, dict[str, str]]:
    text, sessions = await _run_opencode_stage(
        client,
        transport,
        stage_key="diagnose",
        job=job,
        pipeline=pipeline,
        cp_stage="diagnose",
        stage_model=stage_model,
        prompt=_DIAGNOSE_PROMPT.format(ticket_json=ticket_json),
    )
    return parse_diagnose_opinion(text), sessions


async def run_repair_pipeline(
    *,
    settings: DiscordBotSettings,
    store: RepairJobStore,
    generation_store: JobStore,
    repair_job_id: str,
    redis: Any = None,
) -> None:
    """Execute the full repair pipeline for one job.

    Args:
        settings: Control panel settings.
        store: Repair job persistence.
        generation_store: Generation job store for parent lookup.
        repair_job_id: Repair job identifier.
        redis: Optional Redis for SSE events.
    """
    if not settings.yaml.repair.enabled:
        raise FigmaFlutterError("Repair pipeline is disabled (repair.enabled=false)")
    job = await store.get_job(repair_job_id)
    if job is None:
        return
    agent_repo = Path(settings.yaml.repair.agent_repo_path or agent_repo_root()).resolve()
    pipeline = load_debug_pipeline_from_agent_repo(agent_repo)
    await ensure_opencode_serve(
        base_url=settings.yaml.repair.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
        username=settings.yaml.repair.opencode_username,
        config_overlay=build_opencode_overlay(pipeline),
    )
    worktree: Path | None = None
    try:
        parent = None
        if job.parent_generation_job_id:
            parent = await generation_store.get_job(job.parent_generation_job_id)
        if parent is None:
            raise FigmaFlutterError("Parent generation job not found for repair")
        flutter_dir = Path(job.flutter_project_dir or parent.project_dir)
        feature_slug = job.feature_slug or parent.feature_slug or "screen"
        project_slug = job.project_slug or screen_debug_safe_project(flutter_dir)
        await post_status_comment(settings, job, RepairJobStatus.RUNNING)
        job = await _set_stage(
            redis,
            store,
            repair_job_id,
            status=RepairJobStatus.RUNNING,
            stage=RepairStage.PREP,
        )
        if job is None:
            return
        with track_repair_stage(RepairStage.PREP.value):
            worktree = create_repair_worktree(agent_repo, repair_job_id)
            snapshot = copy_processed_snapshot(
                flutter_project_dir=flutter_dir,
                feature_slug=feature_slug,
                worktree=worktree,
                project_slug=project_slug,
            )
            await store.update_job(
                repair_job_id,
                worktree_path=worktree.as_posix(),
                project_slug=project_slug,
                feature_slug=feature_slug,
                flutter_project_dir=flutter_dir.as_posix(),
            )
        job = await store.get_job(repair_job_id)
        if job is None:
            return
        with track_repair_stage(RepairStage.CONTEXT.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.CONTEXT)
            issue_excerpt = f"repair job {repair_job_id}"
            if parent.feedback_comment:
                issue_excerpt = parent.feedback_comment
            ticket = await synthesize_repair_ticket(
                settings=settings,
                debug_root=snapshot.dest_debug_root,
                issue_excerpt=issue_excerpt,
            )
            ticket_json = ticket.model_dump_json()
            await store.update_job(repair_job_id, repair_ticket_json=ticket_json)
            if job.gitlab_project_id and job.gitlab_issue_iid:
                await post_ticket_comment(
                    settings,
                    project_id=job.gitlab_project_id,
                    issue_iid=job.gitlab_issue_iid,
                    body=render_ticket_markdown(ticket, repair_job_id=repair_job_id),
                )
            if ticket.escalate_to_human:
                await _set_stage(
                    redis,
                    store,
                    repair_job_id,
                    status=RepairJobStatus.FAILED,
                    stage=RepairStage.CONTEXT,
                    error_message=ticket.escalate_reason or "Escalate to human",
                )
                await post_status_comment(settings, job, RepairJobStatus.FAILED)
                return
        client = _opencode_client(settings, worktree)
        transport = SyncMessageTransport(client)
        repair_models = settings.yaml.repair.models
        with track_repair_stage(RepairStage.DIAGNOSE.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.DIAGNOSE)
            diagnose, sessions = await _run_diagnose(
                client,
                transport,
                job=job,
                ticket_json=ticket_json,
                pipeline=pipeline,
                stage_model=repair_models.diagnose,
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
            gate = evaluate_diagnose_opinion(ticket, diagnose)
            if not gate.proceed:
                await _set_stage(
                    redis,
                    store,
                    repair_job_id,
                    status=RepairJobStatus.FAILED,
                    stage=RepairStage.DIAGNOSE,
                    error_message=gate.notes or "Diagnose blocked repair",
                )
                await post_status_comment(settings, job, RepairJobStatus.FAILED)
                return
        with track_repair_stage(RepairStage.PLAN.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.PLAN)
            plan_text, sessions = await _run_opencode_stage(
                client,
                transport,
                stage_key="plan",
                job=job,
                pipeline=pipeline,
                cp_stage="plan",
                stage_model=repair_models.plan,
                prompt=(
                    "Produce a numbered implementation plan as JSON list under key steps.\n\n"
                    f"Diagnosis:\n{diagnose.model_dump_json()}\n\nTicket:\n{ticket_json}"
                ),
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
        with track_repair_stage(RepairStage.BUILD.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.BUILD)
            build_text, sessions = await _run_opencode_stage(
                client,
                transport,
                stage_key="build",
                job=job,
                pipeline=pipeline,
                cp_stage="build",
                stage_model=repair_models.build,
                prompt=(
                    "Implement the approved plan in src/figma_flutter_agent only. "
                    "Run ruff and pytest on touched modules.\n\n"
                    f"Plan:\n{plan_text}\n\nTicket:\n{ticket_json}"
                ),
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
        with track_repair_stage(RepairStage.GATES.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.GATES)
            gate_result = run_repair_gates(worktree)
            if not gate_result.passed and settings.yaml.repair.build_retry_on_gate_fail:
                logger.warning("Repair gates failed; retrying build once for {}", repair_job_id)
                with track_repair_stage(RepairStage.BUILD.value):
                    await _set_stage(redis, store, repair_job_id, stage=RepairStage.BUILD)
                    build_text, sessions = await _run_opencode_stage(
                        client,
                        transport,
                        stage_key="build-retry",
                        job=job,
                        pipeline=pipeline,
                        cp_stage="build",
                        stage_model=repair_models.build,
                        prompt=(
                            f"Gates failed.\nRuff:\n{gate_result.ruff_output}\n"
                            f"Pytest:\n{gate_result.pytest_output}\n"
                            f"Fix and re-run checks.\nPrior build:\n{build_text}"
                        ),
                    )
                    await store.update_job(repair_job_id, opencode_session_ids=sessions)
                gate_result = run_repair_gates(worktree)
            if not gate_result.passed:
                await _set_stage(
                    redis,
                    store,
                    repair_job_id,
                    status=RepairJobStatus.FAILED,
                    stage=RepairStage.GATES,
                    error_message="ruff/pytest gates failed",
                )
                await post_status_comment(settings, job, RepairJobStatus.FAILED)
                return
        with track_repair_stage(RepairStage.REVIEW.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.REVIEW)
            review_text, sessions = await _run_opencode_stage(
                client,
                transport,
                stage_key="review",
                job=job,
                pipeline=pipeline,
                cp_stage="review",
                stage_model=repair_models.review,
                prompt=(
                    "Review the repair diff for regression risk. Output pass/fail and summary.\n\n"
                    f"Build summary:\n{build_text}\n\nGates passed: {gate_result.passed}"
                ),
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
        with track_repair_stage(RepairStage.PUBLISH.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.PUBLISH)
            job = await store.get_job(repair_job_id)
            if job is None:
                return
            publish = await run_repair_publish(settings=settings, job=job, worktree=worktree)
            await _set_stage(
                redis,
                store,
                repair_job_id,
                status=RepairJobStatus.MR_READY,
                stage=RepairStage.PUBLISH,
                gitlab_mr_url=publish.mr_url,
                gitlab_mr_iid=publish.mr_iid,
            )
            if job.gitlab_project_id and job.gitlab_issue_iid:
                await post_ticket_comment(
                    settings,
                    project_id=job.gitlab_project_id,
                    issue_iid=job.gitlab_issue_iid,
                    body=f"**MR ready:** {publish.mr_url}",
                )
            await post_status_comment(settings, job, RepairJobStatus.MR_READY)
    except Exception as exc:
        logger.exception("Repair pipeline failed for {}", repair_job_id)
        message = str(exc)[:4000]
        await update_repair_job_and_publish(
            redis,
            store,
            repair_job_id,
            status=RepairJobStatus.FAILED,
            error_message=message,
        )
        failed = await store.get_job(repair_job_id)
        if failed is not None:
            await post_status_comment(settings, failed, RepairJobStatus.FAILED)
    finally:
        if worktree is not None:
            destroy_repair_worktree(agent_repo, worktree)
