"""Background job worker for Discord generation jobs."""

from __future__ import annotations

import asyncio
from pathlib import Path

from disnake.ext import commands
from loguru import logger

from discord_bot.config import DiscordBotSettings
from discord_bot.db import JobStatus, JobStore
from discord_bot.runner.artifacts import publish_artifacts, zip_screen_artifacts
from discord_bot.runner.lock import ProjectLockRegistry
from discord_bot.runner.pipeline import execute_generation_pipeline
from discord_bot.runner.preview import build_preview_session, write_preview_sidecar
from discord_bot.runner.provision import ensure_user_project
from discord_bot.runner.review import generate_feedback_review
from discord_bot.services.gitlab import GitLabClient
from discord_bot.services.notify import send_failure_notice, send_preview_ready
from figma_flutter_agent.errors import FigmaFlutterError


class JobWorker:
    """Poll and execute generation jobs."""

    def __init__(
        self,
        *,
        settings: DiscordBotSettings,
        store: JobStore,
        bot: commands.InteractionBot,
        locks: ProjectLockRegistry,
    ) -> None:
        self._settings = settings
        self._store = store
        self._bot = bot
        self._locks = locks
        self._tasks: set[asyncio.Task[None]] = set()
        self._gitlab = GitLabClient(
            base_url=settings.yaml.gitlab.base_url,
            token=settings.gitlab_private_token.get_secret_value(),
        )

    async def run_forever(self) -> None:
        """Poll for created jobs until cancelled."""
        while True:
            jobs = await self._store.list_jobs_by_status(JobStatus.CREATED)
            for job in jobs:
                if any(task.get_name() == job.id for task in self._tasks):
                    continue
                task = asyncio.create_task(self._run_job(job.id), name=job.id)
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            await asyncio.sleep(1.0)

    async def _run_job(self, job_id: str) -> None:
        job = await self._store.get_job(job_id)
        if job is None:
            return
        project_dir = ensure_user_project(Path(job.project_dir))
        await self._store.update_job(
            job_id,
            status=JobStatus.PIPELINE_RUNNING.value,
            project_dir=project_dir.as_posix(),
        )
        try:
            async with self._locks.acquire(project_dir):
                outcome = await execute_generation_pipeline(
                    figma_url=job.figma_url,
                    project_dir=project_dir,
                )
        except Exception as exc:
            logger.exception("Pipeline failed for job {}", job_id)
            message = str(exc)
            if isinstance(exc, FigmaFlutterError):
                message = str(exc)
            await self._store.update_job(
                job_id,
                status=JobStatus.FAILED.value,
                error_message=message[:4000],
            )
            failed = await self._store.get_job(job_id)
            if failed is not None:
                await send_failure_notice(self._bot, failed, error_message=message)
            return

        feature_slug = outcome.feature_slug or "screen"
        session = build_preview_session(job_id=job_id, config=self._settings.yaml.preview)
        write_preview_sidecar(
            project_dir,
            job_id=job_id,
            session=session,
            feature_slug=feature_slug,
        )
        review = await generate_feedback_review(
            job_id=job_id,
            figma_url=job.figma_url,
            quality_label="preview",
            warnings=outcome.result.warnings,
            feature_slug=feature_slug,
        )
        zip_path = zip_screen_artifacts(
            project_dir=project_dir,
            feature_slug=feature_slug,
            job_id=job_id,
        )
        artifact_url = ""
        artifacts_project = self._settings.yaml.gitlab.artifacts_project_id.strip()
        if artifacts_project:
            try:
                artifact_url = await publish_artifacts(
                    gitlab=self._gitlab,
                    artifacts_project_id=artifacts_project,
                    job_id=job_id,
                    project_dir=project_dir,
                    feature_slug=feature_slug,
                    run_id=outcome.result.run_id,
                    figma_url=job.figma_url,
                    discord_user_id=job.discord_user_id,
                    zip_path=zip_path,
                    review_markdown=review.body,
                )
            except Exception:
                logger.exception("Artifact publish failed for job {}", job_id)

        await self._store.update_job(
            job_id,
            status=JobStatus.PREVIEW_READY.value,
            run_id=outcome.result.run_id,
            feature_slug=feature_slug,
            fixed_preview_url=session.fixed_url,
            adaptive_preview_url=session.adaptive_url,
            preview_token_hash=session.token_hash,
            artifact_zip_path=zip_path.as_posix(),
            artifact_repo_commit_url=artifact_url or None,
        )
        ready_job = await self._store.get_job(job_id)
        if ready_job is None:
            return
        from discord_bot.bot.views.feedback import PreviewFeedbackView

        view = PreviewFeedbackView(job_id=job_id)
        self._bot.add_view(view)
        message = await send_preview_ready(self._bot, ready_job, view=view)
        await self._store.update_job(job_id, review_message_id=message.id)
