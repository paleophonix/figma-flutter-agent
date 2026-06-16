"""Lifespan composition-root tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from control_panel.api.app import lifespan
from control_panel.config.models import (
    DiscordBotSettings,
    DiscordBotYamlConfig,
    DiscordSectionConfig,
    ProjectsConfig,
)


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_lifespan_skips_bot_when_discord_disabled(tmp_path: Path) -> None:
    """Pattern A: bot task is not started when discord.enabled=false."""
    yaml = DiscordBotYamlConfig(
        discord=DiscordSectionConfig(enabled=False),
        projects=ProjectsConfig(workspace_root=tmp_path),
    )
    settings = DiscordBotSettings(
        yaml=yaml,
        discord_bot_token=SecretStr("token"),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=yaml.database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=tmp_path / "cfg.yml",
    )

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_conn.run_sync = AsyncMock()

    @asynccontextmanager
    async def mock_begin():
        yield mock_conn

    mock_engine.begin = mock_begin
    mock_engine.dispose = AsyncMock()

    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with patch("control_panel.api.app.load_discord_bot_settings", return_value=settings):
        with patch("control_panel.api.app.create_engine", return_value=mock_engine):
            with patch("control_panel.api.app.create_pool", new=AsyncMock(return_value=mock_pool)):
                with patch("control_panel.api.app.Redis") as redis_cls:
                    redis_cls.from_url.return_value = mock_redis
                    with patch("control_panel.api.app.DiscordControlBot") as bot_cls:
                        app = FastAPI()
                        async with lifespan(app):
                            assert app.state.bot is None
                        bot_cls.assert_not_called()
