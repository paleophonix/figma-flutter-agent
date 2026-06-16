"""Public REST job routes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from control_panel.api.deps import (
    enforce_create_job_rate_limit,
    get_arq_pool,
    get_redis,
    get_settings,
    get_store,
    require_principal,
)
from control_panel.api.schemas import (
    CreateJobRequest,
    CreateJobResponse,
    JobListResponse,
    JobResponse,
)
from control_panel.config import DiscordBotSettings
from control_panel.db import JobOrigin, JobStatus
from control_panel.db.store import GenerationJob, JobStore
from control_panel.services.job_events import (
    is_terminal_status,
    job_event_channel,
    snapshot_event,
)
from control_panel.services.jobs import enqueue_generation
from figma_flutter_agent.errors import FigmaUrlError

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def _job_response(job: GenerationJob) -> JobResponse:
    """Map internal job to public response."""
    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        origin=job.origin.value,
        principal=job.principal,
        figma_url=job.figma_url,
        feature_slug=job.feature_slug,
        repo_key=job.repo_key,
        target_mode=job.target_mode,
        target_file_path=job.target_file_path,
        fixed_preview_url=job.fixed_preview_url,
        adaptive_preview_url=job.adaptive_preview_url,
        artifact_zip_path=job.artifact_zip_path,
        publish_pr_url=job.publish_pr_url or job.gitlab_mr_url,
        issue_url=job.issue_url or job.gitlab_issue_url,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _owned_job(
    store: JobStore,
    job_id: str,
    principal: str,
) -> GenerationJob:
    job = await store.get_job(job_id)
    if job is None or job.principal != principal:
        raise HTTPException(status_code=404, detail="not_found")
    return job


@router.post(
    "",
    status_code=202,
    response_model=CreateJobResponse,
    summary="Create generation job",
    description="Validate Figma URL, create a job, and enqueue pipeline execution.",
)
async def create_job(
    body: CreateJobRequest,
    principal: str = Depends(require_principal),
    _rate_limit: None = Depends(enforce_create_job_rate_limit),
    settings: DiscordBotSettings = Depends(get_settings),
    store: JobStore = Depends(get_store),
    pool: Any = Depends(get_arq_pool),
    redis: Any = Depends(get_redis),
) -> CreateJobResponse:
    """Create and enqueue a generation job for the authenticated principal."""
    try:
        from figma_flutter_agent.figma.url import parse_figma_url

        parse_figma_url(body.figma_url.strip())
    except FigmaUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await enqueue_generation(
        settings=settings,
        store=store,
        arq_pool=pool,
        figma_url=body.figma_url,
        origin=JobOrigin.API,
        principal=principal,
        repo_key=body.repo_key,
        mode=body.mode,
        target_file=body.target_file,
        redis=redis,
    )
    return CreateJobResponse(job_id=result.job_id, status=result.job.status.value)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs",
    description="List jobs owned by the authenticated API principal.",
)
async def list_jobs(
    principal: str = Depends(require_principal),
    store: JobStore = Depends(get_store),
    limit: int = 50,
    offset: int = 0,
) -> JobListResponse:
    """Return paginated jobs for one principal."""
    jobs = await store.list_jobs_by_principal(principal, limit=limit, offset=offset)
    return JobListResponse(
        items=[_job_response(job) for job in jobs],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job",
    description="Return one job when it belongs to the authenticated principal.",
)
async def get_job(
    job_id: str,
    principal: str = Depends(require_principal),
    store: JobStore = Depends(get_store),
) -> JobResponse:
    """Return job status and metadata."""
    job = await _owned_job(store, job_id, principal)
    return _job_response(job)


@router.get(
    "/{job_id}/artifacts",
    summary="Download artifacts",
    description="Download the artifact zip when preview is ready.",
)
async def get_job_artifacts(
    job_id: str,
    principal: str = Depends(require_principal),
    store: JobStore = Depends(get_store),
) -> FileResponse:
    """Return artifact zip for a completed preview."""
    job = await _owned_job(store, job_id, principal)
    if job.status != JobStatus.PREVIEW_READY:
        raise HTTPException(status_code=409, detail="artifacts_not_ready")
    if not job.artifact_zip_path:
        raise HTTPException(status_code=404, detail="artifacts_missing")
    path = Path(job.artifact_zip_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="artifacts_missing")
    return FileResponse(path, filename=path.name, media_type="application/zip")


@router.get(
    "/{job_id}/events",
    summary="Job event stream",
    description="Server-sent events for job lifecycle updates.",
)
async def stream_job_events(
    job_id: str,
    principal: str = Depends(require_principal),
    store: JobStore = Depends(get_store),
    redis: Any = Depends(get_redis),
) -> StreamingResponse:
    """Stream Redis-backed job lifecycle events."""
    job = await _owned_job(store, job_id, principal)

    async def generator():
        yield f"data: {json.dumps(snapshot_event(job), ensure_ascii=False)}\n\n"
        if is_terminal_status(job.status.value):
            return
        if redis is None:
            return
        pubsub = redis.pubsub()
        await pubsub.subscribe(job_event_channel(job_id))
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
                if is_terminal_status(str(payload.get("status") or "")):
                    break
        finally:
            await pubsub.unsubscribe(job_event_channel(job_id))
            await pubsub.aclose()

    return StreamingResponse(generator(), media_type="text/event-stream")
