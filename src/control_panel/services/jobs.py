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
    else:
        if not principal:
            raise FigmaFlutterError("API jobs require principal")
        resolved_repo = resolve_active_repo_key_for_principal(
            settings,
            principal,
            repo_key=repo_key,
        )
        project_dir = resolve_sandbox_dir_for_principal(settings, principal, resolved_repo)

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
