"""Telegram channel assignment tests."""

from __future__ import annotations

import pytest

from control_panel.config.models import DiscordBotYamlConfig, TelegramChannelConfig, TelegramConfig
from control_panel.services.telegram import pick_telegram_channel_key


@pytest.mark.control_plane
def test_pick_telegram_channel_stable() -> None:
    yaml = DiscordBotYamlConfig(
        telegram=TelegramConfig(
            channels={
                "a": TelegramChannelConfig(chat_id="1", invite_link="https://t.me/a"),
                "b": TelegramChannelConfig(chat_id="2", invite_link="https://t.me/b"),
            }
        )
    )
    key = pick_telegram_channel_key(
        DiscordBotSettings_stub(yaml),
        100,
    )
    assert key in {"a", "b"}


def DiscordBotSettings_stub(yaml: DiscordBotYamlConfig):
    from pathlib import Path

    from pydantic import SecretStr

    from control_panel.config.models import DiscordBotSettings

    return DiscordBotSettings(
        yaml=yaml,
        discord_bot_token=SecretStr("x"),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr("t"),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=yaml.database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
    )
