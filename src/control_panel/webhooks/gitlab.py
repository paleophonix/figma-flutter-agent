"""GitLab webhook event processing."""

from __future__ import annotations

from typing import Any

from loguru import logger

from control_panel.config.models import GitProvider
from control_panel.db import JobStatus, JobStore
from control_panel.db.enums import RepairJobStatus
from control_panel.db.repair_store import RepairJobStore
from control_panel.repair.gitlab_status import post_status_comment
from control_panel.services.close_notify import deliver_issue_closed_notice
from control_panel.services.job_events import publish_issue_closed, update_job_and_publish
from control_panel.services.notify import send_mr_ready_notice
from control_panel.services.repair_jobs import enqueue_repair
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.posthog_business import (
    DEV_COMMITTED_CHANGE,
    capture_business_event,
    infer_change_kind,
    resolve_distinct_id,
)
from figma_flutter_agent.observability.prometheus_metrics import inc_webhook_event

REPAIR_LABEL = "agent-repair"
REPAIR_COMMAND = "/repair"


def _issue_has_repair_label(labels: list[Any]) -> bool:
    for item in labels:
        title = str(item.get("title") or "") if isinstance(item, dict) else str(item)
        if title == REPAIR_LABEL:
            return True
    return False


async def _maybe_enqueue_repair_from_webhook(
    *,
    settings: Any,
    store: JobStore,
    repair_store: RepairJobStore | None,
    arq_pool: Any,
    project_id: str,
    issue_iid: int,
) -> None:
    if repair_store is None or arq_pool is None:
        return
    if not settings.yaml.repair.enabled:
        return
    try:
        await enqueue_repair(
            settings=settings,
            repair_store=repair_store,
            generation_store=store,
            arq_pool=arq_pool,
            gitlab_project_id=project_id,
            gitlab_issue_iid=issue_iid,
            origin="gitlab_webhook",
        )
    except FigmaFlutterError as exc:
        logger.warning("GitLab repair enqueue skipped: {}", exc)
    except Exception:
        logger.exception("GitLab repair enqueue failed for issue {}:{}", project_id, issue_iid)


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
    """Process GitLab issue and merge request webhook events."""
    object_kind = str(payload.get("object_kind") or "unknown")
    try:
        await _process_gitlab_payload_inner(
            payload,
            store=store,
            bot=bot,
            settings=settings,
            redis=redis,
            repair_store=repair_store,
            arq_pool=arq_pool,
        )
        inc_webhook_event("gitlab", object_kind, "success")
    except Exception:
        inc_webhook_event("gitlab", object_kind, "error")
        raise


async def _process_gitlab_payload_inner(
    payload: dict[str, Any],
    *,
    store: JobStore,
    bot: Any,
    settings: Any,
    redis: Any = None,
    repair_store: RepairJobStore | None = None,
    arq_pool: Any = None,
) -> None:
    """Process GitLab issue and merge request webhook events."""
    object_kind = payload.get("object_kind")
    if object_kind == "issue":
        attrs = payload.get("object_attributes") or {}
        project_id = str((payload.get("project") or {}).get("id") or "")
        issue_iid = int(attrs.get("iid") or 0)
        labels = payload.get("labels") or attrs.get("labels") or []
        action = str(attrs.get("action") or "")
        if action in {"open", "update"} and _issue_has_repair_label(labels):
            await _maybe_enqueue_repair_from_webhook(
                settings=settings,
                store=store,
                repair_store=repair_store,
                arq_pool=arq_pool,
                project_id=project_id,
                issue_iid=issue_iid,
            )
        if attrs.get("state") != "closed":
            return
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
    if object_kind == "note":
        attrs = payload.get("object_attributes") or {}
        note = str(attrs.get("note") or "").strip()
        if REPAIR_COMMAND in note.lower():
            issue = payload.get("issue") or {}
            project_id = str((payload.get("project") or {}).get("id") or "")
            issue_iid = int(issue.get("iid") or 0)
            if project_id and issue_iid:
                await _maybe_enqueue_repair_from_webhook(
                    settings=settings,
                    store=store,
                    repair_store=repair_store,
                    arq_pool=arq_pool,
                    project_id=project_id,
                    issue_iid=issue_iid,
                )
    if object_kind == "merge_request":
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
                mr_url = str(attrs.get("url") or repair_job.gitlab_mr_url or "")
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
            status=JobStatus.MR_READY.value,
            gitlab_mr_iid=int(attrs.get("iid") or job.gitlab_mr_iid or 0),
            gitlab_mr_url=mr_url,
            publish_pr_url=mr_url,
        )
        if bot is not None:
            await send_mr_ready_notice(bot, job, mr_url=mr_url)
