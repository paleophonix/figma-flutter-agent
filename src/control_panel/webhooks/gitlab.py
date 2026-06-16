"""GitLab webhook event processing."""

from __future__ import annotations

from typing import Any

from control_panel.config.models import GitProvider
from control_panel.db import JobStatus, JobStore
from control_panel.services.close_notify import deliver_issue_closed_notice
from control_panel.services.job_events import publish_issue_closed, update_job_and_publish
from control_panel.services.notify import send_mr_ready_notice


async def process_gitlab_payload(
    payload: dict[str, Any],
    *,
    store: JobStore,
    bot: Any,
    settings: Any,
    redis: Any = None,
) -> None:
    """Process GitLab issue and merge request webhook events."""
    object_kind = payload.get("object_kind")
    if object_kind == "issue":
        attrs = payload.get("object_attributes") or {}
        if attrs.get("state") != "closed":
            return
        project_id = str((payload.get("project") or {}).get("id") or "")
        issue_iid = int(attrs.get("iid") or 0)
        job = await store.find_job_by_issue(
            project_id,
            issue_iid,
            provider=GitProvider.GITLAB.value,
        )
        if job is None:
            return
        issue_url = str(attrs.get("url") or job.issue_url or job.gitlab_issue_url or "")
        updated = await update_job_and_publish(
            redis,
            store,
            job.id,
            status=JobStatus.ISSUE_CLOSED.value,
        )
        if updated is not None:
            await publish_issue_closed(redis, updated, issue_url=issue_url)
        if bot is not None:
            await deliver_issue_closed_notice(
                bot=bot,
                settings=settings,
                store=store,
                job=updated or job,
                issue_url=issue_url,
            )
    if object_kind == "merge_request":
        attrs = payload.get("object_attributes") or {}
        state = attrs.get("state")
        action = attrs.get("action")
        if state not in {"opened", "merged"} and action not in {"open", "merge"}:
            return
        branch = str(attrs.get("source_branch") or "")
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
            status=JobStatus.MR_READY.value,
            gitlab_mr_iid=int(attrs.get("iid") or job.gitlab_mr_iid or 0),
            gitlab_mr_url=mr_url,
            publish_pr_url=mr_url,
        )
        if bot is not None:
            await send_mr_ready_notice(bot, job, mr_url=mr_url)
