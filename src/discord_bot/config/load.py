"""Load Discord bot settings from YAML and environment."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from ruamel.yaml import YAML

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.errors import FigmaFlutterError

from .models import DiscordBotSettings, DiscordBotYamlConfig


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
    discord_bot_config: str = Field(default="", alias="DISCORD_BOT_CONFIG")
    discord_bot_db_path: str = Field(default="", alias="DISCORD_BOT_DB_PATH")
    discord_bot_internal_secret: str = Field(default="", alias="DISCORD_BOT_INTERNAL_SECRET")
    discord_bot_gitlab_webhook_secret: str = Field(
        default="",
        alias="DISCORD_BOT_GITLAB_WEBHOOK_SECRET",
    )


def resolve_discord_bot_config_path(explicit: Path | None = None) -> Path:
    """Return the Discord bot YAML path.

    Args:
        explicit: Optional override path.

    Returns:
        Resolved config file.

    Raises:
        FigmaFlutterError: When no config file exists.
    """
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
) -> DiscordBotSettings:
    """Load merged Discord bot runtime settings.

    Args:
        config_path: Optional YAML path override.

    Returns:
        Frozen settings bundle for bot, runner, and webhooks.

    Raises:
        FigmaFlutterError: When config or required secrets are missing.
    """
    env = _DiscordBotEnv()
    resolved_config = resolve_discord_bot_config_path(config_path)
    yaml_config = load_discord_bot_yaml(resolved_config)

    internal_secret = env.discord_bot_internal_secret.strip()
    if internal_secret:
        yaml_config = yaml_config.model_copy(
            update={
                "internal": yaml_config.internal.model_copy(
                    update={"callback_secret": internal_secret}
                )
            }
        )
    webhook_secret = env.discord_bot_gitlab_webhook_secret.strip()
    if webhook_secret:
        yaml_config = yaml_config.model_copy(
            update={
                "internal": yaml_config.internal.model_copy(
                    update={"gitlab_webhook_secret": webhook_secret}
                )
            }
        )

    token = env.discord_bot_token.get_secret_value().strip()
    if not token:
        raise FigmaFlutterError("DISCORD_BOT_TOKEN is required")

    db_default = agent_repo_root() / ".discord-bot" / "jobs.sqlite"
    db_path = (
        Path(env.discord_bot_db_path).expanduser().resolve()
        if env.discord_bot_db_path.strip()
        else db_default
    )

    return DiscordBotSettings(
        yaml=yaml_config,
        discord_bot_token=env.discord_bot_token,
        gitlab_private_token=env.gitlab_private_token,
        config_path=resolved_config,
        db_path=db_path,
    )
