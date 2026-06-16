"""Internal API routes."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from control_panel.api.deps import get_bot, get_redis, get_settings, get_store
from control_panel.services import events as event_handlers
from control_panel.services.job_events import publish_worker_event

router = APIRouter(tags=["internal"])


class JobEventPayload(BaseModel):
    """Worker callback payload."""

    event: str = Field(
        description="preview_ready | failed | publish_ready | feedback_issue_created"
    )
    error_message: str | None = None


@router.get("/internal/jobs/{job_id}/preview")
async def preview_session(
    request: Request,
    job_id: str,
    x_internal_secret: str = Header(default=""),
) -> dict[str, Any]:
    """Return preview session metadata for the local companion."""
    settings = get_settings(request)
    if not secrets.compare_digest(x_internal_secret, settings.yaml.internal.callback_secret):
        raise HTTPException(status_code=401, detail="unauthorized")
    store = get_store(request)
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "jobId": job.id,
        "projectDir": job.project_dir,
        "featureSlug": job.feature_slug,
        "tokenHash": job.preview_token_hash,
        "fixedPreviewUrl": job.fixed_preview_url,
        "adaptivePreviewUrl": job.adaptive_preview_url,
    }


@router.post("/internal/jobs/{job_id}/events")
async def job_event(
    request: Request,
    job_id: str,
    payload: JobEventPayload,
    x_internal_secret: str = Header(default=""),
) -> dict[str, str]:
    """Receive worker lifecycle events and notify Discord."""
    settings = get_settings(request)
    if not secrets.compare_digest(x_internal_secret, settings.yaml.internal.callback_secret):
        raise HTTPException(status_code=401, detail="unauthorized")
    store = get_store(request)
    bot = get_bot(request)
    redis = get_redis(request)
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    refreshed = await store.get_job(job_id)
    if refreshed is not None:
        await publish_worker_event(
            redis,
            refreshed,
            payload.event,
            error_message=payload.error_message,
        )
    await event_handlers.dispatch_job_event(
        bot=bot,
        store=store,
        job=job,
        event=payload.event,
        error_message=payload.error_message,
    )
    return {"status": "ok"}
