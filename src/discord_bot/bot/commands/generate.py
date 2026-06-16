"""Slash command handlers."""

from __future__ import annotations

import uuid

import disnake
from disnake.ext import commands

from discord_bot.bot.access import is_authorized
from discord_bot.config.models import TargetMode
from discord_bot.db import JobStatus
from discord_bot.publish.scan import list_screen_candidates
from discord_bot.services.projects import (
    resolve_active_repo_key,
    resolve_repo_config,
    resolve_sandbox_dir,
)
from figma_flutter_agent.errors import FigmaUrlError


def register_generate_command(bot: commands.InteractionBot) -> None:
    """Register the ``/generate`` slash command on ``bot``."""

    @bot.slash_command(description="Generate Flutter layout from a Figma frame URL")
    async def generate(
        inter: disnake.ApplicationCommandInteraction,
        figma_url: str,
        mode: str = commands.Param(choices=["new", "existing"]),
        target_file: str | None = None,
    ) -> None:
        from discord_bot.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("You are not allowed to run /generate.", ephemeral=True)
            return
        from figma_flutter_agent.figma.url import parse_figma_url

        try:
            parse_figma_url(figma_url.strip())
        except FigmaUrlError as exc:
            await inter.response.send_message(f"Invalid Figma URL: {exc}", ephemeral=True)
            return

        await inter.response.defer()
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

        job_id = uuid.uuid4().hex
        project_dir = resolve_sandbox_dir(bot.settings, inter.author.id, repo_key)
        gitlab_project_id = repo_cfg.gitlab_project_id or bot.settings.yaml.gitlab.app_project_id
        await bot.job_store.create_job(
            job_id=job_id,
            figma_url=figma_url.strip(),
            discord_user_id=inter.author.id,
            discord_channel_id=inter.channel_id,
            project_dir=project_dir,
            gitlab_app_project_id=gitlab_project_id,
            repo_key=repo_key,
            git_provider=repo_cfg.provider.value,
            target_mode=mode,
            target_file_path=resolved_target,
        )
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
        await bot.job_store.append_audit(
            job_id=job_id,
            discord_user_id=inter.author.id,
            action="generate_requested",
            payload={"mode": mode, "target_file": resolved_target, "repo_key": repo_key},
        )
        pool = bot.arq_pool
        if pool is not None:
            await pool.enqueue_job("run_generation_job", job_id)
        else:
            await bot.job_store.update_job(
                job_id,
                status=JobStatus.FAILED.value,
                error_message="ARQ pool unavailable; cannot enqueue generation job.",
            )

    @generate.autocomplete("target_file")
    async def target_file_autocomplete(
        inter: disnake.ApplicationCommandInteraction,
        user_input: str,
    ) -> list[str]:
        from discord_bot.bot.app import DiscordControlBot

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
