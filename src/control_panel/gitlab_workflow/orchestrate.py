"""GitLab Issue webhook orchestration."""

from __future__ import annotations

from typing import Any

from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db import JobOrigin, JobStatus
from control_panel.db.repair_store import RepairJobStore
from control_panel.db.store import JobStore
from control_panel.gitlab_workflow.commands import IssueNoteCommand, parse_issue_note
from control_panel.gitlab_workflow.notify import post_bug_ack_comment, post_regen_ack_comment
from control_panel.gitlab_workflow.parser import extract_first_figma_frame_url
from control_panel.services.job_events import publish_issue_closed, update_job_and_publish
from control_panel.services.jobs import enqueue_generation_from_issue
from control_panel.services.repair_jobs import enqueue_repair
from figma_flutter_agent.errors import FigmaFlutterError


def _workflow_enabled(settings: DiscordBotSettings) -> bool:
    return settings.yaml.gitlab_workflow.enabled


def _agent_username(settings: DiscordBotSettings) -> str:
    return settings.yaml.gitlab_workflow.agent_username.strip()


def _issue_has_agent(payload: dict[str, Any], agent_username: str) -> bool:
    if not agent_username:
        return False
    wanted = agent_username.lower()
    assignees = payload.get("assignees") or []
    for item in assignees:
        if str(item.get("username") or "").lower() == wanted:
            return True
    assignee = payload.get("assignee") or {}
    return str(assignee.get("username") or "").lower() == wanted


async def handle_gitlab_event(
    payload: dict[str, Any],
    *,
    store: JobStore,
    settings: DiscordBotSettings,
    redis: Any = None,
    repair_store: RepairJobStore | None = None,
    arq_pool: Any = None,
    bot: Any = None,
) -> None:
    """Route GitLab webhook payloads for Issue-first workflow."""
    await _handle_gitlab_event_inner(
        payload,
        store=store,
        settings=settings,
        redis=redis,
        repair_store=repair_store,
        arq_pool=arq_pool,
        bot=bot,
    )


async def _handle_gitlab_event_inner(
    payload: dict[str, Any],
    *,
    store: JobStore,
    settings: DiscordBotSettings,
    redis: Any = None,
    repair_store: RepairJobStore | None = None,
    arq_pool: Any = None,
    bot: Any = None,
) -> None:
    if not _workflow_enabled(settings):
        return
    object_kind = payload.get("object_kind")
    if object_kind == "issue":
        await _handle_issue_event(
            payload,
            store=store,
            settings=settings,
            redis=redis,
            arq_pool=arq_pool,
            bot=bot,
        )
        return
    if object_kind == "note":
        await _handle_note_event(
            payload,
            store=store,
            settings=settings,
            repair_store=repair_store,
            arq_pool=arq_pool,
        )


async def _handle_issue_event(
    payload: dict[str, Any],
    *,
    store: JobStore,
    settings: DiscordBotSettings,
    redis: Any = None,
    arq_pool: Any = None,
    bot: Any = None,
) -> None:
    attrs = payload.get("object_attributes") or {}
    project_id = str((payload.get("project") or {}).get("id") or "")
    issue_iid = int(attrs.get("iid") or 0)
    if not project_id or issue_iid <= 0:
        return

    state = str(attrs.get("state") or "")
    action = str(attrs.get("action") or "")
    issue_url = str(attrs.get("url") or "")

    if state == "closed":
        await _handle_issue_closed(
            project_id=project_id,
            issue_iid=issue_iid,
            issue_url=issue_url,
            store=store,
            settings=settings,
            redis=redis,
            arq_pool=arq_pool,
            bot=bot,
        )
        return

    if action not in {"open", "update", "reopen"}:
        return
    if not _issue_has_agent(payload, _agent_username(settings)):
        return

    description = str(attrs.get("description") or "")
    try:
        extract_first_figma_frame_url(description)
    except FigmaFlutterError:
        return

    try:
        await enqueue_generation_from_issue(
            settings=settings,
            store=store,
            arq_pool=arq_pool,
            redis=redis,
            project_id=project_id,
            issue_iid=issue_iid,
            issue_url=issue_url,
            description=description,
            force=False,
        )
    except FigmaFlutterError as exc:
        logger.warning(
            "GitLab issue generate skipped for {}:{} — {}",
            project_id,
            issue_iid,
            exc,
        )


