"""Repair job orchestration state machine."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db.enums import RepairJobStatus, RepairStage
from control_panel.db.repair_store import RepairJob, RepairJobStore
from control_panel.db.store import JobStore
from control_panel.repair.context import synthesize_repair_ticket
from control_panel.repair.evaluation import DiagnoseOpinion, evaluate_diagnose_opinions
from control_panel.repair.gates import run_repair_gates
from control_panel.repair.gitlab_status import post_status_comment, post_ticket_comment
from control_panel.repair.opencode.client import OpenCodeClient
from control_panel.repair.opencode.parse import extract_text, parse_diagnose_opinion
from control_panel.repair.opencode.transport import SyncMessageTransport
from control_panel.repair.publish import run_repair_publish
from control_panel.repair.roles import EPISTEMIC_ROLES, ROLE_AGENT_MAP, role_prompt_slice
from control_panel.repair.snapshot import copy_processed_snapshot
from control_panel.repair.ticket import render_ticket_markdown
from control_panel.repair.worktree import create_repair_worktree, destroy_repair_worktree
from control_panel.services.repair_events import update_repair_job_and_publish
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.debug.paths import screen_debug_safe_project
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.prometheus_metrics import track_repair_stage


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
    agent: str,
    prompt: str,
    model: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Create session, send prompt, return response text and updated session map."""
    sessions = dict(job.opencode_session_ids)
    session_id = await client.create_session(title=f"repair-{job.id}-{stage_key}")
    sessions[stage_key] = session_id
    response = await transport.send(session_id, text=prompt, agent=agent, model=model)
    return extract_text(response), sessions


async def _diagnose_one(
    client: OpenCodeClient,
    transport: SyncMessageTransport,
    *,
    job: RepairJob,
    role: str,
    ticket_json: str,
    model: str | None,
) -> DiagnoseOpinion:
    agent = ROLE_AGENT_MAP[role]
    prompt = role_prompt_slice(role, ticket_json)
    text, _ = await _run_opencode_stage(
        client,
        transport,
        stage_key=f"diagnose-{role}",
        job=job,
        agent=agent,
        prompt=prompt,
        model=model,
    )
    return parse_diagnose_opinion(role, text)


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
        settings: Control plane settings.
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
            ticket = await synthesize_repair_ticket(
                settings=settings,
                debug_root=snapshot.dest_debug_root,
                issue_excerpt=f"repair job {repair_job_id}",
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
        diagnose_model = settings.yaml.repair.models.diagnose.strip() or None
        with track_repair_stage(RepairStage.DIAGNOSE.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.DIAGNOSE)
            opinions = await asyncio.gather(
                *[
                    _diagnose_one(
                        client,
                        transport,
                        job=job,
                        role=role,
                        ticket_json=ticket_json,
                        model=diagnose_model,
                    )
                    for role in EPISTEMIC_ROLES
                ]
            )
        with track_repair_stage(RepairStage.EVAL.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.EVAL)
            evaluation = evaluate_diagnose_opinions(ticket, list(opinions))
            if not evaluation.proceed_to_consilium:
                await _set_stage(
                    redis,
                    store,
                    repair_job_id,
                    status=RepairJobStatus.FAILED,
                    stage=RepairStage.EVAL,
                    error_message=evaluation.notes or "Evaluation blocked consilium",
                )
                await post_status_comment(settings, job, RepairJobStatus.FAILED)
                return
        with track_repair_stage(RepairStage.CONSILIUM.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.CONSILIUM)
            consilium_text, sessions = await _run_opencode_stage(
            client,
            transport,
            stage_key="consilium",
            job=job,
            agent="repair-consilium",
            prompt=(
                "Synthesize diagnostician opinions into one repair recommendation.\n\n"
                f"Ticket:\n{ticket_json}\n\nOpinions:\n"
                f"{json.dumps([o.model_dump() for o in opinions], ensure_ascii=False)}"
            ),
            model=settings.yaml.repair.models.consilium.strip() or None,
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
        with track_repair_stage(RepairStage.PLAN.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.PLAN)
            plan_text, sessions = await _run_opencode_stage(
                client,
                transport,
                stage_key="plan",
                job=job,
                agent="repair-planner",
                prompt=(
                    "Produce a numbered implementation plan as JSON list under key steps.\n\n"
                    f"Consilium:\n{consilium_text}\n\nTicket:\n{ticket_json}"
                ),
                model=settings.yaml.repair.models.plan.strip() or None,
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
        with track_repair_stage(RepairStage.BUILD.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.BUILD)
            build_text, sessions = await _run_opencode_stage(
                client,
                transport,
                stage_key="build",
                job=job,
                agent="repair-build",
                prompt=(
                    "Implement the approved plan in src/figma_flutter_agent only. "
                    "Run ruff and pytest on touched modules.\n\n"
                    f"Plan:\n{plan_text}\n\nTicket:\n{ticket_json}"
                ),
                model=settings.yaml.repair.models.build.strip() or None,
            )
            await store.update_job(repair_job_id, opencode_session_ids=sessions)
        with track_repair_stage(RepairStage.GATES.value):
            await _set_stage(redis, store, repair_job_id, stage=RepairStage.GATES)
            gate = run_repair_gates(worktree)
            if not gate.passed and settings.yaml.repair.build_retry_on_gate_fail:
                logger.warning("Repair gates failed; retrying build once for {}", repair_job_id)
                with track_repair_stage(RepairStage.BUILD.value):
                    await _set_stage(redis, store, repair_job_id, stage=RepairStage.BUILD)
                    build_text, sessions = await _run_opencode_stage(
                        client,
                        transport,
                        stage_key="build-retry",
                        job=job,
                        agent="repair-build",
                        prompt=(
                            f"Gates failed.\nRuff:\n{gate.ruff_output}\nPytest:\n{gate.pytest_output}\n"
                            f"Fix and re-run checks.\nPrior build:\n{build_text}"
                        ),
                        model=settings.yaml.repair.models.build.strip() or None,
                    )
                    await store.update_job(repair_job_id, opencode_session_ids=sessions)
                gate = run_repair_gates(worktree)
            if not gate.passed:
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
                agent="repair-review",
                prompt=(
                    "Review the repair diff for regression risk. Output pass/fail and summary.\n\n"
                    f"Build summary:\n{build_text}\n\nGates passed: {gate.passed}"
                ),
                model=settings.yaml.repair.models.review.strip() or None,
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
