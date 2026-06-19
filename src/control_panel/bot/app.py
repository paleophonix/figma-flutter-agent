"""Discord bot application wiring."""

from __future__ import annotations

import disnake
from disnake.ext import commands
from loguru import logger

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
        guild_ids = settings.yaml.discord.guild_ids or None
        super().__init__(
            intents=intents,
            test_guilds=guild_ids,
        )
        self.settings = settings
        self.job_store = store
        self.arq_pool = arq_pool
        self._persistent_views_registered = False
        self._guild_commands_synced = False

    async def _ensure_guild_command_sync(self) -> None:
        """Register slash commands on joined guilds when no explicit guild_ids are set."""
        if self._guild_commands_synced:
            return

        discord_cfg = self.settings.yaml.discord
        if discord_cfg.guild_ids:
            logger.info("Discord slash commands use guild_ids={}", discord_cfg.guild_ids)
            self._guild_commands_synced = True
            return

        if not discord_cfg.sync_joined_guilds:
            logger.warning(
                "discord.guild_ids is empty; slash commands are GLOBAL and may take up to 1 hour "
                "to appear. Set FIGMA_CP_DISCORD_GUILD_IDS or discord.sync_joined_guilds: true."
            )
            self._guild_commands_synced = True
            return

        joined = [guild.id for guild in self.guilds]
        if not joined:
            logger.warning("Discord bot is not in any guild; slash commands were not guild-synced")
            return

        self._test_guilds = tuple(joined)
        for command in self.all_slash_commands.values():
            command.guild_ids = tuple(joined)
        await self._sync_application_commands()
        logger.info("Discord slash commands synced to joined guilds: {}", joined)
        self._guild_commands_synced = True

    async def on_ready(self) -> None:
        await self._ensure_guild_command_sync()
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
