"""Telegram Bot API webhook registration."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from control_panel.config import DiscordBotSettings

TELEGRAM_WEBHOOK_PATH = "/webhooks/telegram"
TELEGRAM_ALLOWED_UPDATES = ("callback_query",)


def resolve_telegram_webhook_secret(settings: DiscordBotSettings) -> str:
    """Return webhook secret token for Telegram ``setWebhook`` and inbound auth."""
    explicit = settings.telegram_webhook_secret.get_secret_value().strip()
    if explicit:
        return explicit
    return settings.yaml.internal.callback_secret.strip()


def telegram_webhook_callback_url(settings: DiscordBotSettings) -> str:
    """Build the public callback URL registered with Telegram."""
    base = settings.yaml.internal.control_panel_url.rstrip("/")
    return f"{base}{TELEGRAM_WEBHOOK_PATH}"


def should_register_telegram_webhook(settings: DiscordBotSettings) -> bool:
    """Return whether startup should call Telegram ``setWebhook``."""
    token = settings.telegram_bot_token.get_secret_value().strip()
    if not token:
        return False
    if not settings.yaml.telegram.channels:
        return False
    url = telegram_webhook_callback_url(settings)
    if not url.startswith("https://"):
        return False
    return bool(resolve_telegram_webhook_secret(settings))


async def register_telegram_webhook(settings: DiscordBotSettings) -> bool:
    """Register callback-query webhook with Telegram Bot API."""
    token = settings.telegram_bot_token.get_secret_value().strip()
    if not token:
        return False
    if not settings.yaml.telegram.channels:
        logger.info("Telegram webhook skipped: telegram.channels is empty")
        return False

    callback_url = telegram_webhook_callback_url(settings)
    if not callback_url.startswith("https://"):
        logger.warning(
            "Telegram webhook skipped: internal.control_panel_url must be HTTPS (got {})",
            callback_url,
        )
        return False

    secret = resolve_telegram_webhook_secret(settings)
    if not secret:
        logger.warning(
            "Telegram webhook skipped: set TELEGRAM_WEBHOOK_SECRET or internal.callback_secret",
        )
        return False

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload: dict[str, Any] = {
        "url": callback_url,
        "secret_token": secret,
        "allowed_updates": list(TELEGRAM_ALLOWED_UPDATES),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(api_url, json=payload)
        if response.status_code >= 400:
            logger.error("Telegram setWebhook HTTP {}: {}", response.status_code, response.text)
            return False
        data = response.json()
    if not data.get("ok"):
        logger.error("Telegram setWebhook rejected: {}", data.get("description", data))
        return False
    logger.info("Telegram webhook registered at {}", callback_url)
    return True
