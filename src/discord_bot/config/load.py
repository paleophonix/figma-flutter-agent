"""Load Discord bot settings from YAML and environment."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from ruamel.yaml import YAML

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.errors import FigmaFlutterError

from .database_url import resolve_database_url
from .models import DatabaseMode, DiscordBotSettings, DiscordBotYamlConfig


class _DiscordBotEnv(BaseSettings):
    """Environment overrides for the Discord bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: object,
        env_settings: object,
        dotenv_settings: object,
        file_secret_settings: object,
    ) -> tuple[object, ...]:
        sources: list[object] = [init_settings, env_settings, file_secret_settings]
        if not os.getenv("PYTEST_CURRENT_TEST"):
            sources.insert(1, dotenv_settings)
        return tuple(sources)

    discord_bot_token: SecretStr = Field(default=SecretStr(""), alias="DISCORD_BOT_TOKEN")
    gitlab_private_token: SecretStr = Field(default=SecretStr(""), alias="GITLAB_PRIVATE_TOKEN")
    github_token: SecretStr = Field(default=SecretStr(""), alias="GITHUB_TOKEN")
    discord_bot_config: str = Field(default="", alias="DISCORD_BOT_CONFIG")
    figma_cp_database_url: str = Field(default="", alias="FIGMA_CP_DATABASE_URL")
    figma_cp_database_mode: str = Field(default="", alias="FIGMA_CP_DATABASE_MODE")
    figma_cp_pg_password: str = Field(default="", alias="FIGMA_CP_PG_PASSWORD")
    figma_cp_redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="FIGMA_CP_REDIS_URL")
    discord_bot_internal_secret: str = Field(default="", alias="DISCORD_BOT_INTERNAL_SECRET")
    discord_bot_gitlab_webhook_secret: str = Field(
        default="",
        alias="DISCORD_BOT_GITLAB_WEBHOOK_SECRET",
    )
    discord_bot_github_webhook_secret: str = Field(
        default="",
        alias="DISCORD_BOT_GITHUB_WEBHOOK_SECRET",
    )
    figma_cp_internal_url: str = Field(default="", alias="FIGMA_CP_INTERNAL_URL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")


def resolve_discord_bot_config_path(explicit: Path | None = None) -> Path:
    """Return the Discord bot YAML path."""
    if explicit is not None:
        resolved = explicit.expanduser().resolve()
        if not resolved.is_file():
            raise FigmaFlutterError(f"Discord bot config not found: {resolved}")
        return resolved

    env = _DiscordBotEnv()
    if env.discord_bot_config.strip():
        resolved = Path(env.discord_bot_config).expanduser().resolve()
        if not resolved.is_file():
            raise FigmaFlutterError(f"Discord bot config not found: {resolved}")
        return resolved

    root = agent_repo_root()
    local = root / ".discord-bot.yml"
    if local.is_file():
        return local
    example = root / ".discord-bot.yml.example"
    if example.is_file():
        return example
    raise FigmaFlutterError(
        "Discord bot config missing. Copy .discord-bot.yml.example to .discord-bot.yml"
    )


def load_discord_bot_yaml(config_path: Path) -> DiscordBotYamlConfig:
    """Parse Discord bot YAML into a typed config model."""
    yaml = YAML(typ="safe")
    raw = yaml.load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise FigmaFlutterError(f"Discord bot config must be a mapping: {config_path}")
    return DiscordBotYamlConfig.model_validate(raw)


def load_discord_bot_settings(
    config_path: Path | None = None,
    *,
    require_discord_token: bool = True,
) -> DiscordBotSettings:
    """Load merged Discord bot runtime settings."""
    env = _DiscordBotEnv()
    resolved_config = resolve_discord_bot_config_path(config_path)
    yaml_config = load_discord_bot_yaml(resolved_config)

    internal_secret = env.discord_bot_internal_secret.strip()
    internal_updates: dict[str, str] = {}
    if internal_secret:
        internal_updates["callback_secret"] = internal_secret
    webhook_secret = env.discord_bot_gitlab_webhook_secret.strip()
    if webhook_secret:
        internal_updates["gitlab_webhook_secret"] = webhook_secret
    github_webhook_secret = env.discord_bot_github_webhook_secret.strip()
    if github_webhook_secret:
        internal_updates["github_webhook_secret"] = github_webhook_secret
    internal_url = env.figma_cp_internal_url.strip()
    if internal_url:
        internal_updates["control_plane_url"] = internal_url
    if internal_updates:
        yaml_config = yaml_config.model_copy(
            update={
                "internal": yaml_config.internal.model_copy(update=internal_updates),
            }
        )

    token = env.discord_bot_token.get_secret_value().strip()
    if require_discord_token and not token:
        raise FigmaFlutterError("DISCORD_BOT_TOKEN is required")

    database_url = resolve_database_url(
        config=yaml_config.database,
        env_database_url=env.figma_cp_database_url,
        env_database_mode=env.figma_cp_database_mode,
        env_pg_password=env.figma_cp_pg_password,
    )
    mode_raw = env.figma_cp_database_mode.strip() or yaml_config.database.mode.value
    database_mode = DatabaseMode(mode_raw)

    return DiscordBotSettings(
        yaml=yaml_config,
        discord_bot_token=env.discord_bot_token,
        gitlab_private_token=env.gitlab_private_token,
        github_token=env.github_token,
        telegram_bot_token=SecretStr(env.telegram_bot_token.strip()),
        database_url=database_url,
        database_mode=database_mode,
        redis_url=env.figma_cp_redis_url.strip(),
        config_path=resolved_config,
    )
