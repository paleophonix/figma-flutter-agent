"""Handle Discord quality feedback button interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import disnake

from control_panel.db import (
    JobStatus,
    JobStore,
    Quality,
)
from figma_flutter_agent.observability.posthog_business import (
    DEV_SUBMITTED_FEEDBACK,
    capture_business_event,
    resolve_distinct_id,
)

if TYPE_CHECKING:
    from control_panel.bot.app import DiscordControlBot


async def handle_feedback(
    *,
    inter: disnake.MessageInteraction,
    job_id: str,
    quality: Quality,
) -> None:
    """Route quality feedback to publish queue or comment collection."""
    bot = inter.bot
    if not isinstance(bot, DiscordControlBot):
        await inter.response.send_message("Bot context unavailable.", ephemeral=True)
        return
    store = bot.job_store
    job = await store.get_job(job_id)
    if job is None:
        await inter.response.send_message("Job not found.", ephemeral=True)
        return
    if inter.author.id != job.discord_user_id:
        await inter.response.send_message(
            "Only the /generate author can rate this layout.",
            ephemeral=True,
        )
        return
    if job.status != JobStatus.PREVIEW_READY:
        await inter.response.send_message("Feedback already handled.", ephemeral=True)
        return

    await inter.response.defer(ephemeral=True)
    await store.append_audit(
        job_id=job_id,
        discord_user_id=inter.author.id,
        action="feedback",
        payload={"quality": quality.value},
    )

    if quality == Quality.GOOD:
        capture_business_event(
            settings=bot.settings,
            event=DEV_SUBMITTED_FEEDBACK,
            distinct_id=resolve_distinct_id(discord_user_id=inter.author.id, job_id=job_id),
            properties={
                "job_id": job_id,
                "feedback_quality": quality.value,
                "origin": "discord",
            },
        )
        await _enqueue_publish(
            inter=inter,
            bot=bot,
            store=store,
            job=job,
        )
        return

    await store.update_job(
        job.id,
        status=JobStatus.AWAITING_FEEDBACK_COMMENT.value,
        feedback_quality=quality.value,
    )
    await inter.edit_original_response(
        content=(
            "Опиши, что не так с вёрсткой — **одним сообщением в этот канал**. "
            "После этого создам тикет с артефактами."
        ),
    )


async def _enqueue_publish(
    *,
    inter: disnake.MessageInteraction,
    bot: DiscordControlBot,
    store: JobStore,
    job,
) -> None:
    from control_panel.db import Quality

    await store.update_job(job.id, status=JobStatus.ACCEPTED.value, feedback_quality=Quality.GOOD.value)
    pool = bot.arq_pool
    if pool is None:
        await inter.edit_original_response(content="Publish queue unavailable.")
        return
    await pool.enqueue_job("publish_job", job.id)
    await inter.edit_original_response(content="Publish queued. You will be notified when the PR is ready.")
