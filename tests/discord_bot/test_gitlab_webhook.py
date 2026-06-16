"""GitLab webhook routing tests."""

from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from discord_bot.config.models import DiscordBotSettings, DiscordBotYamlConfig, InternalConfig
from discord_bot.db import JobStatus, JobStore
from discord_bot.webhooks.app import create_webhook_app


class _StubBot:
    def get_channel(self, channel_id: int) -> None:
        return None


@pytest.mark.discord
@pytest.mark.asyncio
async def test_gitlab_issue_closed_webhook(tmp_path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite")
    await store.create_job(
        job_id="job1",
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        discord_user_id=42,
        discord_channel_id=99,
        project_dir=tmp_path / "proj",
        gitlab_app_project_id="7",
    )
    await store.update_job(
        "job1",
        status=JobStatus.FEEDBACK_ISSUE_CREATED.value,
        gitlab_issue_iid=3,
    )
    settings = DiscordBotSettings(
        yaml=DiscordBotYamlConfig(internal=InternalConfig(gitlab_webhook_secret="secret")),
        discord_bot_token="x",  # noqa: S106
        gitlab_private_token="y",  # noqa: S106
        config_path=tmp_path / "cfg.yml",
        db_path=tmp_path / "jobs.sqlite",
    )
    app = create_webhook_app(settings=settings, store=store, bot=_StubBot())
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    payload = {
        "object_kind": "issue",
        "project": {"id": 7},
        "object_attributes": {"iid": 3, "state": "closed", "url": "https://gitlab/issue/3"},
    }
    response = await client.post(
        "/webhooks/gitlab",
        data=json.dumps(payload),
        headers={"X-Gitlab-Token": "secret", "Content-Type": "application/json"},
    )
    assert response.status == 200
    await asyncio.sleep(0.05)
    await client.close()
    job = await store.get_job("job1")
    assert job is not None
    assert job.status == JobStatus.ISSUE_CLOSED
