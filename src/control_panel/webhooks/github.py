"""GitHub webhook event processing."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from control_panel.config.models import GitProvider
from control_panel.db import JobStatus, JobStore
from control_panel.services.close_notify import deliver_issue_closed_notice
from control_panel.services.job_events import publish_issue_closed, update_job_and_publish
from control_panel.services.notify import send_mr_ready_notice
from figma_flutter_agent.observability.posthog_business import (
    DEV_COMMITTED_CHANGE,
    capture_business_event,
    infer_change_kind,
    resolve_distinct_id,
)
from figma_flutter_agent.observability.prometheus_metrics import inc_webhook_event


def verify_signature(*, secret: str, body: bytes, signature_header: str) -> bool:
    """Verify GitHub ``X-Hub-Signature-256`` header."""
    if not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    supplied = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, supplied)


async def process_github_payload(
    payload: dict[str, Any],
    *,
    event_name: str,
    store: JobStore,
    bot: Any,
    settings: Any,
    redis: Any = None,
) -> None:
    """Process GitHub issue and pull request webhook events."""
    try:
        await _process_github_payload_inner(
            payload,
            event_name=event_name,
            store=store,
            bot=bot,
            settings=settings,
            redis=redis,
        )
        inc_webhook_event("github", event_name or "unknown", "success")
    except Exception:
        inc_webhook_event("github", event_name or "unknown", "error")
        raise


async def _process_github_payload_inner(
    payload: dict[str, Any],
    *,
    event_name: str,
    store: JobStore,
    bot: Any,
    settings: Any,
    redis: Any = None,
) -> None:
    """Process GitHub issue and pull request webhook events."""
    if event_name == "issues":
        action = payload.get("action")
        issue = payload.get("issue") or {}
        if action != "closed":
            return
        repo = (payload.get("repository") or {}).get("full_name") or ""
        issue_number = int(issue.get("number") or 0)
        job = await store.find_job_by_issue(
            repo,
            issue_number,
            provider=GitProvider.GITHUB.value,
        )
        if job is None:
            job = await _find_job_by_github_marker(store, payload)
        if job is None:
            return
        issue_url = str(issue.get("html_url") or job.issue_url or job.gitlab_issue_url or "")
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
    if event_name == "pull_request":
        action = payload.get("action")
        pull_request = payload.get("pull_request") or {}
        branch = str((pull_request.get("head") or {}).get("ref") or "")
        if action == "closed" and bool(pull_request.get("merged")):
            job = await store.find_job_by_branch(branch)
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
                        "origin": "github_webhook",
                    },
                )
            return
        if action not in {"opened", "reopened", "synchronize"}:
            return
        job = await store.find_job_by_branch(branch)
        if job is None:
            return
        pr_url = str(pull_request.get("html_url") or job.publish_pr_url or "")
        pr_number = int(pull_request.get("number") or job.publish_pr_number or 0)
        await update_job_and_publish(
            redis,
            store,
            job.id,
            status=JobStatus.MR_READY.value,
            publish_pr_url=pr_url,
            publish_pr_number=pr_number,
        )
        if bot is not None:
            await send_mr_ready_notice(bot, job, mr_url=pr_url)


async def _find_job_by_github_marker(store: JobStore, payload: dict[str, Any]) -> Any:
    """Lookup a job by GitHub issue body marker fallback."""
    body = str((payload.get("issue") or {}).get("body") or "")
    marker_prefix = "<!-- figma-flutter-agent-job:"
    if marker_prefix not in body:
        return None
    start = body.index(marker_prefix) + len(marker_prefix)
    end = body.find("-->", start)
    if end < 0:
        return None
    job_id = body[start:end].strip()
    return await store.get_job(job_id)
