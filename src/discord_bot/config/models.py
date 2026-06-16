"""Pydantic models for Discord bot YAML and environment configuration."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr


class AccessMode(StrEnum):
    """Who may invoke bot commands."""

    EVERYONE = "everyone"
    ROLES = "roles"
    ALLOWLIST = "allowlist"


class PrStrategy(StrEnum):
    """How accepted jobs land in the remote repository."""

    NEW_PER_JOB = "new_per_job"
    UPDATE_OPEN = "update_open"
    PUSH_MAIN = "push_main"
    BRANCH_MR = "branch_mr"  # legacy alias for NEW_PER_JOB


class GitProvider(StrEnum):
    """Remote git hosting provider."""

    GITLAB = "gitlab"
    GITHUB = "github"


class TargetMode(StrEnum):
    """Whether the job updates an existing screen or creates a new one."""

    NEW = "new"
    EXISTING = "existing"


class CustomCodePolicy(StrEnum):
    """How publish handles manual edits outside auto-generated zones."""

    PRESERVE_CUSTOM = "preserve_custom"
    BLOCK_ON_DIRTY = "block_on_dirty"
    REPLACE_SCREEN = "replace_screen"


class DatabaseMode(StrEnum):
    """Where the control plane stores jobs and audit events."""

    BUNDLED = "bundled"
    EXTERNAL = "external"


class DatabaseConfig(BaseModel):
    """PostgreSQL connection policy.

    Use ``bundled`` with ``docker compose --profile bundled-db`` to run Postgres in
    Docker (data on host under ``FIGMA_CP_PGDATA``). Use ``external`` to point at a
    managed or VPS-hosted Postgres; set ``database.url`` or ``FIGMA_CP_DATABASE_URL``.
    """

    mode: DatabaseMode = DatabaseMode.BUNDLED
    url: str = ""
    bundled_host: str = "postgres"
    bundled_port: int = Field(default=5432, ge=1, le=65535)
    user: str = "figma_cp"
    database: str = "figma_control_plane"


class DiscordAccessConfig(BaseModel):
    """Slash-command access policy."""

    mode: AccessMode = AccessMode.EVERYONE
    allowed_role_ids: list[int] = Field(default_factory=list)
    allowed_user_ids: list[int] = Field(default_factory=list)


class DiscordSectionConfig(BaseModel):
    """Discord application settings."""

    guild_ids: list[int] = Field(default_factory=list)
    changelog_channel_id: int | None = None
    access: DiscordAccessConfig = Field(default_factory=DiscordAccessConfig)


class UserProjectEntry(BaseModel):
    """Per-Discord-user Flutter workspace mapping."""

    project_key: str
    gitlab_username: str = ""
    active_repo_key: str = ""


class RepoConfig(BaseModel):
    """Remote repository target for publish."""

    provider: GitProvider = GitProvider.GITLAB
    remote: str = ""
    target_branch: str = "main"
    lib_root: str = "lib"
    pubspec_path: str = "pubspec.yaml"
    bot_push: bool = True
    gitlab_project_id: str = ""
    github_repo: str = ""


class PublishConfig(BaseModel):
    """Publish and PR policies."""

    custom_code_policy: CustomCodePolicy = CustomCodePolicy.PRESERVE_CUSTOM
    pr_strategy: PrStrategy = PrStrategy.UPDATE_OPEN
    source_branch_template: str = "figma/{feature_slug}"
    assignee_username: str = ""
    boss_reviewer_username: str = ""


class ProjectsConfig(BaseModel):
    """Flutter project provisioning under a shared workspace root."""

    workspace_root: Path = Path("/workspace")
    default_user_key: str = "default"
    users: dict[str, UserProjectEntry] = Field(default_factory=dict)
    repos: dict[str, RepoConfig] = Field(default_factory=dict)


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


class TelegramChannelConfig(BaseModel):
    """Pre-created Telegram channel assigned to users."""

    chat_id: str
    invite_link: str = ""


class TelegramConfig(BaseModel):
    """Telegram Bot API notification settings."""

    channels: dict[str, TelegramChannelConfig] = Field(default_factory=dict)


class ArtifactsConfig(BaseModel):
    """Remote repository for generation artifact bundles."""

    remote: str = ""


class FeedbackConfig(BaseModel):
    """Feedback issue label mapping by quality rating."""

    priority_labels: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "total_mess": ["priority::high", "P1"],
            "major_wrong": ["priority::medium", "P2"],
            "minor_wrong": ["priority::low", "P3"],
        }
    )


class InternalConfig(BaseModel):
    """Webhook server bind and shared secrets."""

    callback_secret: str = ""
    webhook_bind: str = "127.0.0.1:8787"
    gitlab_webhook_secret: str = ""
    github_webhook_secret: str = ""
    control_plane_url: str = "http://127.0.0.1:8787"


class DiscordBotYamlConfig(BaseModel):
    """Root document for ``.discord-bot.yml``."""

    discord: DiscordSectionConfig = Field(default_factory=DiscordSectionConfig)
    projects: ProjectsConfig = Field(default_factory=ProjectsConfig)
    gitlab: GitLabConfig = Field(default_factory=GitLabConfig)
    preview: PreviewConfig = Field(default_factory=PreviewConfig)
    internal: InternalConfig = Field(default_factory=InternalConfig)
    publish: PublishConfig = Field(default_factory=PublishConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class DiscordBotSettings(BaseModel):
    """Runtime settings merged from YAML and environment."""

    model_config = {"frozen": True}

    yaml: DiscordBotYamlConfig
    discord_bot_token: SecretStr
    gitlab_private_token: SecretStr
    github_token: SecretStr
    telegram_bot_token: SecretStr
    database_url: str
    database_mode: DatabaseMode
    redis_url: str
    config_path: Path
    agent_config_path: Path | None = None
