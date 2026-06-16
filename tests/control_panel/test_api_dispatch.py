"""API-origin dispatch tests."""

from __future__ import annotations

import pytest

from control_panel.db.enums import JobOrigin, JobStatus
from control_panel.db.store import GenerationJob
from control_panel.services import events as event_handlers


def _job(**kwargs) -> GenerationJob:
    base = dict(
        id="job1",
        run_id=None,
        figma_url="https://figma.test",
        discord_user_id=None,
        discord_channel_id=None,
        discord_message_id=None,
        review_message_id=None,
        project_dir="/tmp",
        feature_slug="bank_home",
        status=JobStatus.PREVIEW_READY,
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
        principal="ci-bot",
        error_message=None,
        created_at="",
        updated_at="",
    )
    base.update(kwargs)
    return GenerationJob(**base)


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_dispatch_job_event_noop_for_api_origin(job_store) -> None:
    job = _job()
    await event_handlers.dispatch_job_event(
        bot=None,
        store=job_store,
        job=job,
        event="preview_ready",
    )
