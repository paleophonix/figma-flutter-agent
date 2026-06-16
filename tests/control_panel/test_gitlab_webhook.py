"""GitLab webhook routing tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from control_panel.api.app import app
from control_panel.config.models import DiscordBotSettings, DiscordBotYamlConfig, InternalConfig
from control_panel.db import JobStatus
from control_panel.db.engine import create_engine, create_session_factory
from control_panel.db.models import Base
from control_panel.db.store import JobStore


class _StubBot:
    def get_channel(self, channel_id: int) -> None:
        return None


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_gitlab_issue_closed_webhook(tmp_path) -> None:
    import os

    url = os.getenv("FIGMA_CP_DATABASE_URL")
    if not url:
        pytest.skip("FIGMA_CP_DATABASE_URL is not set")

    engine = create_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    store = JobStore(create_session_factory(engine))
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
        issue_provider="gitlab",
        issue_project_ref="7",
        issue_number=3,
        issue_url="https://gitlab/issue/3",
    )
    settings = DiscordBotSettings(
        yaml=DiscordBotYamlConfig(internal=InternalConfig(gitlab_webhook_secret="secret")),
        discord_bot_token="x",  # noqa: S106
        gitlab_private_token="y",  # noqa: S106
        github_token="z",  # noqa: S106
        telegram_bot_token="t",  # noqa: S106
        database_url=url,
        database_mode=DiscordBotYamlConfig().database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=tmp_path / "cfg.yml",
    )
    app.state.settings = settings
    app.state.store = store
    app.state.bot = _StubBot()
    app.state.arq_pool = None
    app.state.engine = engine

    payload = {
        "object_kind": "issue",
        "object_attributes": {"state": "closed", "iid": 3, "url": "https://gitlab/issue/3"},
        "project": {"id": 7},
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/gitlab",
            json=payload,
            headers={"X-Gitlab-Token": "secret"},
        )
    assert response.status_code == 200
    updated = await store.get_job("job1")
    assert updated is not None
    assert updated.status == JobStatus.ISSUE_CLOSED
    await engine.dispose()
