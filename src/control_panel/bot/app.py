"""Discord bot application wiring."""

from __future__ import annotations

import disnake
from disnake.ext import commands

from control_panel.bot.handlers.messages import handle_feedback_comment_message
from control_panel.bot.views.close_issue import CloseIssueView
from control_panel.config import DiscordBotSettings
from control_panel.db import JobStatus, JobStore


class DiscordControlBot(commands.InteractionBot):
    """Interaction bot with shared job store and settings."""

    def __init__(
        self,
        *,
        settings: DiscordBotSettings,
        store: JobStore,
        arq_pool: object | None = None,
    ) -> None:
        intents = disnake.Intents.default()
        intents.message_content = True
        super().__init__(
            intents=intents,
            test_guilds=settings.yaml.discord.guild_ids or None,
        )
        self.settings = settings
        self.job_store = store
        self.arq_pool = arq_pool
        self._persistent_views_registered = False

    async def on_ready(self) -> None:
        if self._persistent_views_registered:
            return
        from control_panel.bot.views.feedback import PreviewFeedbackView

        jobs = await self.job_store.list_jobs_by_status(JobStatus.PREVIEW_READY)
        for job in jobs:
            self.add_view(PreviewFeedbackView(job_id=job.id))
        open_issues = await self.job_store.list_jobs_by_status(JobStatus.FEEDBACK_ISSUE_CREATED)
        for job in open_issues:
            self.add_view(CloseIssueView(job_id=job.id))
        self._persistent_views_registered = True

    async def on_message(self, message: disnake.Message) -> None:
        await handle_feedback_comment_message(self, message)
        await super().on_message(message)
