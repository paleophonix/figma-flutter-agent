"""Redis pub/sub repair job lifecycle events for SSE consumers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from control_panel.db.enums import RepairJobStatus
from control_panel.db.repair_store import RepairJob, RepairJobStore

REPAIR_EVENT_CHANNEL = "control_panel:repair:{job_id}:events"

TERMINAL_REPAIR_STATUSES = frozenset(
    {
        RepairJobStatus.FAILED.value,
        RepairJobStatus.MR_READY.value,
        RepairJobStatus.CANCELLED.value,
    }
)


def repair_event_channel(job_id: str) -> str:
    """Return Redis channel name for one repair job."""
    return REPAIR_EVENT_CHANNEL.format(job_id=job_id)


def build_repair_event(
    job: RepairJob,
    event_type: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized SSE/event envelope."""
    body: dict[str, Any] = {
        "type": event_type,
        "jobId": job.id,
        "status": job.status.value,
        "origin": job.origin,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }
    if job.stage is not None:
        body["stage"] = job.stage.value
    return body


async def publish_repair_event(redis: Any, job_id: str, event: dict[str, Any]) -> None:
    """Publish one repair job event to Redis."""
    if redis is None:
        return
    channel = repair_event_channel(job_id)
    await redis.publish(channel, json.dumps(event, ensure_ascii=False))


def is_terminal_repair_status(status: str) -> bool:
    """Return whether a repair status is terminal."""
    return status in TERMINAL_REPAIR_STATUSES


async def update_repair_job_and_publish(
    redis: Any,
    store: RepairJobStore,
    job_id: str,
    **fields: Any,
) -> RepairJob | None:
    """Update repair job and publish status_changed when status moves."""
    previous = await store.get_job(job_id)
    updated = await store.update_job(job_id, **fields)
    if updated is None or previous is None:
        return updated
    if updated.status != previous.status:
        await publish_repair_event(
            redis,
            job_id,
            build_repair_event(
                updated,
                "status_changed",
                payload={
                    "status": updated.status.value,
                    "previousStatus": previous.status.value,
                },
            ),
        )
    elif updated.stage != previous.stage:
        await publish_repair_event(
            redis,
            job_id,
            build_repair_event(
                updated,
                "stage_changed",
                payload={"stage": updated.stage.value if updated.stage else None},
            ),
        )
    return updated


def snapshot_repair_event(job: RepairJob) -> dict[str, Any]:
    """Build a snapshot event for SSE subscribers."""
    payload: dict[str, Any] = {
        "status": job.status.value,
        "gitlabMrUrl": job.gitlab_mr_url,
        "errorMessage": job.error_message,
    }
    if job.stage is not None:
        payload["stage"] = job.stage.value
    return build_repair_event(job, "snapshot", payload=payload)
