"""Dispatch worker events to Discord notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from control_panel.bot.views.close_issue import CloseIssueView
from control_panel.bot.views.feedback import PreviewFeedbackView
from control_panel.db import AutocloseMode, JobOrigin, JobStore
from control_panel.runner.errors import enrich_failure_message
from control_panel.services.notify import (
    send_failure_notice,
    send_issue_created_notice,
    send_preview_ready,
    send_publish_ready_notice,
)
from control_panel.services.telegram import TelegramNotifier

if TYPE_CHECKING:
    from control_panel.bot.app import DiscordControlBot
    from control_panel.db.store import GenerationJob


async def dispatch_job_event(
    *,
    bot: DiscordControlBot | None,
    store: JobStore,
    job: GenerationJob,
    event: str,
    error_message: str | None = None,
) -> None:
    """Route a worker lifecycle event to Discord UI updates."""
    if job.origin == JobOrigin.API:
        logger.debug("Skipping Discord dispatch for api-origin job {}", job.id)
        return
    if bot is None:
        logger.debug("Discord bot unavailable; skip dispatch for job {}", job.id)
        return
    if event == "preview_ready":
        refreshed = await store.get_job(job.id)
        if refreshed is None:
            return
        view = PreviewFeedbackView(job_id=refreshed.id)
        bot.add_view(view)
        message = await send_preview_ready(bot, refreshed, view=view)
        await store.update_job(job.id, review_message_id=message.id)
        return
    if event == "failed":
        refreshed = await store.get_job(job.id)
        if refreshed is None:
            return
        await send_failure_notice(
            bot,
            refreshed,
            error_message=enrich_failure_message(
                error_message or refreshed.error_message or "",
            ),
        )
        return
    if event == "publish_ready":
        refreshed = await store.get_job(job.id)
        if refreshed is None:
            return
        await send_publish_ready_notice(
            bot,
            refreshed,
            pr_url=refreshed.publish_pr_url or refreshed.gitlab_mr_url or "",
        )
        return
    if event == "feedback_issue_created":
        refreshed = await store.get_job(job.id)
        if refreshed is None or refreshed.discord_user_id is None:
            return
        issue_url = refreshed.issue_url or refreshed.gitlab_issue_url or ""
        autoclose = await store.get_autoclose_mode(refreshed.discord_user_id)
        close_view = None
        if autoclose == AutocloseMode.USER.value:
            close_view = CloseIssueView(job_id=refreshed.id)
            bot.add_view(close_view)
        await send_issue_created_notice(
            bot,
            refreshed,
            issue_url=issue_url,
            close_view=close_view,
        )
        notifier = TelegramNotifier(bot.settings)
        if notifier.enabled:
            await notifier.notify_issue_created(
                store,
                refreshed,
                issue_url=issue_url,
                autoclose_mode=autoclose,
            )
        return
    logger.warning("Unknown job event {} for job {}", event, job.id)
