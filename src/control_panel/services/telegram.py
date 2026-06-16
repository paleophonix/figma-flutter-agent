"""Telegram Bot API notifications."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db import AutocloseMode
from control_panel.db.store import GenerationJob, JobStore


class TelegramNotifier:
    """Send Telegram messages via Bot API."""

    def __init__(self, settings: DiscordBotSettings) -> None:
        self._settings = settings
        self._token = settings.telegram_bot_token.get_secret_value().strip()

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def resolve_chat_id(self, store: JobStore, discord_user_id: int) -> str | None:
        """Return Telegram chat id for a subscribed user."""
        if not await store.is_telegram_enabled(discord_user_id):
            return None
        channel_key = await store.get_telegram_channel_key(discord_user_id)
        if not channel_key:
            return None
        channel = self._settings.yaml.telegram.channels.get(channel_key)
        if channel is None:
            return None
        return channel.chat_id

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        """Post a message to a Telegram chat."""
        if not self.enabled:
            return
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                logger.warning("Telegram sendMessage failed: {}", response.text)

    def _close_keyboard(self, job_id: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "Закрыть тикет", "callback_data": f"close_issue:{job_id}"}],
            ]
        }

    async def notify_issue_created(
        self,
        store: JobStore,
        job: GenerationJob,
        *,
        issue_url: str,
        autoclose_mode: str,
    ) -> None:
        """Notify user's Telegram channel that a feedback issue was created."""
        chat_id = await self.resolve_chat_id(store, job.discord_user_id)
        if not chat_id:
            return
        text = (
            f"Создан тикет по генерации `{job.id}`\n"
            f"{issue_url}\n"
            f"Качество: {job.feedback_quality.value if job.feedback_quality else '-'}"
        )
        markup = (
            self._close_keyboard(job.id) if autoclose_mode == AutocloseMode.USER.value else None
        )
        await self.send_message(chat_id=chat_id, text=text, reply_markup=markup)

    async def notify_issue_closed(
        self,
        store: JobStore,
        job: GenerationJob,
        *,
        issue_url: str,
    ) -> None:
        """Notify user's Telegram channel that a feedback issue was closed."""
        chat_id = await self.resolve_chat_id(store, job.discord_user_id)
        if not chat_id:
            return
        await self.send_message(
            chat_id=chat_id,
            text=f"Тикет закрыт по job `{job.id}`\n{issue_url}",
        )


def pick_telegram_channel_key(settings: DiscordBotSettings, discord_user_id: int) -> str | None:
    """Assign a channel from the pool using stable hashing."""
    channels = settings.yaml.telegram.channels
    if not channels:
        return None
    keys = sorted(channels)
    index = discord_user_id % len(keys)
    return keys[index]
