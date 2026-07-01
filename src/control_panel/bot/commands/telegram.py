"""Telegram subscription slash command."""

from __future__ import annotations

import disnake
from disnake.ext import commands

from control_panel.bot.access import is_authorized
from control_panel.services.projects import list_user_repo_keys, resolve_active_repo_key
from control_panel.services.telegram import TelegramNotifier, pick_telegram_channel_key


def register_telegram_command(bot: commands.InteractionBot) -> None:
    """Register ``/telegram`` toggle."""

    @bot.slash_command(description="Подписка на уведомления в Telegram")
    async def telegram(inter: disnake.ApplicationCommandInteraction) -> None:
        from control_panel.bot.app import DiscordControlBot

        if not isinstance(bot, DiscordControlBot):
            await inter.response.send_message("Bot misconfigured.", ephemeral=True)
            return
        if not is_authorized(inter, bot.settings.yaml):
            await inter.response.send_message("Нет доступа.", ephemeral=True)
            return
        notifier = TelegramNotifier(bot.settings)
        if not notifier.enabled:
            await inter.response.send_message("TELEGRAM_BOT_TOKEN не настроен.", ephemeral=True)
            return
        channels = bot.settings.yaml.telegram.channels
        if not channels:
            await inter.response.send_message(
                "Пул каналов пуст (telegram.channels).", ephemeral=True
            )
            return

        prefs = await bot.job_store.get_user_preferences(inter.author.id)
        enabled = not bool(prefs and prefs.telegram_enabled)
        channel_key = pick_telegram_channel_key(bot.settings, inter.author.id)
        if channel_key is None:
            await inter.response.send_message("Не удалось назначить канал.", ephemeral=True)
            return
        default_repo = ""
        keys = list_user_repo_keys(bot.settings, inter.author.id)
        if keys:
            default_repo = await resolve_active_repo_key(
                bot.settings, bot.job_store, inter.author.id
            )
        await bot.job_store.set_telegram_prefs(
            inter.author.id,
            enabled=enabled,
            channel_key=channel_key if enabled else None,
            default_repo_key=default_repo or "default",
        )
        invite = channels[channel_key].invite_link
        if enabled:
            lines = [
                "Telegram-уведомления **включены**.",
                f"Канал: `{channel_key}`",
            ]
            if invite:
                lines.append(f"Ссылка: {invite}")
            await inter.response.send_message("\n".join(lines), ephemeral=True)
            return
        await inter.response.send_message("Telegram-уведомления **выключены**.", ephemeral=True)
