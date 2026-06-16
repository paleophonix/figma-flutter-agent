"""Resolve per-user Flutter project directories."""

from __future__ import annotations

from pathlib import Path

from discord_bot.config.models import DiscordBotYamlConfig, UserProjectEntry


def resolve_user_entry(
    yaml_config: DiscordBotYamlConfig,
    discord_user_id: int,
) -> UserProjectEntry:
    """Return the configured project entry for a Discord user.

    Args:
        yaml_config: Bot YAML config.
        discord_user_id: Discord snowflake id.

    Returns:
        User project mapping; falls back to default key when unmapped.
    """
    users = yaml_config.projects.users
    key = str(discord_user_id)
    if key in users:
        return users[key]
    default_key = yaml_config.projects.default_user_key
    if default_key in users:
        return users[default_key]
    return UserProjectEntry(project_key=default_key, gitlab_username="")


def resolve_project_dir(
    yaml_config: DiscordBotYamlConfig,
    discord_user_id: int,
) -> Path:
    """Return the Flutter project root for a Discord user."""
    entry = resolve_user_entry(yaml_config, discord_user_id)
    root = yaml_config.projects.workspace_root.expanduser().resolve()
    return (root / entry.project_key).resolve()


def resolve_gitlab_username(
    yaml_config: DiscordBotYamlConfig,
    discord_user_id: int,
) -> str:
    """Return GitLab username for reviewers, if configured."""
    return resolve_user_entry(yaml_config, discord_user_id).gitlab_username
