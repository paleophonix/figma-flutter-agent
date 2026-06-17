"""Load Discord bot settings from YAML and environment."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from ruamel.yaml import YAML

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.errors import FigmaFlutterError

from .database_url import resolve_database_url
from .models import ApiClientConfig, DatabaseMode, DiscordBotSettings, DiscordBotYamlConfig, RepairConfig


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
    control_panel_api_enabled: bool = Field(default=False, alias="CONTROL_PANEL_API_ENABLED")
    control_panel_api_clients: str = Field(default="", alias="CONTROL_PANEL_API_CLIENTS")
    control_panel_rate_limit_jobs_per_min: int = Field(
        default=10,
        alias="CONTROL_PANEL_RATE_LIMIT_JOBS_PER_MIN",
    )
    control_panel_rate_limit_jobs_global_per_min: int = Field(
        default=50,
        alias="CONTROL_PANEL_RATE_LIMIT_JOBS_GLOBAL_PER_MIN",
    )
    control_panel_metrics_token: SecretStr = Field(
        default=SecretStr(""),
        alias="CONTROL_PANEL_METRICS_TOKEN",
    )
    posthog_api_key: SecretStr = Field(default=SecretStr(""), alias="POSTHOG_API_KEY")
    posthog_host: str = Field(default="https://us.i.posthog.com", alias="POSTHOG_HOST")
    posthog_capture_max_attempts: int = Field(default=3, alias="POSTHOG_CAPTURE_MAX_ATTEMPTS")
    posthog_capture_timeout_sec: float = Field(default=8.0, alias="POSTHOG_CAPTURE_TIMEOUT_SEC")
    posthog_capture_retry_base_sec: float = Field(
        default=0.75,
        alias="POSTHOG_CAPTURE_RETRY_BASE_SEC",
    )
    opencode_server_password: SecretStr = Field(
        default=SecretStr(""),
        alias="OPENCODE_SERVER_PASSWORD",
    )
    repair_opencode_url: str = Field(default="", alias="REPAIR_OPENCODE_URL")
    repair_context_model: str = Field(default="", alias="REPAIR_CONTEXT_MODEL")
    repair_diagnose_model: str = Field(default="", alias="REPAIR_DIAGNOSE_MODEL")
    repair_consilium_model: str = Field(default="", alias="REPAIR_CONSILIUM_MODEL")
    repair_plan_model: str = Field(default="", alias="REPAIR_PLAN_MODEL")
    repair_build_model: str = Field(default="", alias="REPAIR_BUILD_MODEL")
    repair_review_model: str = Field(default="", alias="REPAIR_REVIEW_MODEL")


def _parse_api_clients(raw: str) -> tuple[ApiClientConfig, ...]:
    """Parse API client definitions from JSON env."""
    text = raw.strip()
    if not text:
        return ()
    data = json.loads(text)
    if not isinstance(data, list):
        raise FigmaFlutterError("CONTROL_PANEL_API_CLIENTS must be a JSON array")
    return tuple(ApiClientConfig.model_validate(item) for item in data)


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


def _merge_repair_env(yaml_config: DiscordBotYamlConfig, env: _DiscordBotEnv) -> DiscordBotYamlConfig:
    """Apply repair-related environment overrides."""
    repair = yaml_config.repair
    models = repair.models.model_copy(
        update={
            k: v
            for k, v in {
                "context": env.repair_context_model.strip(),
                "diagnose": env.repair_diagnose_model.strip(),
                "consilium": env.repair_consilium_model.strip(),
                "plan": env.repair_plan_model.strip(),
                "build": env.repair_build_model.strip(),
                "review": env.repair_review_model.strip(),
            }.items()
            if v
        }
    )
    opencode_url = env.repair_opencode_url.strip()
    agent_path = repair.agent_repo_path
    if not str(agent_path).strip():
        agent_path = agent_repo_root()
    updates: dict[str, object] = {"models": models, "agent_repo_path": agent_path}
    if opencode_url:
        updates["opencode_base_url"] = opencode_url
    merged_repair = repair.model_copy(update=updates)
    return yaml_config.model_copy(update={"repair": merged_repair})


def load_discord_bot_settings(
    config_path: Path | None = None,
    *,
    require_discord_token: bool = True,
) -> DiscordBotSettings:
    """Load merged Discord bot runtime settings."""
    env = _DiscordBotEnv()
    resolved_config = resolve_discord_bot_config_path(config_path)
    yaml_config = load_discord_bot_yaml(resolved_config)
    yaml_config = _merge_repair_env(yaml_config, env)

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
        api_enabled=env.control_panel_api_enabled,
        api_clients=_parse_api_clients(env.control_panel_api_clients),
        api_rate_limit_jobs_per_min=env.control_panel_rate_limit_jobs_per_min,
        api_rate_limit_jobs_global_per_min=env.control_panel_rate_limit_jobs_global_per_min,
        metrics_token=env.control_panel_metrics_token,
        telegram_webhook_secret=SecretStr(env.telegram_webhook_secret.strip()),
        opencode_server_password=env.opencode_server_password,
        posthog_api_key=env.posthog_api_key,
        posthog_host=env.posthog_host.strip() or "https://us.i.posthog.com",
        posthog_capture_max_attempts=env.posthog_capture_max_attempts,
        posthog_capture_timeout_sec=env.posthog_capture_timeout_sec,
        posthog_capture_retry_base_sec=env.posthog_capture_retry_base_sec,
    )
