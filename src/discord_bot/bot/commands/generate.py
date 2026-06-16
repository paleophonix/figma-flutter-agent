"""Slash command handlers."""

from __future__ import annotations

import uuid

import disnake
from disnake.ext import commands

from discord_bot.bot.access import is_authorized
from discord_bot.services.projects import resolve_project_dir
from figma_flutter_agent.errors import FigmaUrlError
from figma_flutter_agent.figma.url import parse_figma_url


def register_generate_command(bot: commands.InteractionBot) -> None:
    """Register the ``/generate`` slash command on ``bot``."""

    @bot.slash_command(description="Generate Flutter layout from a Figma frame URL")
    async def generate(
        inter: disnake.ApplicationCommandInteraction,
        figma_url: str,
    ) -> None:
        from discord_bot.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("You are not allowed to run /generate.", ephemeral=True)
            return
        try:
            parse_figma_url(figma_url.strip())
        except FigmaUrlError as exc:
            await inter.response.send_message(f"Invalid Figma URL: {exc}", ephemeral=True)
            return

        await inter.response.defer()
        job_id = uuid.uuid4().hex
        project_dir = resolve_project_dir(bot.settings.yaml, inter.author.id)
        gitlab_project_id = bot.settings.yaml.gitlab.app_project_id
        await bot.job_store.create_job(
            job_id=job_id,
            figma_url=figma_url.strip(),
            discord_user_id=inter.author.id,
            discord_channel_id=inter.channel_id,
            project_dir=project_dir,
            gitlab_app_project_id=gitlab_project_id,
        )
        message = await inter.edit_original_response(
            content=(
                f"**Generation started**\n"
                f"Author: {inter.author.mention}\n"
                f"Job: `{job_id}`\n"
                f"Figma: {figma_url.strip()}"
            )
        )
        await bot.job_store.update_job(job_id, discord_message_id=message.id)
        await bot.job_store.append_audit(
            job_id=job_id,
            discord_user_id=inter.author.id,
            action="generate",
            payload={"figma_url": figma_url.strip()},
        )
