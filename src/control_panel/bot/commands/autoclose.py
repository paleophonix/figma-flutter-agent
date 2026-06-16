"""User autoclose policy slash command."""

from __future__ import annotations

import disnake
from disnake.ext import commands

from control_panel.bot.access import is_authorized
from control_panel.db import AutocloseMode
from control_panel.services.projects import list_user_repo_keys, resolve_active_repo_key


def register_autoclose_command(bot: commands.InteractionBot) -> None:
    """Register ``/autoclose`` toggle."""

    @bot.slash_command(description="Кто закрывает тикет: разработчик или ты")
    async def autoclose(inter: disnake.ApplicationCommandInteraction) -> None:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("Нет доступа.", ephemeral=True)
            return

        current = await bot.job_store.get_autoclose_mode(inter.author.id)
        new_mode = (
            AutocloseMode.USER.value
            if current == AutocloseMode.DEVELOPER.value
            else AutocloseMode.DEVELOPER.value
        )
        default_repo = "default"
        keys = list_user_repo_keys(bot.settings, inter.author.id)
        if keys:
            default_repo = await resolve_active_repo_key(bot.settings, bot.job_store, inter.author.id)
        await bot.job_store.set_autoclose_mode(
            inter.author.id,
            new_mode,
            default_repo_key=default_repo,
        )
        label = (
            "ты (кнопка в Discord/Telegram)"
            if new_mode == AutocloseMode.USER.value
            else "разработчик в трекере"
        )
        await inter.response.send_message(
            f"Закрытие тикета: **{label}**.",
            ephemeral=True,
        )
