"""Discord bot unit tests."""

from __future__ import annotations

import asyncio

import pytest

from discord_bot.bot.access import is_authorized
from discord_bot.config.models import (
    AccessMode,
    DiscordAccessConfig,
    DiscordBotYamlConfig,
    DiscordSectionConfig,
)
from discord_bot.db import JobStatus, JobStore, Quality
from discord_bot.runner.feature_slug import infer_feature_slug
from discord_bot.runner.preview import build_preview_session, hash_preview_token
from discord_bot.runner.provision import ensure_user_project


@pytest.mark.discord
def test_infer_feature_slug_from_feature_first_path() -> None:
    files = ["lib/features/bank_home/screens/bank_home_screen.dart"]
    assert infer_feature_slug(files) == "bank_home"


@pytest.mark.discord
@pytest.mark.asyncio
async def test_job_store_create_and_update(tmp_path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite")
    job = await store.create_job(
        job_id="abc123",
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        discord_user_id=42,
        discord_channel_id=99,
        project_dir=tmp_path / "proj",
        gitlab_app_project_id="1",
    )
    assert job.status == JobStatus.CREATED
    updated = await store.update_job("abc123", status=JobStatus.PIPELINE_RUNNING.value)
    assert updated is not None
    assert updated.status == JobStatus.PIPELINE_RUNNING


@pytest.mark.discord
def test_preview_session_token_hash() -> None:
    from discord_bot.config.models import PreviewConfig

    session = build_preview_session(job_id="job1", config=PreviewConfig())
    assert hash_preview_token(session.token) == session.token_hash
    assert session.fixed_url.startswith("figma-flutter://preview/job1")


@pytest.mark.discord
def test_provision_user_project(tmp_path) -> None:
    project_dir = tmp_path / "user_app"
    resolved = ensure_user_project(project_dir)
    assert (resolved / "pubspec.yaml").is_file()


@pytest.mark.discord
def test_access_allowlist_denies_unknown_user() -> None:
    yaml_config = DiscordBotYamlConfig(
        discord=DiscordSectionConfig(
            access=DiscordAccessConfig(
                mode=AccessMode.ALLOWLIST,
                allowed_user_ids=[111],
            )
        )
    )

    class _Author:
        id = 222

    class _Inter:
        author = _Author()
        guild = None

    assert is_authorized(_Inter(), yaml_config) is False


@pytest.mark.discord
def test_quality_enum_values() -> None:
    assert Quality.GOOD.value == "good"
