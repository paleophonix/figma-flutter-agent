"""Pydantic models for Discord bot YAML and environment configuration."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class AccessMode(StrEnum):
    """Who may invoke bot commands."""

    EVERYONE = "everyone"
    ROLES = "roles"
    ALLOWLIST = "allowlist"


class PrStrategy(StrEnum):
    """How accepted jobs land in GitLab."""

    BRANCH_MR = "branch_mr"
    PUSH_MAIN = "push_main"


class DiscordAccessConfig(BaseModel):
    """Slash-command access policy."""

    mode: AccessMode = AccessMode.EVERYONE
    allowed_role_ids: list[int] = Field(default_factory=list)
    allowed_user_ids: list[int] = Field(default_factory=list)


class DiscordSectionConfig(BaseModel):
    """Discord application settings."""

    guild_ids: list[int] = Field(default_factory=list)
    access: DiscordAccessConfig = Field(default_factory=DiscordAccessConfig)


class UserProjectEntry(BaseModel):
    """Per-Discord-user Flutter workspace mapping."""

    project_key: str
    gitlab_username: str = ""


class ProjectsConfig(BaseModel):
    """Flutter project provisioning under a shared workspace root."""

    workspace_root: Path = Path("/srv/figma-agent/projects")
    default_user_key: str = "default"
    users: dict[str, UserProjectEntry] = Field(default_factory=dict)


class GitLabConfig(BaseModel):
    """GitLab API targets for app code and artifacts."""

    base_url: str = "https://gitlab.com"
    app_project_id: str = ""
    artifacts_project_id: str = ""
    target_branch: str = "main"
    pr_strategy: PrStrategy = PrStrategy.BRANCH_MR
    source_branch_template: str = "generate/{job_id}"
    assignee_username: str = ""
    boss_reviewer_username: str = ""


class PreviewConfig(BaseModel):
    """Local companion preview settings."""

    companion_scheme: str = "figma-flutter"
    token_ttl_sec: int = Field(default=3600, ge=60, le=86400)
    static_port_base: int = Field(default=17357, ge=1024, le=65535)
    adaptive_port_base: int = Field(default=17358, ge=1024, le=65535)


class InternalConfig(BaseModel):
    """Webhook server bind and shared secrets."""

    callback_secret: str = ""
    webhook_bind: str = "127.0.0.1:8787"
    gitlab_webhook_secret: str = ""


class DiscordBotYamlConfig(BaseModel):
    """Root document for ``.discord-bot.yml``."""

    discord: DiscordSectionConfig = Field(default_factory=DiscordSectionConfig)
    projects: ProjectsConfig = Field(default_factory=ProjectsConfig)
    gitlab: GitLabConfig = Field(default_factory=GitLabConfig)
    preview: PreviewConfig = Field(default_factory=PreviewConfig)
    internal: InternalConfig = Field(default_factory=InternalConfig)


class DiscordBotSettings(BaseModel):
    """Runtime settings merged from YAML and environment."""

    model_config = {"frozen": True}

    yaml: DiscordBotYamlConfig
    discord_bot_token: SecretStr
    gitlab_private_token: SecretStr
    config_path: Path
    db_path: Path
    agent_config_path: Path | None = None
