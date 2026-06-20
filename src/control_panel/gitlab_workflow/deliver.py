"""Finalize GitLab Issue generation jobs after pipeline success."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from control_panel.config import DiscordBotSettings
from control_panel.db.store import GenerationJob, JobStore
from control_panel.gitlab_workflow.branch_push import push_issue_branch
from control_panel.gitlab_workflow.notify import post_preview_ready_comment
from control_panel.gitlab_workflow.preview_urls import build_http_preview_url
from control_panel.preview.serve import ensure_flutter_preview_server
from control_panel.runner.preview import PreviewSession


async def finalize_gitlab_generation(
    *,
    settings: DiscordBotSettings,
    store: JobStore,
    job: GenerationJob,
    session: PreviewSession,
) -> GenerationJob | None:
    """Push issue branch, start preview, and notify the GitLab issue."""
    project_dir = Path(job.project_dir)
    try:
        ensure_flutter_preview_server(project_dir=project_dir, mode="fixed")
        ensure_flutter_preview_server(project_dir=project_dir, mode="adaptive")
    except Exception:
        logger.exception("Preview server start failed for GitLab job {}", job.id)

    fixed_url = build_http_preview_url(
        settings,
        job_id=job.id,
        token=session.token,
        mode="fixed",
    )
    adaptive_url = build_http_preview_url(
        settings,
        job_id=job.id,
        token=session.token,
        mode="adaptive",
    )
    refreshed = await store.update_job(
        job.id,
        fixed_preview_url=fixed_url,
        adaptive_preview_url=adaptive_url,
    )
    if refreshed is None:
        return None

    try:
        branch_url = await push_issue_branch(settings, refreshed)
    except Exception:
        logger.exception("Issue branch push failed for job {}", job.id)
        branch_url = ""
    else:
        await store.update_job(
            job.id,
            gitlab_source_branch=refreshed.publish_branch,
        )

    if branch_url:
        await post_preview_ready_comment(settings, refreshed, branch_url=branch_url)
    return await store.get_job(job.id)
