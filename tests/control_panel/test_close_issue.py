"""Issue close Discord reply tests."""

from __future__ import annotations

import pytest

from control_panel.db.enums import IssueKind, JobOrigin, JobStatus
from control_panel.db.store import GenerationJob
from control_panel.services.issues import IssueService


def _job(**kwargs) -> GenerationJob:
    base = dict(
        id="job1",
        run_id=None,
        figma_url="https://figma.test",
        discord_user_id=1,
        discord_channel_id=2,
        discord_message_id=None,
        review_message_id=None,
        project_dir="/tmp",
        feature_slug="bank_home",
        status=JobStatus.FEEDBACK_ISSUE_CREATED,
        repo_key="mobile",
        git_provider="gitlab",
        target_mode=None,
        target_file_path=None,
        fixed_preview_url=None,
        adaptive_preview_url=None,
        preview_token_hash=None,
        artifact_zip_path=None,
        artifact_repo_commit_url=None,
        gitlab_app_project_id="7",
        gitlab_issue_iid=3,
        gitlab_issue_url="https://gitlab/issue/3",
        gitlab_mr_iid=None,
        gitlab_mr_url=None,
        gitlab_source_branch=None,
        publish_branch=None,
        publish_pr_url=None,
        publish_pr_number=None,
        feedback_quality=None,
        feedback_comment="broken layout",
        feedback_comment_message_id=999,
        issue_provider="gitlab",
        issue_project_ref="7",
        issue_number=3,
        issue_url="https://gitlab/issue/3",
        issue_kind=None,
        origin=JobOrigin.DISCORD,
        principal=None,
        error_message=None,
        created_at="",
        updated_at="",
    )
    base.update(kwargs)
    return GenerationJob(**base)


@pytest.mark.control_panel
@pytest.mark.asyncio
async def test_fetch_last_issue_comment_gitlab_skips_system(monkeypatch) -> None:
    job = _job()

    async def _notes(**_kwargs):
        return [
            {"body": "artifact", "system": False},
            {"body": "closed", "system": True},
            {"body": "fixed in main", "system": False},
        ]

    class _FakeGitLab:
        async def list_issue_notes(self, **_kwargs):
            return await _notes()

    service = IssueService.__new__(IssueService)
    monkeypatch.setattr(service, "_gitlab", lambda: _FakeGitLab())
    result = await IssueService.fetch_last_issue_comment(service, job)
    assert result == "fixed in main"


@pytest.mark.control_panel
@pytest.mark.asyncio
async def test_deliver_feat_close_posts_changelog(monkeypatch) -> None:
    from pathlib import Path
    from unittest.mock import AsyncMock, MagicMock

    from pydantic import SecretStr

    from control_panel.config.models import (
        DiscordBotSettings,
        DiscordBotYamlConfig,
        DiscordSectionConfig,
    )
    from control_panel.services.close_notify import deliver_issue_closed_notice

    sent: list[str] = []

    class _Channel:
        async def send(self, *, content: str) -> None:
            sent.append(content)

    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=_Channel())

    yaml = DiscordBotYamlConfig(
        discord=DiscordSectionConfig(changelog_channel_id=555),
    )
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
    store = AsyncMock()
    store.is_telegram_enabled = AsyncMock(return_value=False)

    job = _job(issue_kind=IssueKind.FEAT)

    async def _last_comment(_self, _job):
        return "Shipped in v1.2"

    monkeypatch.setattr(
        IssueService,
        "fetch_last_issue_comment",
        _last_comment,
    )

    await deliver_issue_closed_notice(
        bot=bot,
        settings=settings,
        store=store,
        job=job,
        issue_url="https://gitlab/issue/3",
    )
    assert sent
    assert "Shipped in v1.2" in sent[0]
    assert "bank_home" in sent[0]
