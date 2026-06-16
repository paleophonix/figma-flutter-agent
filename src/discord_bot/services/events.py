"""Dispatch worker events to Discord notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from discord_bot.bot.views.feedback import PreviewFeedbackView
from discord_bot.db import JobStore
from discord_bot.services.notify import (
    send_failure_notice,
    send_preview_ready,
    send_publish_ready_notice,
)

if TYPE_CHECKING:
    from discord_bot.bot.app import DiscordControlBot
    from discord_bot.db.store import GenerationJob


async def dispatch_job_event(
    *,
    bot: DiscordControlBot,
    store: JobStore,
    job: GenerationJob,
    event: str,
    error_message: str | None = None,
) -> None:
    """Route a worker lifecycle event to Discord UI updates."""
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
        await send_failure_notice(bot, refreshed, error_message=error_message or refreshed.error_message or "")
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
    logger.warning("Unknown job event {} for job {}", event, job.id)
