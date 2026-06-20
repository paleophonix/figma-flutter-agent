"""Shared job creation and enqueue logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from control_panel.config.models import TargetMode
from control_panel.db import JobOrigin, JobStatus
from control_panel.db.store import GenerationJob, JobStore
from control_panel.publish.scan import list_screen_candidates
from control_panel.services.job_events import publish_status_changed
from control_panel.services.projects import (
    resolve_active_repo_key,
    resolve_active_repo_key_for_principal,
    resolve_repo_config,
    resolve_sandbox_dir,
    resolve_sandbox_dir_for_principal,
)
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.observability.posthog_business import (
    TEAM_REQUESTED_GENERATION,
    capture_business_event,
    resolve_distinct_id,
)

if TYPE_CHECKING:
    from arq import ArqRedis

    from control_panel.config import DiscordBotSettings


@dataclass(frozen=True)
class EnqueueGenerationResult:
    """Outcome of enqueueing a generation job."""

    job_id: str
    job: GenerationJob


async def enqueue_generation(
    *,
    settings: DiscordBotSettings,
    store: JobStore,
    arq_pool: ArqRedis | None,
    figma_url: str,
    origin: JobOrigin,
    principal: str | None = None,
    discord_user_id: int | None = None,
    discord_channel_id: int | None = None,
    repo_key: str | None = None,
    mode: str = TargetMode.NEW.value,
    target_file: str | None = None,
    redis: object | None = None,
) -> EnqueueGenerationResult:
    """Create a job and enqueue ``run_generation_job``."""
    from figma_flutter_agent.figma.url import parse_figma_url

    parse_figma_url(figma_url.strip())

    if origin == JobOrigin.DISCORD:
        if discord_user_id is None or discord_channel_id is None:
            raise FigmaFlutterError("Discord jobs require discord_user_id and discord_channel_id")
        resolved_repo = repo_key or await resolve_active_repo_key(
            settings,
            store,
            discord_user_id,
        )
        project_dir = resolve_sandbox_dir(settings, discord_user_id, resolved_repo)
    elif origin == JobOrigin.API:
        if not principal:
            raise FigmaFlutterError("API jobs require principal")
        resolved_repo = resolve_active_repo_key_for_principal(
            settings,
            principal,
            repo_key=repo_key,
        )
        project_dir = resolve_sandbox_dir_for_principal(settings, principal, resolved_repo)
    else:
        raise FigmaFlutterError(f"Unsupported job origin: {origin}")

    repo_cfg = resolve_repo_config(settings, resolved_repo)
    resolved_target = target_file
    if mode == TargetMode.EXISTING.value and not resolved_target:
        candidates = await list_screen_candidates(settings, repo_cfg)
        if not candidates:
            raise FigmaFlutterError("No screen files found in the active repository.")
        resolved_target = candidates[0]

    job_id = uuid.uuid4().hex
    gitlab_project_id = repo_cfg.gitlab_project_id or settings.yaml.gitlab.app_project_id
    job = await store.create_job(
        job_id=job_id,
        figma_url=figma_url.strip(),
        origin=origin.value,
        principal=principal,
        discord_user_id=discord_user_id,
        discord_channel_id=discord_channel_id,
        project_dir=project_dir,
        gitlab_app_project_id=gitlab_project_id,
        repo_key=resolved_repo,
        git_provider=repo_cfg.provider.value,
        target_mode=mode,
        target_file_path=resolved_target,
    )
    await publish_status_changed(redis, job)

    if arq_pool is None:
        await store.update_job(
            job_id,
            status=JobStatus.FAILED.value,
            error_message="ARQ pool unavailable; cannot enqueue generation job.",
        )
        refreshed = await store.get_job(job_id)
        if refreshed is not None:
            await publish_status_changed(redis, refreshed, previous_status=JobStatus.CREATED)
        if refreshed is None:
            raise FigmaFlutterError("Failed to create job")
        return EnqueueGenerationResult(job_id=job_id, job=refreshed)

    await arq_pool.enqueue_job("run_generation_job", job_id)
    capture_business_event(
        settings=settings,
        event=TEAM_REQUESTED_GENERATION,
        distinct_id=resolve_distinct_id(
            principal=principal,
            discord_user_id=discord_user_id,
            job_id=job_id,
        ),
        properties={
            "job_id": job_id,
            "origin": origin.value,
            "repo_key": resolved_repo,
            "target_mode": mode,
        },
    )
    if discord_user_id is not None:
        await store.append_audit(
            job_id=job_id,
            discord_user_id=discord_user_id,
            action="generate_requested",
            payload={
                "mode": mode,
                "target_file": resolved_target,
                "repo_key": resolved_repo,
                "origin": origin.value,
            },
        )
    refreshed = await store.get_job(job_id)
    if refreshed is None:
        raise FigmaFlutterError("Failed to load job after enqueue")
    return EnqueueGenerationResult(job_id=job_id, job=refreshed)


async def enqueue_generation_from_issue(
    *,
    settings: DiscordBotSettings,
    store: JobStore,
    arq_pool: ArqRedis | None,
    redis: object | None,
    project_id: str,
    issue_iid: int,
    issue_url: str,
    description: str,
    force: bool = False,
) -> EnqueueGenerationResult:
    """Create or reuse a GitLab-linked job and enqueue generation."""
    from pathlib import Path

    from control_panel.config.models import GitProvider
    from control_panel.gitlab_workflow.branch import issue_branch_name
    from control_panel.gitlab_workflow.parser import extract_first_figma_frame_url
    from control_panel.gitlab_workflow.project import issue_sandbox_dir

    figma_url = extract_first_figma_frame_url(description)
    project_ref = str(project_id)

    if not force:
        active = await store.find_active_generation_for_issue(project_ref, issue_iid)
        if active is not None:
            return EnqueueGenerationResult(job_id=active.id, job=active)
        existing = await store.find_job_by_issue(project_ref, issue_iid, provider="gitlab")
        if existing is not None and existing.status == JobStatus.PREVIEW_READY:
            return EnqueueGenerationResult(job_id=existing.id, job=existing)

    existing = await store.find_job_by_issue(project_ref, issue_iid, provider="gitlab")
    sandbox = Path(issue_sandbox_dir(settings, project_id=project_ref, issue_iid=issue_iid))
    sandbox.mkdir(parents=True, exist_ok=True)

    if existing is not None and force:
        job_id = existing.id
        branch = existing.publish_branch or issue_branch_name(
            settings,
            issue_iid=issue_iid,
            job_id=job_id,
        )
        job = await store.update_job(
            job_id,
            figma_url=figma_url.strip(),
            status=JobStatus.CREATED.value,
            error_message=None,
            publish_branch=branch,
            gitlab_source_branch=branch,
        )
        if job is None:
            raise FigmaFlutterError(f"Failed to refresh job {job_id}")
    else:
        job_id = uuid.uuid4().hex
        branch = issue_branch_name(settings, issue_iid=issue_iid, job_id=job_id)
        job = await store.create_job(
            job_id=job_id,
            figma_url=figma_url.strip(),
            origin=JobOrigin.GITLAB.value,
            project_dir=sandbox,
            gitlab_app_project_id=project_ref,
            gitlab_issue_iid=issue_iid,
            gitlab_issue_url=issue_url,
            publish_branch=branch,
            issue_provider=GitProvider.GITLAB.value,
            issue_project_ref=project_ref,
            issue_number=issue_iid,
            issue_url=issue_url,
            repo_key=project_ref,
            git_provider=GitProvider.GITLAB.value,
        )
        await store.update_job(job_id, gitlab_source_branch=branch)
        job = await store.get_job(job_id)
        if job is None:
            raise FigmaFlutterError("Failed to create GitLab generation job")

    await publish_status_changed(redis, job)

    if arq_pool is None:
        await store.update_job(
            job_id,
            status=JobStatus.FAILED.value,
            error_message="ARQ pool unavailable; cannot enqueue generation job.",
        )
        refreshed = await store.get_job(job_id)
        if refreshed is None:
            raise FigmaFlutterError("Failed to load job after enqueue failure")
        return EnqueueGenerationResult(job_id=job_id, job=refreshed)

    await arq_pool.enqueue_job("run_generation_job", job_id)
    capture_business_event(
        settings=settings,
        event=TEAM_REQUESTED_GENERATION,
        distinct_id=resolve_distinct_id(job_id=job_id),
        properties={
            "job_id": job_id,
            "origin": JobOrigin.GITLAB.value,
            "repo_key": project_ref,
            "gitlab_issue_iid": issue_iid,
            "force": force,
        },
    )
    refreshed = await store.get_job(job_id)
    if refreshed is None:
        raise FigmaFlutterError("Failed to load job after enqueue")
    return EnqueueGenerationResult(job_id=job_id, job=refreshed)
