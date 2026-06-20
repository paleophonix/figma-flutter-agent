"""Tests for GitLab workflow orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from control_panel.config.models import (
    DiscordBotSettings,
    DiscordBotYamlConfig,
    GitLabWorkflowConfig,
)
from control_panel.db import JobOrigin, JobStatus
from control_panel.db.store import JobStore
from control_panel.gitlab_workflow.orchestrate import handle_gitlab_event


@pytest.mark.asyncio
async def test_issue_open_enqueues_generation_when_agent_assigned(tmp_path) -> None:
    store = MagicMock(spec=JobStore)
    store.find_active_generation_for_issue = AsyncMock(return_value=None)
    store.find_job_by_issue = AsyncMock(return_value=None)
    enqueue = AsyncMock()
    settings = DiscordBotSettings(
        yaml=DiscordBotYamlConfig(
            gitlab_workflow=GitLabWorkflowConfig(enabled=True, agent_username="figma-bot"),
        ),
        discord_bot_token="x",  # noqa: S106
        gitlab_private_token="y",  # noqa: S106
        github_token="z",  # noqa: S106
        telegram_bot_token="t",  # noqa: S106
        database_url="postgresql+asyncpg://x/y",
        database_mode=DiscordBotYamlConfig().database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=tmp_path / "cfg.yml",
    )
    arq_pool = MagicMock()
    payload = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "open",
            "state": "opened",
            "iid": 7,
            "url": "https://gitlab/issue/7",
            "description": "https://www.figma.com/design/abc/App?node-id=1-2",
        },
        "project": {"id": 99},
        "assignees": [{"username": "figma-bot"}],
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "control_panel.gitlab_workflow.orchestrate.enqueue_generation_from_issue",
            enqueue,
        )
        await handle_gitlab_event(
            payload,
            store=store,
            settings=settings,
            arq_pool=arq_pool,
        )

    enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_issue_close_enqueues_publish_for_gitlab_job(tmp_path) -> None:
    store = MagicMock(spec=JobStore)
    job = MagicMock()
    job.id = "job1"
    job.origin = JobOrigin.GITLAB
    job.status = JobStatus.PREVIEW_READY
    store.find_job_by_issue = AsyncMock(return_value=job)
    store.update_job = AsyncMock(return_value=job)
    settings = DiscordBotSettings(
        yaml=DiscordBotYamlConfig(gitlab_workflow=GitLabWorkflowConfig(enabled=True)),
        discord_bot_token="x",  # noqa: S106
        gitlab_private_token="y",  # noqa: S106
        github_token="z",  # noqa: S106
        telegram_bot_token="t",  # noqa: S106
        database_url="postgresql+asyncpg://x/y",
        database_mode=DiscordBotYamlConfig().database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=tmp_path / "cfg.yml",
    )
    arq_pool = MagicMock()
    arq_pool.enqueue_job = AsyncMock()
    payload = {
        "object_kind": "issue",
        "object_attributes": {
            "action": "close",
            "state": "closed",
            "iid": 7,
            "url": "https://gitlab/issue/7",
        },
        "project": {"id": 99},
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "control_panel.gitlab_workflow.orchestrate.update_job_and_publish",
            AsyncMock(return_value=job),
        )
        monkeypatch.setattr(
            "control_panel.gitlab_workflow.orchestrate.publish_issue_closed",
            AsyncMock(),
        )
        await handle_gitlab_event(
            payload,
            store=store,
            settings=settings,
            arq_pool=arq_pool,
        )

    arq_pool.enqueue_job.assert_awaited_once_with("publish_job", "job1")
