"""Discord notification helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import disnake
from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db import GenerationJob

if TYPE_CHECKING:
    from control_panel.bot.views.close_issue import CloseIssueView
    from control_panel.bot.views.feedback import PreviewFeedbackView


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
    close_view: CloseIssueView | None = None,
) -> None:
    """Confirm issue creation to the author."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return
    await channel.send(
        content=(
            f"<@{job.discord_user_id}> **Feedback issue created**\n\nJob: `{job.id}`\n{issue_url}"
        ),
        view=close_view,
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
        content=(f"<@{job.discord_user_id}> **Merge request ready**\n\nJob: `{job.id}`\n{mr_url}")
    )


async def send_issue_closed_notice(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    issue_url: str,
    last_comment: str | None = None,
) -> None:
    """Notify the author that a feedback issue was closed.

    When ``feedback_comment_message_id`` is set, replies in-thread to the user's
    feedback comment. Body prefers the last tracker comment when available.
    """
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return

    if last_comment and last_comment.strip():
        content = (
            f"<@{job.discord_user_id}> **Тикет закрыт**\n"
            f"{issue_url}\n\n"
            f"{last_comment.strip()[:1800]}"
        )
    else:
        content = (
            f"<@{job.discord_user_id}> **Feedback issue closed**\n\nJob: `{job.id}`\n{issue_url}"
        )

    message_id = job.feedback_comment_message_id
    if message_id is not None:
        try:
            reference = await channel.fetch_message(message_id)
            await reference.reply(content=content)
            return
        except disnake.NotFound:
            logger.warning(
                "Feedback comment message {} not found for job {}",
                message_id,
                job.id,
            )
        except disnake.HTTPException:
            logger.exception(
                "Failed to reply to feedback comment message {} for job {}",
                message_id,
                job.id,
            )

    await channel.send(content=content)


async def send_changelog_notice(
    bot: disnake.ext.commands.InteractionBot,
    settings: DiscordBotSettings,
    job: GenerationJob,
    *,
    issue_url: str,
    last_comment: str | None,
) -> None:
    """Post the last tracker comment to the configured changelog channel."""
    channel_id = settings.yaml.discord.changelog_channel_id
    if channel_id is None:
        logger.warning("changelog_channel_id is not configured; skipping feat close notice")
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.warning("Changelog Discord channel {} not found", channel_id)
        return
    if not last_comment or not last_comment.strip():
        logger.warning("Feat issue closed for job {} without a last comment", job.id)
        return

    feature = job.feature_slug or "screen"
    content = f"**feat: {feature}**\n{issue_url}\n\n{last_comment.strip()[:1800]}"
    await channel.send(content=content)


async def send_publish_ready_notice(
    bot: disnake.ext.commands.InteractionBot,
    job: GenerationJob,
    *,
    pr_url: str,
) -> None:
    """Notify the author that a pull request was published."""
    channel = bot.get_channel(job.discord_channel_id)
    if channel is None:
        return
    await channel.send(
        content=(
            f"<@{job.discord_user_id}> **Pull request published**\n\nJob: `{job.id}`\n{pr_url}"
        )
    )
