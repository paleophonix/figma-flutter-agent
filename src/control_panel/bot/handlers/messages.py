"""Capture feedback comments from Discord channel messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import disnake

from control_panel.db import JobStatus
from figma_flutter_agent.observability.posthog_business import (
    DEV_SUBMITTED_FEEDBACK,
    capture_business_event,
    resolve_distinct_id,
)

if TYPE_CHECKING:
    from control_panel.bot.app import DiscordControlBot


async def handle_feedback_comment_message(bot: DiscordControlBot, message: disnake.Message) -> bool:
    """If the message is a pending feedback comment, enqueue issue creation."""
    if message.author.bot or not message.content or not message.content.strip():
        return False
    store = bot.job_store
    job = await store.find_awaiting_comment_job(
        discord_user_id=message.author.id,
        discord_channel_id=message.channel.id,
    )
    if job is None:
        return False

    await store.update_job(
        job.id,
        feedback_comment=message.content.strip()[:8000],
        feedback_comment_message_id=message.id,
        status=JobStatus.FEEDBACK_ISSUE_CREATING.value,
    )
    await store.append_audit(
        job_id=job.id,
        discord_user_id=message.author.id,
        action="feedback_comment",
        payload={"length": len(message.content.strip())},
    )
    capture_business_event(
        settings=bot.settings,
        event=DEV_SUBMITTED_FEEDBACK,
        distinct_id=resolve_distinct_id(discord_user_id=message.author.id, job_id=job.id),
        properties={
            "job_id": job.id,
            "feedback_quality": job.feedback_quality.value if job.feedback_quality else "unknown",
            "origin": "discord",
            "has_comment": True,
        },
    )
    pool = bot.arq_pool
    if pool is None:
        await message.channel.send(
            f"<@{message.author.id}> Очередь недоступна — не могу создать тикет.",
        )
        return True
    await pool.enqueue_job("feedback_issue_job", job.id)
    await message.channel.send(
        f"<@{message.author.id}> Принято. Создаю тикет по job `{job.id}`…",
    )
    return True
