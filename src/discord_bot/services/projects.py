"""Resolve per-user workspace and repository targets."""

from __future__ import annotations

from pathlib import Path

from discord_bot.config.models import (
    DiscordBotSettings,
    DiscordBotYamlConfig,
    RepoConfig,
    UserProjectEntry,
)
from discord_bot.db.store import JobStore
from figma_flutter_agent.errors import FigmaFlutterError


def resolve_user_entry(
    yaml_config: DiscordBotYamlConfig,
    discord_user_id: int,
) -> UserProjectEntry:
    """Return the configured project entry for a Discord user."""
    users = yaml_config.projects.users
    key = str(discord_user_id)
    if key in users:
        return users[key]
    default_key = yaml_config.projects.default_user_key
    if default_key in users:
        return users[default_key]
    return UserProjectEntry(project_key=default_key, gitlab_username="")


async def resolve_active_repo_key(
    settings: DiscordBotSettings,
    store: JobStore,
    discord_user_id: int,
) -> str:
    """Return the active repository key for a Discord user."""
    stored = await store.get_active_repo_key(discord_user_id, default="")
    if stored:
        return stored
    entry = resolve_user_entry(settings.yaml, discord_user_id)
    if entry.active_repo_key:
        return entry.active_repo_key
    repos = settings.yaml.projects.repos
    if len(repos) == 1:
        return next(iter(repos))
    if repos:
        return next(iter(repos))
    raise FigmaFlutterError("No repository configured. Use /repo list and /repo use.")


def resolve_repo_config(settings: DiscordBotSettings, repo_key: str) -> RepoConfig:
    """Return repository config for ``repo_key``."""
    repo = settings.yaml.projects.repos.get(repo_key)
    if repo is None:
        raise FigmaFlutterError(f"Unknown repository key: {repo_key}")
    return repo


def resolve_sandbox_dir(
    settings: DiscordBotSettings,
    discord_user_id: int,
    repo_key: str,
) -> Path:
    """Return the local sandbox directory for generation."""
    entry = resolve_user_entry(settings.yaml, discord_user_id)
    root = settings.yaml.projects.workspace_root.expanduser().resolve()
    return (root / entry.project_key / repo_key).resolve()


def resolve_project_dir(
    yaml_config: DiscordBotYamlConfig,
    discord_user_id: int,
) -> Path:
    """Return the legacy Flutter project root for a Discord user."""
    entry = resolve_user_entry(yaml_config, discord_user_id)
    root = yaml_config.projects.workspace_root.expanduser().resolve()
    return (root / entry.project_key).resolve()


def resolve_gitlab_username(
    yaml_config: DiscordBotYamlConfig,
    discord_user_id: int,
) -> str:
    """Return GitLab username for reviewers, if configured."""
    return resolve_user_entry(yaml_config, discord_user_id).gitlab_username


def list_user_repo_keys(settings: DiscordBotSettings, discord_user_id: int) -> list[str]:
    """Return repository keys available to the user."""
    return sorted(settings.yaml.projects.repos)
