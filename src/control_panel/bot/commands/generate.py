"""Slash command handlers."""

from __future__ import annotations

import disnake
from disnake.ext import commands

from control_panel.bot.access import is_authorized
from control_panel.config.models import TargetMode
from control_panel.db import JobOrigin
from control_panel.publish.scan import list_screen_candidates
from control_panel.services.jobs import enqueue_generation
from control_panel.services.projects import (
    resolve_active_repo_key,
    resolve_repo_config,
)
from figma_flutter_agent.errors import FigmaUrlError
from figma_flutter_agent.figma.url import parse_figma_url


def register_generate_command(bot: commands.InteractionBot) -> None:
    """Register the ``/generate`` slash command on ``bot``."""

    @bot.slash_command(description="Generate Flutter layout from a Figma frame URL")
    async def generate(
        inter: disnake.ApplicationCommandInteraction,
        figma_url: str,
        mode: str = commands.Param(choices=["new", "existing"]),
        target_file: str | None = None,
    ) -> None:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message(
                "You are not allowed to run /generate.", ephemeral=True
            )
            return

        await inter.response.defer()

        try:
            parse_figma_url(figma_url.strip())
        except FigmaUrlError as exc:
            await inter.edit_original_response(content=f"Invalid Figma URL: {exc}")
            return

        try:
            repo_key = await resolve_active_repo_key(bot.settings, bot.job_store, inter.author.id)
            repo_cfg = resolve_repo_config(bot.settings, repo_key)
        except Exception as exc:
            await inter.edit_original_response(content=f"Repository error: {exc}")
            return

        resolved_target = target_file
        if mode == TargetMode.EXISTING.value and not resolved_target:
            candidates = await list_screen_candidates(bot.settings, repo_cfg)
            if not candidates:
                await inter.edit_original_response(
                    content="No screen files found in the active repository.",
                )
                return
            resolved_target = candidates[0]

        result = await enqueue_generation(
            settings=bot.settings,
            store=bot.job_store,
            arq_pool=bot.arq_pool,
            figma_url=figma_url,
            origin=JobOrigin.DISCORD,
            discord_user_id=inter.author.id,
            discord_channel_id=inter.channel_id,
            repo_key=repo_key,
            mode=mode,
            target_file=resolved_target,
        )
        job_id = result.job_id
        message = await inter.edit_original_response(
            content=(
                f"**Generation started**\n"
                f"Author: {inter.author.mention}\n"
                f"Job: `{job_id}`\n"
                f"Repo: `{repo_key}`\n"
                f"Mode: `{mode}`\n"
                f"Target: `{resolved_target or '(new screen)'}`\n"
                f"Figma: {figma_url.strip()}"
            )
        )
        await bot.job_store.update_job(job_id, discord_message_id=message.id)

    @generate.autocomplete("target_file")
    async def target_file_autocomplete(
        inter: disnake.ApplicationCommandInteraction,
        user_input: str,
    ) -> list[str]:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            return []
        try:
            repo_key = await resolve_active_repo_key(bot.settings, bot.job_store, inter.author.id)
            repo_cfg = resolve_repo_config(bot.settings, repo_key)
            candidates = await list_screen_candidates(bot.settings, repo_cfg)
        except Exception:
            return []
        if user_input:
            candidates = [item for item in candidates if user_input.lower() in item.lower()]
        return candidates[:25]