async def _handle_issue_closed(
    *,
    project_id: str,
    issue_iid: int,
    issue_url: str,
    store: JobStore,
    settings: DiscordBotSettings,
    redis: Any = None,
    arq_pool: Any = None,
    bot: Any = None,
) -> None:
    job = await store.find_job_by_issue(project_id, issue_iid, provider="gitlab")
    if job is None:
        job = await store.find_job_by_issue(project_id, issue_iid)
    if job is None:
        return
    prior_status = job.status
    updated = await update_job_and_publish(
        redis,
        store,
        job.id,
        status=JobStatus.ISSUE_CLOSED.value,
    )
    refreshed = updated or job
    if updated is not None:
        await publish_issue_closed(redis, updated, issue_url=issue_url)

    if refreshed.origin != JobOrigin.GITLAB and bot is not None:
        from control_panel.services.close_notify import deliver_issue_closed_notice

        await deliver_issue_closed_notice(
            bot=bot,
            settings=settings,
            store=store,
            job=refreshed,
            issue_url=issue_url,
        )
        return

    if refreshed.origin != JobOrigin.GITLAB:
        return

    if arq_pool is None:
        logger.warning("ARQ pool unavailable; cannot publish MR for job {}", job.id)
        return
    if prior_status not in {
        JobStatus.PREVIEW_READY,
        JobStatus.MR_READY,
        JobStatus.ISSUE_CLOSED,
        JobStatus.ACCEPTED,
    }:
        logger.warning(
            "Issue closed for job {} in status {}; skipping publish",
            job.id,
            prior_status.value,
        )
        return
    await arq_pool.enqueue_job("publish_job", job.id)


async def _handle_note_event(
    payload: dict[str, Any],
    *,
    store: JobStore,
    settings: DiscordBotSettings,
    repair_store: RepairJobStore | None = None,
    arq_pool: Any = None,
) -> None:
    attrs = payload.get("object_attributes") or {}
    note = str(attrs.get("note") or "").strip()
    parsed = parse_issue_note(note)
    if parsed is None:
        return

    issue = payload.get("issue") or {}
    project_id = str((payload.get("project") or {}).get("id") or "")
    issue_iid = int(issue.get("iid") or 0)
    if not project_id or issue_iid <= 0:
        return

    if parsed.command in {IssueNoteCommand.BUG, IssueNoteCommand.REPAIR}:
        await _handle_bug_note(
            settings=settings,
            store=store,
            repair_store=repair_store,
            arq_pool=arq_pool,
            project_id=project_id,
            issue_iid=issue_iid,
            feedback=parsed.body,
        )
        return

    if parsed.command == IssueNoteCommand.FIX:
        issue_url = str(issue.get("url") or "")
        description = str(issue.get("description") or "")
        await post_regen_ack_comment(settings, project_id=project_id, issue_iid=issue_iid)
        await enqueue_generation_from_issue(
            settings=settings,
            store=store,
            arq_pool=arq_pool,
            redis=None,
            project_id=project_id,
            issue_iid=issue_iid,
            issue_url=issue_url,
            description=description,
            force=True,
        )


async def _handle_bug_note(
    *,
    settings: DiscordBotSettings,
    store: JobStore,
    repair_store: RepairJobStore | None,
    arq_pool: Any,
    project_id: str,
    issue_iid: int,
    feedback: str,
) -> None:
    job = await store.find_job_by_issue(project_id, issue_iid, provider="gitlab")
    if job is None:
        logger.warning("No generation job linked to GitLab issue {}:{}", project_id, issue_iid)
        return
    if feedback.strip():
        await store.update_job(job.id, feedback_comment=feedback.strip())

    escalation = settings.yaml.gitlab_workflow.escalation_assignee_username.strip()
    if not escalation:
        escalation = settings.yaml.publish.boss_reviewer_username.strip()
    if escalation:
        from control_panel.services.gitlab import GitLabClient

        gitlab = GitLabClient(
            base_url=settings.yaml.gitlab.base_url,
            token=settings.gitlab_private_token.get_secret_value(),
        )
        await gitlab.update_issue_assignees(
            project_id=project_id,
            issue_iid=issue_iid,
            assignee_username=escalation,
        )

    await post_bug_ack_comment(settings, project_id=project_id, issue_iid=issue_iid)

    if repair_store is None or arq_pool is None:
        logger.warning("Repair queue unavailable for /bug on issue {}:{}", project_id, issue_iid)
        return
    if not settings.yaml.repair.enabled:
        logger.warning("Repair disabled; /bug recorded but not enqueued for issue {}:{}", project_id, issue_iid)
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
        logger.warning("GitLab /bug repair enqueue skipped: {}", exc)
