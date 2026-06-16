"""Discord notification helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import disnake

from discord_bot.db import GenerationJob

if TYPE_CHECKING:
    from discord_bot.bot.views.feedback import PreviewFeedbackView


async def send_preview_ready(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    view: PreviewFeedbackView,
) -> disnake.Message:
    """Notify the job author that preview is ready."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        raise RuntimeError(f"Discord channel not found: {job.discord_channel_id}")
    content = (
        f"<@{job.discord_user_id}> **Layout ready for review**\n\n"
        f"Job: `{job.id}`\n"
        f"Run: `{job.run_id or '-'}`\n"
        f"Open both previews and choose a quality rating.\n\n"
        f"Fixed: <{job.fixed_preview_url}>\n"
        f"Adaptive: <{job.adaptive_preview_url}>"
    )
    return await channel.send(content=content, view=view)


async def send_failure_notice(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    error_message: str,
) -> None:
    """Notify the job author about a pipeline failure."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return
    await channel.send(
        content=(
            f"<@{job.discord_user_id}> **Generation failed**\n\n"
            f"Job: `{job.id}`\n"
            f"```{error_message[:1500]}```"
        )
    )


async def send_issue_created_notice(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    issue_url: str,
) -> None:
    """Confirm GitLab issue creation to the author."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return
    await channel.send(
        content=(
            f"<@{job.discord_user_id}> **Feedback issue created**\n\n"
            f"Job: `{job.id}`\n"
            f"{issue_url}"
        )
    )


async def send_mr_ready_notice(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    mr_url: str,
) -> None:
    """Notify the author that an MR is ready."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return
    await channel.send(
        content=(
            f"<@{job.discord_user_id}> **Merge request ready**\n\n"
            f"Job: `{job.id}`\n"
            f"{mr_url}"
        )
    )


async def send_issue_closed_notice(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    issue_url: str,
) -> None:
    """Notify the author that a feedback issue was closed."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return
    await channel.send(
        content=(
            f"<@{job.discord_user_id}> **Feedback issue closed**\n\n"
            f"Job: `{job.id}`\n"
            f"{issue_url}"
        )
    )
