"""GitLab webhook event processing."""

from __future__ import annotations

from typing import Any

from control_panel.db import JobStore
from control_panel.db.enums import RepairJobStatus
from control_panel.db.repair_store import RepairJobStore
from control_panel.gitlab_workflow.orchestrate import handle_gitlab_event
from control_panel.repair.gitlab_status import post_status_comment
from control_panel.services.job_events import update_job_and_publish
from control_panel.services.notify import send_mr_ready_notice
from figma_flutter_agent.observability.posthog_business import (
    DEV_COMMITTED_CHANGE,
    capture_business_event,
    infer_change_kind,
    resolve_distinct_id,
)
from figma_flutter_agent.observability.prometheus_metrics import inc_webhook_event


async def process_gitlab_payload(
    payload: dict[str, Any],
    *,
    store: JobStore,
    bot: Any,
    settings: Any,
    redis: Any = None,
    repair_store: RepairJobStore | None = None,
    arq_pool: Any = None,
) -> None:
    """Process GitLab issue, note, and merge request webhook events."""
    object_kind = str(payload.get("object_kind") or "unknown")
    try:
        await handle_gitlab_event(
            payload,
            store=store,
            settings=settings,
            redis=redis,
            repair_store=repair_store,
            arq_pool=arq_pool,
            bot=bot,
        )
        if object_kind == "merge_request":
            await _handle_merge_request(
                payload,
                store=store,
                bot=bot,
                settings=settings,
                redis=redis,
                repair_store=repair_store,
            )
        inc_webhook_event("gitlab", object_kind, "success")
    except Exception:
        inc_webhook_event("gitlab", object_kind, "error")
        raise


async def _handle_merge_request(
    payload: dict[str, Any],
    *,
    store: JobStore,
    bot: Any,
    settings: Any,
    redis: Any = None,
    repair_store: RepairJobStore | None = None,
) -> None:
    """Handle merge request lifecycle for legacy Discord and repair jobs."""
    attrs = payload.get("object_attributes") or {}
    state = attrs.get("state")
    action = attrs.get("action")
    branch = str(attrs.get("source_branch") or "")
    if state == "merged" or action == "merge":
        job = await store.find_job_by_branch(branch)
        if job is None:
            project_id = str((payload.get("project") or {}).get("id") or "")
            mr_iid = int(attrs.get("iid") or 0)
            job = await store.find_job_by_mr(project_id, mr_iid)
        if job is not None:
            capture_business_event(
                settings=settings,
                event=DEV_COMMITTED_CHANGE,
                distinct_id=resolve_distinct_id(
                    discord_user_id=job.discord_user_id,
                    principal=job.principal,
                    job_id=job.id,
                ),
                properties={
                    "job_id": job.id,
                    "branch": branch,
                    "change_kind": infer_change_kind(commit_message="", branch=branch),
                    "origin": "gitlab_webhook",
                },
            )
        return
    if state not in {"opened", "merged"} and action not in {"open", "merge"}:
        return
    if branch.startswith("repair/") and repair_store is not None:
        repair_job_id = branch.removeprefix("repair/")
        repair_job = await repair_store.get_job(repair_job_id)
        if repair_job is not None:
            await post_status_comment(settings, repair_job, RepairJobStatus.MR_READY)
        return
    job = await store.find_job_by_branch(branch)
    if job is None:
        project_id = str((payload.get("project") or {}).get("id") or "")
        mr_iid = int(attrs.get("iid") or 0)
        job = await store.find_job_by_mr(project_id, mr_iid)
    if job is None:
        return
    mr_url = str(attrs.get("url") or job.gitlab_mr_url or job.publish_pr_url or "")
    await update_job_and_publish(
        redis,
        store,
        job.id,
        gitlab_mr_iid=int(attrs.get("iid") or job.gitlab_mr_iid or 0),
        gitlab_mr_url=mr_url,
        publish_pr_url=mr_url,
    )
    if bot is not None:
        await send_mr_ready_notice(bot, job, mr_url=mr_url)
