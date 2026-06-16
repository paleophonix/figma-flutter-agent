"""Discord close-notification delivery."""

from __future__ import annotations

import disnake

from discord_bot.config import DiscordBotSettings
from discord_bot.db.store import GenerationJob, JobStore
from discord_bot.services.issues import IssueService
from discord_bot.services.notify import send_changelog_notice, send_issue_closed_notice
from discord_bot.services.telegram import TelegramNotifier


async def deliver_issue_closed_notice(
    *,
    bot: disnake.ext.commands.InteractionBot,
    settings: DiscordBotSettings,
    store: JobStore,
    job: GenerationJob,
    issue_url: str,
) -> None:
    """Post issue close to Discord (reply thread or changelog) and optional Telegram."""
    from discord_bot.db import IssueKind

    last_comment = await IssueService(settings).fetch_last_issue_comment(job)
    if job.issue_kind == IssueKind.FEAT:
        await send_changelog_notice(
            bot,
            settings,
            job=job,
            issue_url=issue_url,
            last_comment=last_comment,
        )
        return

    await send_issue_closed_notice(
        bot,
        job,
        issue_url=issue_url,
        last_comment=last_comment,
    )
    notifier = TelegramNotifier(settings)
    if notifier.enabled and await store.is_telegram_enabled(job.discord_user_id):
        await notifier.notify_issue_closed(store, job, issue_url=issue_url)
