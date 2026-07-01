"""Telegram webhook registration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from control_panel.config.models import (
    DiscordBotSettings,
    DiscordBotYamlConfig,
    InternalConfig,
    TelegramChannelConfig,
    TelegramConfig,
)
from control_panel.services.telegram_webhook import (
    register_telegram_webhook,
    resolve_telegram_webhook_secret,
    should_register_telegram_webhook,
    telegram_webhook_callback_url,
)


def _settings(
    *,
    control_panel_url: str = "https://cp.example.com",
    telegram_token: str = "bot-token",
    webhook_secret: str = "wh-secret",
    callback_secret: str = "",
    channels: bool = True,
) -> DiscordBotSettings:
    yaml = DiscordBotYamlConfig(
        internal=InternalConfig(
            control_panel_url=control_panel_url,
            callback_secret=callback_secret,
        ),
        telegram=TelegramConfig(
            channels={
                "team-a": TelegramChannelConfig(chat_id="-1001"),
            }
            if channels
            else {},
        ),
    )
    return DiscordBotSettings(
        yaml=yaml,
        discord_bot_token=SecretStr(""),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(telegram_token),
        telegram_webhook_secret=SecretStr(webhook_secret),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=yaml.database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
    )


@pytest.mark.control_panel
def test_resolve_telegram_webhook_secret_prefers_env() -> None:
    settings = _settings(webhook_secret="from-env", callback_secret="from-yaml")
    assert resolve_telegram_webhook_secret(settings) == "from-env"


@pytest.mark.control_panel
def test_resolve_telegram_webhook_secret_falls_back_to_callback_secret() -> None:
    settings = _settings(webhook_secret="", callback_secret="from-yaml")
    assert resolve_telegram_webhook_secret(settings) == "from-yaml"


@pytest.mark.control_panel
def test_telegram_webhook_callback_url() -> None:
    settings = _settings(control_panel_url="https://cp.example.com/")
    assert telegram_webhook_callback_url(settings) == "https://cp.example.com/webhooks/telegram"


@pytest.mark.control_panel
def test_should_register_requires_https_and_channels() -> None:
    assert should_register_telegram_webhook(_settings()) is True
    assert (
        should_register_telegram_webhook(_settings(control_panel_url="http://127.0.0.1:8787"))
        is False
    )
    assert should_register_telegram_webhook(_settings(channels=False)) is False
    assert should_register_telegram_webhook(_settings(telegram_token="")) is False


@pytest.mark.control_panel
@pytest.mark.asyncio
async def test_register_telegram_webhook_posts_set_webhook() -> None:
    settings = _settings()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "control_panel.services.telegram_webhook.httpx.AsyncClient", return_value=mock_client
    ):
        ok = await register_telegram_webhook(settings)

    assert ok is True
    mock_client.post.assert_awaited_once()
    call_args = mock_client.post.await_args
    assert call_args.args[0] == "https://api.telegram.org/botbot-token/setWebhook"
    payload = call_args.kwargs["json"]
    assert payload["url"] == "https://cp.example.com/webhooks/telegram"
    assert payload["secret_token"] == "wh-secret"
    assert payload["allowed_updates"] == ["callback_query"]


@pytest.mark.control_panel
@pytest.mark.asyncio
async def test_register_telegram_webhook_skips_http_url() -> None:
    settings = _settings(control_panel_url="http://127.0.0.1:8787")
    with patch("control_panel.services.telegram_webhook.httpx.AsyncClient") as client_cls:
        ok = await register_telegram_webhook(settings)
    assert ok is False
    client_cls.assert_not_called()
