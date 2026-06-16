"""Discord bot application wiring."""

from __future__ import annotations

import disnake
from disnake.ext import commands

from discord_bot.config import DiscordBotSettings
from discord_bot.db import JobStatus, JobStore


class DiscordControlBot(commands.InteractionBot):
    """Interaction bot with shared job store and settings."""

    def __init__(self, *, settings: DiscordBotSettings, store: JobStore) -> None:
        intents = disnake.Intents.default()
        intents.message_content = False
        super().__init__(
            intents=intents,
            test_guilds=settings.yaml.discord.guild_ids or None,
        )
        self.settings = settings
        self.job_store = store
        self._persistent_views_registered = False

    async def on_ready(self) -> None:
        if self._persistent_views_registered:
            return
        from discord_bot.bot.views.feedback import PreviewFeedbackView

        jobs = await self.job_store.list_jobs_by_status(JobStatus.PREVIEW_READY)
        for job in jobs:
            self.add_view(PreviewFeedbackView(job_id=job.id))
        self._persistent_views_registered = True
