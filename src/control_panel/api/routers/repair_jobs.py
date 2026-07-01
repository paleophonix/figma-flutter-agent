"""Public REST repair job routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from control_panel.api.deps import (
    get_arq_pool,
    get_redis,
    get_repair_store,
    get_settings,
    get_store,
    require_principal,
)
from control_panel.api.schemas import (
    CreateRepairJobRequest,
    CreateRepairJobResponse,
    RepairJobListResponse,
    RepairJobResponse,
)
from control_panel.config import DiscordBotSettings
from control_panel.db.repair_store import RepairJob, RepairJobStore
from control_panel.db.store import JobStore
from control_panel.services.repair_events import (
    is_terminal_repair_status,
    repair_event_channel,
    snapshot_repair_event,
)
from control_panel.services.repair_jobs import enqueue_repair
from figma_flutter_agent.errors import FigmaFlutterError

router = APIRouter(prefix="/v1/repair-jobs", tags=["repair-jobs"])


def _repair_response(job: RepairJob) -> RepairJobResponse:
    """Map internal repair job to public response."""
    return RepairJobResponse(
        job_id=job.id,
        status=job.status.value,
        stage=job.stage.value if job.stage else None,
        origin=job.origin,
        principal=job.principal,
        parent_generation_job_id=job.parent_generation_job_id,
        feature_slug=job.feature_slug,
        gitlab_mr_url=job.gitlab_mr_url,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _owned_repair_job(
    store: RepairJobStore,
    job_id: str,
    principal: str,
) -> RepairJob:
    job = await store.get_job(job_id)
    if job is None or job.principal != principal:
        raise HTTPException(status_code=404, detail="not_found")
    return job


@router.post(
    "",
    status_code=202,
    response_model=CreateRepairJobResponse,
    summary="Create repair job",
    description="Enqueue compiler auto-repair for a failed generation job or GitLab issue.",
)
async def create_repair_job(
    body: CreateRepairJobRequest,
    principal: str = Depends(require_principal),
    settings: DiscordBotSettings = Depends(get_settings),
    repair_store: RepairJobStore = Depends(get_repair_store),
    generation_store: JobStore = Depends(get_store),
    pool: Any = Depends(get_arq_pool),
) -> CreateRepairJobResponse:
    """Create and enqueue a repair job."""
    if not body.generation_job_id and not (body.gitlab_project_id and body.gitlab_issue_iid):
        raise HTTPException(
            status_code=422,
            detail="generation_job_id or gitlab_project_id+gitlab_issue_iid required",
        )
    try:
        result = await enqueue_repair(
            settings=settings,
            repair_store=repair_store,
            generation_store=generation_store,
            arq_pool=pool,
            parent_generation_job_id=body.generation_job_id,
            gitlab_project_id=body.gitlab_project_id,
            gitlab_issue_iid=body.gitlab_issue_iid,
            principal=principal,
            origin="api",
        )
    except FigmaFlutterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CreateRepairJobResponse(
        job_id=result.job_id,
        status=result.job.status.value,
        queued_behind=result.queued_behind,
    )


@router.get(
    "",
    response_model=RepairJobListResponse,
    summary="List repair jobs",
)
async def list_repair_jobs(
    principal: str = Depends(require_principal),
    repair_store: RepairJobStore = Depends(get_repair_store),
    limit: int = 50,
    offset: int = 0,
) -> RepairJobListResponse:
    """Return paginated repair jobs for one principal."""
    jobs = await repair_store.list_jobs_by_principal(principal, limit=limit, offset=offset)
    return RepairJobListResponse(
        items=[_repair_response(job) for job in jobs],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{job_id}",
    response_model=RepairJobResponse,
    summary="Get repair job",
)
async def get_repair_job(
    job_id: str,
    principal: str = Depends(require_principal),
    repair_store: RepairJobStore = Depends(get_repair_store),
) -> RepairJobResponse:
    """Return one repair job."""
    job = await _owned_repair_job(repair_store, job_id, principal)
    return _repair_response(job)


@router.get(
    "/{job_id}/events",
    summary="Repair job event stream",
)
async def stream_repair_job_events(
    job_id: str,
    principal: str = Depends(require_principal),
    repair_store: RepairJobStore = Depends(get_repair_store),
    redis: Any = Depends(get_redis),
) -> StreamingResponse:
    """Stream Redis-backed repair job lifecycle events."""
    job = await _owned_repair_job(repair_store, job_id, principal)

    async def generator() -> AsyncIterator[str]:
        yield f"data: {json.dumps(snapshot_repair_event(job), ensure_ascii=False)}\n\n"
        if is_terminal_repair_status(job.status.value):
            return
        if redis is None:
            return
        pubsub = redis.pubsub()
        await pubsub.subscribe(repair_event_channel(job_id))
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=30.0,
                )
                if message is None:
                    await asyncio.sleep(0.05)
                    continue
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                status = str(
                    payload.get("status") or payload.get("payload", {}).get("status") or ""
                )
                if is_terminal_repair_status(status):
                    break
        finally:
            await pubsub.unsubscribe(repair_event_channel(job_id))
            await pubsub.aclose()

    return StreamingResponse(generator(), media_type="text/event-stream")
