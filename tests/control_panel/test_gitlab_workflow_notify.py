"""Tests for GitLab workflow issue comments."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from control_panel.config.models import DiscordBotSettings, DiscordBotYamlConfig
from control_panel.db.store import GenerationJob
from control_panel.gitlab_workflow.notify import post_generation_started_comment


def _settings() -> DiscordBotSettings:
    return DiscordBotSettings(
        yaml=DiscordBotYamlConfig(),
        discord_bot_token=SecretStr("x"),
        gitlab_private_token=SecretStr("gitlab-token"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=DiscordBotYamlConfig().database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
    )


@pytest.mark.asyncio
async def test_post_generation_started_comment_posts_branch_and_frame() -> None:
    job = MagicMock(spec=GenerationJob)
    job.gitlab_app_project_id = "83548281"
    job.issue_project_ref = None
    job.gitlab_issue_iid = 12
    job.issue_number = None
    job.id = "job-12"
    job.feature_slug = None
    job.publish_branch = "figma/issue-12"
    job.gitlab_source_branch = None
    job.figma_url = "https://www.figma.com/design/abc/App?node-id=1-2"

    mock_client = MagicMock()
    mock_client.create_issue_note = AsyncMock()

    with patch(
        "control_panel.gitlab_workflow.notify._gitlab",
        return_value=mock_client,
    ):
        await post_generation_started_comment(_settings(), job)

    mock_client.create_issue_note.assert_awaited_once()
    kwargs = mock_client.create_issue_note.await_args.kwargs
    assert kwargs["project_id"] == "83548281"
    assert kwargs["issue_iid"] == 12
    assert "**Generation started**" in kwargs["body"]
    assert "`figma/issue-12`" in kwargs["body"]
    assert job.figma_url in kwargs["body"]
