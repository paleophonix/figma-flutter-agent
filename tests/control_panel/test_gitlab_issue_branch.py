"""Tests for GitLab issue branch naming."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from control_panel.config.models import (
    DiscordBotSettings,
    DiscordBotYamlConfig,
    GitLabConfig,
    GitLabWorkflowConfig,
)
from unittest.mock import MagicMock

from control_panel.db.store import GenerationJob
from control_panel.gitlab_workflow.branch import (
    issue_branch_name,
    resolve_issue_branch_name,
    resolve_issue_branch_template,
)


def _settings(*, gitlab_template: str = "", workflow_template: str = "figma/issue-{issue_iid}") -> DiscordBotSettings:
    return DiscordBotSettings(
        yaml=DiscordBotYamlConfig(
            gitlab=GitLabConfig(issue_branch_template=gitlab_template),
            gitlab_workflow=GitLabWorkflowConfig(issue_branch_template=workflow_template),
        ),
        discord_bot_token=SecretStr("x"),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=DiscordBotYamlConfig().database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
    )


def test_issue_branch_name_uses_workflow_template() -> None:
    settings = _settings()
    assert issue_branch_name(settings, issue_iid=4, feature_slug="login_version_1", job_id="abc") == "figma/issue-4"


def test_gitlab_section_overrides_workflow_template() -> None:
    settings = _settings(gitlab_template="feature/{feature_slug}")
    assert resolve_issue_branch_template(settings) == "feature/{feature_slug}"
    assert issue_branch_name(settings, issue_iid=1, feature_slug="login_version_1", job_id="abc") == "feature/login_version_1"


def test_resolve_issue_branch_name_from_job() -> None:
    settings = _settings(workflow_template="figma/{feature_slug}")
    job = MagicMock(spec=GenerationJob)
    job.id = "job123"
    job.gitlab_issue_iid = 9
    job.issue_number = None
    job.feature_slug = "login_version_1"
    job.publish_branch = None
    job.gitlab_source_branch = None
    assert resolve_issue_branch_name(settings, job) == "figma/login_version_1"
