"""Close feedback issue from Discord button."""

from __future__ import annotations

from typing import TYPE_CHECKING

import disnake

from control_panel.db import AutocloseMode, JobStatus
from control_panel.services.close_notify import deliver_issue_closed_notice
from control_panel.services.issues import IssueService

if TYPE_CHECKING:
    from control_panel.bot.app import DiscordControlBot


async def handle_close_issue(*, inter: disnake.MessageInteraction, job_id: str) -> None:
    """Close the remote issue when user autoclose policy allows it."""
    bot = inter.bot
    if not isinstance(bot, DiscordControlBot):
        await inter.response.send_message("Bot context unavailable.", ephemeral=True)
        return
    store = bot.job_store
    settings = bot.settings
    job = await store.get_job(job_id)
    if job is None:
        await inter.response.send_message("Job not found.", ephemeral=True)
        return
    if inter.author.id != job.discord_user_id:
        await inter.response.send_message(
            "Only the job author can close this issue.", ephemeral=True
        )
        return
    mode = await store.get_autoclose_mode(inter.author.id)
    if mode != AutocloseMode.USER.value:
        await inter.response.send_message(
            "Закрытие тикета пользователем отключено. Используй /autoclose.",
            ephemeral=True,
        )
        return
    if job.status != JobStatus.FEEDBACK_ISSUE_CREATED:
        await inter.response.send_message("Issue is not open for this job.", ephemeral=True)
        return

    await inter.response.defer(ephemeral=True)
    try:
        await IssueService(settings).close_issue(job)
    except Exception as exc:
        await inter.edit_original_response(content=f"Не удалось закрыть тикет: {exc}")
        return

    await store.update_job(job_id, status=JobStatus.ISSUE_CLOSED.value)
    refreshed = await store.get_job(job_id)
    if refreshed is not None:
        issue_url = refreshed.issue_url or refreshed.gitlab_issue_url or ""
        await deliver_issue_closed_notice(
            bot=bot,
            settings=settings,
            store=store,
            job=refreshed,
            issue_url=issue_url,
        )
    await inter.edit_original_response(content="Тикет закрыт.")
