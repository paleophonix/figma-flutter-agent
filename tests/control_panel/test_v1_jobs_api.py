"""Integration tests for /v1/jobs via FastAPI dependency overrides."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from control_panel.api.deps import get_arq_pool, get_redis, get_settings, get_store, hash_api_key
from control_panel.api.routers.jobs import router as jobs_router
from control_panel.config.models import (
    ApiClientConfig,
    DiscordBotSettings,
    DiscordBotYamlConfig,
    ProjectsConfig,
    RepoConfig,
)
from control_panel.db import JobOrigin, JobStatus
from control_panel.db.store import GenerationJob


def _settings(*, key_hash: str, workspace_root: Path) -> DiscordBotSettings:
    yaml = DiscordBotYamlConfig(
        projects=ProjectsConfig(
            workspace_root=workspace_root,
            repos={"default": RepoConfig(gitlab_project_id="1")},
        ),
    )
    clients = (ApiClientConfig(principal="ci-bot", key_hash=key_hash, project_key="default"),)
    return DiscordBotSettings(
        yaml=yaml,
        discord_bot_token=SecretStr(""),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=yaml.database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=workspace_root / "cfg.yml",
        api_enabled=True,
        api_clients=clients,
    )


def _job(
    *,
    job_id: str,
    principal: str,
    project_dir: Path,
) -> GenerationJob:
    now = datetime.now(UTC).isoformat()
    return GenerationJob(
        id=job_id,
        run_id=None,
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        discord_user_id=None,
        discord_channel_id=None,
        discord_message_id=None,
        review_message_id=None,
        project_dir=project_dir.as_posix(),
        feature_slug=None,
        status=JobStatus.CREATED,
        repo_key="default",
        git_provider="gitlab",
        target_mode="new",
        target_file_path=None,
        fixed_preview_url=None,
        adaptive_preview_url=None,
        preview_token_hash=None,
        artifact_zip_path=None,
        artifact_repo_commit_url=None,
        gitlab_app_project_id="1",
        gitlab_issue_iid=None,
        gitlab_issue_url=None,
        gitlab_mr_iid=None,
        gitlab_mr_url=None,
        gitlab_source_branch=None,
        publish_branch=None,
        publish_pr_url=None,
        publish_pr_number=None,
        feedback_quality=None,
        feedback_comment=None,
        feedback_comment_message_id=None,
        issue_provider=None,
        issue_project_ref=None,
        issue_number=None,
        issue_url=None,
        issue_kind=None,
        origin=JobOrigin.API,
        principal=principal,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


class _MemoryJobStore:
    """Minimal in-memory store for API route tests."""

    def __init__(self, workspace_root: Path) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._workspace_root = workspace_root

    async def ping(self) -> None:
        return None

    async def create_job(
        self,
        *,
        job_id: str,
        figma_url: str,
        project_dir: Path,
        origin: str = JobOrigin.DISCORD.value,
        principal: str | None = None,
        discord_user_id: int | None = None,
        discord_channel_id: int | None = None,
        gitlab_app_project_id: str = "",
        repo_key: str | None = None,
        git_provider: str | None = None,
        target_mode: str | None = None,
        target_file_path: str | None = None,
    ) -> GenerationJob:
        job = _job(job_id=job_id, principal=principal or "", project_dir=project_dir)
        job = GenerationJob(
            id=job.id,
            run_id=job.run_id,
            figma_url=figma_url,
            discord_user_id=discord_user_id,
            discord_channel_id=discord_channel_id,
            discord_message_id=job.discord_message_id,
            review_message_id=job.review_message_id,
            project_dir=project_dir.as_posix(),
            feature_slug=job.feature_slug,
            status=job.status,
            repo_key=repo_key,
            git_provider=git_provider,
            target_mode=target_mode,
            target_file_path=target_file_path,
            fixed_preview_url=job.fixed_preview_url,
            adaptive_preview_url=job.adaptive_preview_url,
            preview_token_hash=job.preview_token_hash,
            artifact_zip_path=job.artifact_zip_path,
            artifact_repo_commit_url=job.artifact_repo_commit_url,
            gitlab_app_project_id=gitlab_app_project_id or None,
            gitlab_issue_iid=job.gitlab_issue_iid,
            gitlab_issue_url=job.gitlab_issue_url,
            gitlab_mr_iid=job.gitlab_mr_iid,
            gitlab_mr_url=job.gitlab_mr_url,
            gitlab_source_branch=job.gitlab_source_branch,
            publish_branch=job.publish_branch,
            publish_pr_url=job.publish_pr_url,
            publish_pr_number=job.publish_pr_number,
            feedback_quality=job.feedback_quality,
            feedback_comment=job.feedback_comment,
            feedback_comment_message_id=job.feedback_comment_message_id,
            issue_provider=job.issue_provider,
            issue_project_ref=job.issue_project_ref,
            issue_number=job.issue_number,
            issue_url=job.issue_url,
            issue_kind=job.issue_kind,
            origin=JobOrigin(origin),
            principal=principal,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> GenerationJob | None:
        return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **fields: Any) -> GenerationJob | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        data = job.__dict__.copy()
        if "status" in fields:
            data["status"] = JobStatus(fields["status"])
        for key, value in fields.items():
            if key != "status":
                data[key] = value
        updated = GenerationJob(**data)
        self._jobs[job_id] = updated
        return updated

    async def list_jobs_by_principal(
        self,
        principal: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GenerationJob]:
        jobs = [job for job in self._jobs.values() if job.principal == principal]
        jobs.sort(key=lambda item: item.created_at, reverse=True)
        return jobs[offset : offset + limit]


@pytest.fixture
def v1_app(tmp_path: Path):
    """FastAPI app with /v1/jobs router and dependency overrides (no lifespan)."""
    app = FastAPI()
    app.include_router(jobs_router)
    digest = hash_api_key("secret")
    settings = _settings(key_hash=digest, workspace_root=tmp_path)
    store = _MemoryJobStore(tmp_path)
    arq_pool = AsyncMock()
    arq_pool.enqueue_job = AsyncMock()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_arq_pool] = lambda: arq_pool
    app.dependency_overrides[get_redis] = lambda: None

    yield app, store, arq_pool, settings, digest
    app.dependency_overrides.clear()


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_create_job_unauthorized(v1_app) -> None:
    app, *_rest = v1_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/jobs",
            json={"figma_url": "https://www.figma.com/design/x/y?node-id=1-2"},
        )
    assert response.status_code == 401


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_create_job_accepted(v1_app) -> None:
    import sys

    app, _store, arq_pool, _settings_obj, _digest = v1_app
    url_module = MagicMock()
    url_module.parse_figma_url = MagicMock(return_value=object())
    transport = ASGITransport(app=app)
    with patch.dict(sys.modules, {"figma_flutter_agent.figma.url": url_module}):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/jobs",
                json={"figma_url": "https://www.figma.com/design/x/y?node-id=1-2"},
                headers={"X-API-Key": "secret"},
            )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == JobStatus.CREATED.value
    assert body["job_id"]
    arq_pool.enqueue_job.assert_awaited_once_with("run_generation_job", body["job_id"])


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_get_job_wrong_principal_returns_404(v1_app, tmp_path: Path) -> None:
    app, store, *_rest = v1_app
    await store.create_job(
        job_id="owned-by-other",
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        project_dir=tmp_path / "proj",
        origin=JobOrigin.API.value,
        principal="other-bot",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/jobs/owned-by-other",
            headers={"X-API-Key": "secret"},
        )
    assert response.status_code == 404


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_list_jobs_scoped_to_principal(v1_app, tmp_path: Path) -> None:
    app, store, *_rest = v1_app
    await store.create_job(
        job_id="mine",
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        project_dir=tmp_path / "proj",
        origin=JobOrigin.API.value,
        principal="ci-bot",
    )
    await store.create_job(
        job_id="theirs",
        figma_url="https://www.figma.com/design/x/y?node-id=3-4",
        project_dir=tmp_path / "proj2",
        origin=JobOrigin.API.value,
        principal="other-bot",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/jobs", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["job_id"] == "mine"
    assert body["items"][0]["principal"] == "ci-bot"
