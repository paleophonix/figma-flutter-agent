"""Enqueue compiler auto-repair jobs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from control_panel.config import DiscordBotSettings
from control_panel.db.enums import RepairJobStatus
from control_panel.db.repair_store import RepairJob, RepairJobStore
from control_panel.db.store import GenerationJob, JobStore
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.prometheus_metrics import set_repair_queue_depth


async def _refresh_repair_queue_depth(repair_store: RepairJobStore) -> None:
    set_repair_queue_depth(await repair_store.count_queued())


@dataclass(frozen=True)
class EnqueueRepairResult:
    """Outcome of enqueueing a repair job."""

    job_id: str
    job: RepairJob
    queued_behind: str | None = None


async def enqueue_repair(
    *,
    settings: DiscordBotSettings,
    repair_store: RepairJobStore,
    generation_store: JobStore,
    arq_pool: Any,
    parent_generation_job_id: str | None = None,
    gitlab_project_id: str | None = None,
    gitlab_issue_iid: int | None = None,
    principal: str | None = None,
    origin: str = "api",
) -> EnqueueRepairResult:
    """Create a repair job and enqueue ARQ worker execution when the slot is free.

    Args:
        settings: Control plane settings.
        repair_store: Repair persistence.
        generation_store: Generation job store for parent resolution.
        arq_pool: ARQ redis pool.
        parent_generation_job_id: Source generation job id.
        gitlab_project_id: Linked GitLab project id.
        gitlab_issue_iid: Linked GitLab issue iid.
        principal: API principal owner.
        origin: Job origin label.

    Returns:
        EnqueueRepairResult with new job id.

    Raises:
        FigmaFlutterError: When repair is disabled or parent job missing.
    """
    if not settings.yaml.repair.enabled:
        raise FigmaFlutterError("Repair is disabled (repair.enabled=false)")
    parent: GenerationJob | None = None
    if parent_generation_job_id:
        parent = await generation_store.get_job(parent_generation_job_id)
        if parent is None:
            raise FigmaFlutterError(f"Generation job not found: {parent_generation_job_id}")
    if parent is None and gitlab_project_id and gitlab_issue_iid:
        parent = await generation_store.find_job_by_issue(
            gitlab_project_id,
            gitlab_issue_iid,
            provider="gitlab",
        )
    if parent is None:
        raise FigmaFlutterError("Could not resolve parent generation job for repair")
    active = await repair_store.find_active_job()
    queued_behind = None
    if active is not None and active.status == RepairJobStatus.RUNNING or active is not None and active.status == RepairJobStatus.QUEUED:
        queued_behind = active.id
    job_id = f"repair_{uuid.uuid4().hex[:16]}"
    job = await repair_store.create_job(
        job_id=job_id,
        parent_generation_job_id=parent.id,
        gitlab_project_id=gitlab_project_id or parent.gitlab_app_project_id,
        gitlab_issue_iid=gitlab_issue_iid or parent.gitlab_issue_iid or parent.issue_number,
        feature_slug=parent.feature_slug,
        flutter_project_dir=parent.project_dir,
        principal=principal,
        origin=origin,
    )
    if queued_behind is not None:
        await _refresh_repair_queue_depth(repair_store)
        return EnqueueRepairResult(job_id=job_id, job=job, queued_behind=queued_behind)
    await arq_pool.enqueue_job("run_repair_job", job_id)
    await _refresh_repair_queue_depth(repair_store)
    return EnqueueRepairResult(job_id=job_id, job=job)


async def maybe_enqueue_next_repair(
    *,
    repair_store: RepairJobStore,
    arq_pool: Any,
) -> None:
    """Start the next queued repair job when the serial slot is free."""
    running = await repair_store.find_active_job()
    if running is not None and running.status == RepairJobStatus.RUNNING:
        return
    next_job = await repair_store.find_next_queued()
    if next_job is None:
        return
    await arq_pool.enqueue_job("run_repair_job", next_job.id)
    await _refresh_repair_queue_depth(repair_store)
