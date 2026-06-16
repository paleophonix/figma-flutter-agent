"""Discord close-notification delivery."""

from __future__ import annotations

import disnake

from control_panel.config import DiscordBotSettings
from control_panel.db.store import GenerationJob, JobStore
from control_panel.services.issues import IssueService
from control_panel.services.notify import send_changelog_notice, send_issue_closed_notice
from control_panel.services.telegram import TelegramNotifier


async def deliver_issue_closed_notice(
    *,
    bot: disnake.ext.commands.InteractionBot | None,
    settings: DiscordBotSettings,
    store: JobStore,
    job: GenerationJob,
    issue_url: str,
) -> None:
    """Post issue close to Discord (reply thread or changelog) and optional Telegram."""
    from control_panel.db import IssueKind

    last_comment = await IssueService(settings).fetch_last_issue_comment(job)
    if job.issue_kind == IssueKind.FEAT:
        if bot is not None:
            await send_changelog_notice(
                bot,
                settings,
                job=job,
                issue_url=issue_url,
                last_comment=last_comment,
            )
        return

    if bot is None:
        return

    await send_issue_closed_notice(
        bot,
        job,
        issue_url=issue_url,
        last_comment=last_comment,
    )
    notifier = TelegramNotifier(settings)
    if (
        notifier.enabled
        and job.discord_user_id is not None
        and await store.is_telegram_enabled(job.discord_user_id)
    ):
        await notifier.notify_issue_closed(store, job, issue_url=issue_url)
