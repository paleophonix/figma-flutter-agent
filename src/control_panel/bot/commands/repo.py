"""Repository selection slash commands."""

from __future__ import annotations

import disnake
from disnake.ext import commands

from control_panel.bot.access import is_authorized
from control_panel.services.projects import (
    list_user_repo_keys,
    resolve_active_repo_key,
    resolve_repo_config,
)


def register_repo_command(bot: commands.InteractionBot) -> None:
    """Register ``/repo`` subcommands."""

    @bot.slash_command(description="Manage active publish repository")
    async def repo(inter: disnake.ApplicationCommandInteraction) -> None:
        """Repository command group root."""
        pass

    @repo.sub_command(description="List configured repositories")
    async def list_repos(inter: disnake.ApplicationCommandInteraction) -> None:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("You are not allowed to use /repo.", ephemeral=True)
            return
        keys = list_user_repo_keys(bot.settings, inter.author.id)
        if not keys:
            await inter.response.send_message("No repositories configured.", ephemeral=True)
            return
        active = await resolve_active_repo_key(bot.settings, bot.job_store, inter.author.id)
        lines = []
        for key in keys:
            marker = " (active)" if key == active else ""
            repo_cfg = resolve_repo_config(bot.settings, key)
            lines.append(f"- `{key}` → {repo_cfg.remote}{marker}")
        await inter.response.send_message("\n".join(lines), ephemeral=True)

    @repo.sub_command(description="Set active repository")
    async def use(
        inter: disnake.ApplicationCommandInteraction,
        repo_key: str,
    ) -> None:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("You are not allowed to use /repo.", ephemeral=True)
            return
        keys = list_user_repo_keys(bot.settings, inter.author.id)
        if repo_key not in keys:
            await inter.response.send_message(
                f"Unknown repo `{repo_key}`. Available: {', '.join(keys)}",
                ephemeral=True,
            )
            return
        await bot.job_store.set_active_repo_key(inter.author.id, repo_key)
        await inter.response.send_message(f"Active repository set to `{repo_key}`.", ephemeral=True)

    @repo.sub_command(description="Show active repository")
    async def status(inter: disnake.ApplicationCommandInteraction) -> None:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("You are not allowed to use /repo.", ephemeral=True)
            return
        active = await resolve_active_repo_key(bot.settings, bot.job_store, inter.author.id)
        repo_cfg = resolve_repo_config(bot.settings, active)
        await inter.response.send_message(
            (
                f"Active repo: `{active}`\n"
                f"Provider: {repo_cfg.provider.value}\n"
                f"Remote: {repo_cfg.remote}\n"
                f"Target branch: {repo_cfg.target_branch}\n"
                f"Lib root: {repo_cfg.lib_root}"
            ),
            ephemeral=True,
        )

    @use.autocomplete("repo_key")
    async def repo_key_autocomplete(
        inter: disnake.ApplicationCommandInteraction,
        user_input: str,
    ) -> list[str]:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            return []
        keys = list_user_repo_keys(bot.settings, inter.author.id)
        if user_input:
            keys = [key for key in keys if user_input.lower() in key.lower()]
        return keys[:25]
