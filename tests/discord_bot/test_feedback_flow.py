"""Feedback flow unit tests."""

from __future__ import annotations

import pytest

from discord_bot.config.models import DiscordBotYamlConfig, FeedbackConfig
from discord_bot.db import JobStatus, Quality
from discord_bot.services.issues import priority_labels


@pytest.mark.control_plane
def test_priority_labels_map() -> None:
    yaml = DiscordBotYamlConfig(
        feedback=FeedbackConfig(
            priority_labels={
                "total_mess": ["P1"],
                "major_wrong": ["P2"],
                "minor_wrong": ["P3"],
            }
        )
    )
    from pathlib import Path

    from pydantic import SecretStr

    from discord_bot.config.models import DiscordBotSettings

    settings = DiscordBotSettings(
        yaml=yaml,
        discord_bot_token=SecretStr("x"),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=yaml.database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
    )
    labels = priority_labels(settings, Quality.TOTAL_MESS)
    assert "P1" in labels
    assert "bug" in labels
    assert "agent-feedback::total-mess" in labels


@pytest.mark.control_plane
def test_feat_issue_labels() -> None:
    from discord_bot.services.issues import feat_issue_labels

    labels = feat_issue_labels()
    assert "feat" in labels
    assert "agent-feedback::good" in labels


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_awaiting_comment_job_lookup(job_store, tmp_path) -> None:
    job = await job_store.create_job(
        job_id="job_comment",
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        discord_user_id=42,
        discord_channel_id=99,
        project_dir=tmp_path / "proj",
    )
    await job_store.update_job(
        job.id,
        status=JobStatus.AWAITING_FEEDBACK_COMMENT.value,
        feedback_quality=Quality.MINOR_WRONG.value,
    )
    found = await job_store.find_awaiting_comment_job(
        discord_user_id=42,
        discord_channel_id=99,
    )
    assert found is not None
    assert found.id == job.id
