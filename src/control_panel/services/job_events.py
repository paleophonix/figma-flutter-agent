"""Redis pub/sub job lifecycle events for SSE consumers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from control_panel.db.enums import JobStatus
from control_panel.db.store import GenerationJob, JobStore

JOB_EVENT_CHANNEL = "control_panel:job:{job_id}:events"

TERMINAL_STATUSES = frozenset(
    {
        JobStatus.FAILED.value,
        JobStatus.ISSUE_CLOSED.value,
        JobStatus.MR_READY.value,
    }
)


def job_event_channel(job_id: str) -> str:
    """Return Redis channel name for one job."""
    return JOB_EVENT_CHANNEL.format(job_id=job_id)


def build_job_event(
    job: GenerationJob,
    event_type: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized SSE/event envelope."""
    return {
        "type": event_type,
        "jobId": job.id,
        "status": job.status.value,
        "origin": job.origin.value,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }


async def publish_job_event(redis: Any, job_id: str, event: dict[str, Any]) -> None:
    """Publish one job event to Redis."""
    if redis is None:
        return
    channel = job_event_channel(job_id)
    await redis.publish(channel, json.dumps(event, ensure_ascii=False))


async def publish_status_changed(
    redis: Any,
    job: GenerationJob,
    *,
    previous_status: JobStatus | None = None,
) -> None:
    """Publish a status transition event."""
    payload: dict[str, Any] = {"status": job.status.value}
    if previous_status is not None:
        payload["previousStatus"] = previous_status.value
    await publish_job_event(
        redis,
        job.id,
        build_job_event(job, "status_changed", payload=payload),
    )


async def publish_worker_event(
    redis: Any,
    job: GenerationJob,
    event: str,
    *,
    error_message: str | None = None,
) -> None:
    """Publish a worker callback event."""
    payload: dict[str, Any] = {}
    if error_message:
        payload["errorMessage"] = error_message
    if event == "preview_ready":
        payload["fixedPreviewUrl"] = job.fixed_preview_url
        payload["adaptivePreviewUrl"] = job.adaptive_preview_url
    if event == "publish_ready":
        payload["prUrl"] = job.publish_pr_url or job.gitlab_mr_url
    if event == "feedback_issue_created":
        payload["issueUrl"] = job.issue_url or job.gitlab_issue_url
    await publish_job_event(redis, job.id, build_job_event(job, event, payload=payload))


async def publish_issue_closed(
    redis: Any,
    job: GenerationJob,
    *,
    issue_url: str,
) -> None:
    """Publish issue closed event."""
    payload = {
        "issueUrl": issue_url,
        "issueKind": job.issue_kind.value if job.issue_kind else None,
    }
    await publish_job_event(redis, job.id, build_job_event(job, "issue_closed", payload=payload))


async def update_job_and_publish(
    redis: Any,
    store: JobStore,
    job_id: str,
    **fields: Any,
) -> GenerationJob | None:
    """Update a job and publish status change when applicable."""
    before = await store.get_job(job_id)
    job = await store.update_job(job_id, **fields)
    if job is None or before is None:
        return job
    if "status" in fields and before.status != job.status:
        await publish_status_changed(redis, job, previous_status=before.status)
    return job


def snapshot_event(job: GenerationJob) -> dict[str, Any]:
    """Build replay snapshot for new SSE subscribers."""
    return build_job_event(
        job,
        "snapshot",
        payload={
            "figmaUrl": job.figma_url,
            "featureSlug": job.feature_slug,
            "fixedPreviewUrl": job.fixed_preview_url,
            "adaptivePreviewUrl": job.adaptive_preview_url,
            "errorMessage": job.error_message,
            "issueUrl": job.issue_url,
            "prUrl": job.publish_pr_url or job.gitlab_mr_url,
        },
    )


def is_terminal_status(status: str) -> bool:
    """Return True when SSE stream may end."""
    return status in TERMINAL_STATUSES


async def publish_snapshot(redis: Any, job: GenerationJob) -> None:
    """Publish current job snapshot (debug helper)."""
    if redis is None:
        return
    await publish_job_event(redis, job.id, snapshot_event(job))
    logger.debug("Published snapshot for job {}", job.id)
