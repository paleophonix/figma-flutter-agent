"""Issue service helpers tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from control_panel.config.models import (
    DiscordBotSettings,
    DiscordBotYamlConfig,
    GitLabConfig,
    GitProvider,
    RepoConfig,
)
from control_panel.services.issues import artifacts_provider, resolve_app_project_ref


def _settings() -> DiscordBotSettings:
    return DiscordBotSettings(
        yaml=DiscordBotYamlConfig(gitlab=GitLabConfig(app_project_id="123")),
        discord_bot_token=SecretStr("x"),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=DiscordBotYamlConfig().database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
    )


@pytest.mark.control_plane
def test_artifacts_provider_github() -> None:
    assert artifacts_provider("org/artifacts") == GitProvider.GITHUB


@pytest.mark.control_plane
def test_artifacts_provider_gitlab_numeric() -> None:
    assert artifacts_provider("456") == GitProvider.GITLAB


@pytest.mark.control_plane
def test_resolve_app_project_ref_github() -> None:
    settings = _settings()
    repo = RepoConfig(provider=GitProvider.GITHUB, github_repo="org/app")
    assert resolve_app_project_ref(settings, repo) == "org/app"
