"""ARQ worker tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from discord_bot.config import DiscordBotSettings, load_discord_bot_settings
from discord_bot.config.models import GitProvider
from discord_bot.db import IssueKind, JobStatus, JobStore, Quality
from discord_bot.db.engine import create_engine, create_session_factory
from discord_bot.db.models import Base
from discord_bot.feedback.bundle import build_feedback_bundle_zip
from discord_bot.feedback.llm_review import generate_feedback_issue_review
from discord_bot.publish.orchestrate import run_publish_for_job
from discord_bot.runner.artifacts import (
    publish_artifacts,
    publish_artifacts_remote,
    zip_screen_artifacts,
)
from discord_bot.runner.pipeline import execute_generation_pipeline
from discord_bot.runner.preview import build_preview_session, write_preview_sidecar
from discord_bot.runner.provision import ensure_user_project
from discord_bot.runner.review import generate_feedback_review
from discord_bot.services.github import GitHubClient
from discord_bot.services.gitlab import GitLabClient
from discord_bot.services.issues import (
    IssueService,
    artifacts_provider,
    resolve_artifacts_remote,
)
from discord_bot.services.projects import resolve_active_repo_key, resolve_repo_config
from discord_bot.workers.callback import post_job_event
from discord_bot.workers.locks import RedisProjectLock
from figma_flutter_agent.errors import FigmaFlutterError


async def run_generation_job(ctx: dict[str, Any], job_id: str) -> None:
    """Execute the figma-flutter pipeline for one queued job."""
    settings: DiscordBotSettings = ctx["settings"]
    store: JobStore = ctx["store"]
    redis: Redis = ctx["redis"]
    job = await store.get_job(job_id)
    if job is None:
        return
    project_dir = ensure_user_project(Path(job.project_dir))
    await store.update_job(
        job_id,
        status=JobStatus.PIPELINE_RUNNING.value,
        project_dir=project_dir.as_posix(),
    )
    lock = RedisProjectLock(redis)
    try:
        async with lock.acquire(project_dir.as_posix()):
            outcome = await execute_generation_pipeline(
                figma_url=job.figma_url,
                project_dir=project_dir,
            )
    except Exception as exc:
        logger.exception("Pipeline failed for job {}", job_id)
        message = str(exc)
        if isinstance(exc, FigmaFlutterError):
            message = str(exc)
        await store.update_job(
            job_id,
            status=JobStatus.FAILED.value,
            error_message=message[:4000],
        )
        await post_job_event(settings, job_id=job_id, event="failed", error_message=message)
        return

    feature_slug = outcome.feature_slug or "screen"
    session = build_preview_session(job_id=job_id, config=settings.yaml.preview)
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
    artifacts_project = settings.yaml.gitlab.artifacts_project_id.strip()
    if artifacts_project:
        gitlab = GitLabClient(
            base_url=settings.yaml.gitlab.base_url,
            token=settings.gitlab_private_token.get_secret_value(),
        )
        try:
            artifact_url = await publish_artifacts(
                gitlab=gitlab,
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

    await store.update_job(
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
    await post_job_event(settings, job_id=job_id, event="preview_ready")


async def feedback_issue_job(ctx: dict[str, Any], job_id: str) -> None:
    """Create a feedback issue with LLM review and artifact bundle."""
    settings: DiscordBotSettings = ctx["settings"]
    store: JobStore = ctx["store"]
    job = await store.get_job(job_id)
    if job is None:
        return
    if job.feedback_quality is None or job.feedback_quality == Quality.GOOD:
        return
    await store.update_job(job_id, status=JobStatus.FEEDBACK_ISSUE_CREATING.value)
    job = await store.get_job(job_id)
    if job is None:
        return
    project_dir = Path(job.project_dir)
    feature_slug = job.feature_slug or "screen"
    quality = job.feedback_quality

    try:
        repo_key = job.repo_key or await resolve_active_repo_key(
            settings, store, job.discord_user_id
        )
        repo = resolve_repo_config(settings, repo_key)
        review = await generate_feedback_issue_review(
            job_id=job_id,
            figma_url=job.figma_url,
            quality=quality,
            feature_slug=feature_slug,
            user_comment=job.feedback_comment or "",
            project_dir=project_dir,
        )
        debug_zip: Path | None = None
        try:
            debug_zip = zip_screen_artifacts(
                project_dir=project_dir,
                feature_slug=feature_slug,
                job_id=job_id,
            )
        except FileNotFoundError:
            logger.warning("Debug zip missing for feedback job {}", job_id)
        bundle_zip = build_feedback_bundle_zip(
            project_dir=project_dir,
            feature_slug=feature_slug,
            job_id=job_id,
            debug_zip_path=debug_zip,
        )
        artifacts_remote = resolve_artifacts_remote(settings)
        artifact_url = ""
        if artifacts_remote:
            provider = artifacts_provider(artifacts_remote)
            gitlab = GitLabClient(
                base_url=settings.yaml.gitlab.base_url,
                token=settings.gitlab_private_token.get_secret_value(),
            )
            github = None
            if provider == GitProvider.GITHUB:
                github = GitHubClient(
                    token=settings.github_token.get_secret_value(),
                    repo=artifacts_remote,
                )
            artifact_url = await publish_artifacts_remote(
                provider=provider,
                remote=artifacts_remote,
                gitlab=gitlab,
                github=github,
                job_id=job_id,
                project_dir=project_dir,
                feature_slug=feature_slug,
                run_id=job.run_id or job_id,
                figma_url=job.figma_url,
                discord_user_id=job.discord_user_id,
                zip_path=bundle_zip,
                review_markdown=review.body,
            )
        issue_service = IssueService(settings)
        created = await issue_service.create_feedback_issue(
            job=job,
            repo=repo,
            review=review,
            quality=quality,
            zip_path=bundle_zip,
            artifact_repo_url=artifact_url,
        )
        project_ref = created.project_ref
        await store.update_job(
            job_id,
            status=JobStatus.FEEDBACK_ISSUE_CREATED.value,
            artifact_zip_path=bundle_zip.as_posix(),
            artifact_repo_commit_url=artifact_url or None,
            issue_provider=created.provider,
            issue_project_ref=project_ref,
            issue_number=created.number,
            issue_url=created.url,
            issue_kind=IssueKind.BUG.value,
            gitlab_app_project_id=project_ref if created.provider == "gitlab" else job.gitlab_app_project_id,
            gitlab_issue_iid=created.number if created.provider == "gitlab" else job.gitlab_issue_iid,
            gitlab_issue_url=created.url if created.provider == "gitlab" else job.gitlab_issue_url,
            repo_key=repo_key,
            git_provider=repo.provider.value,
        )
        await post_job_event(settings, job_id=job_id, event="feedback_issue_created")
    except Exception as exc:
        logger.exception("Feedback issue job failed for {}", job_id)
        await store.update_job(
            job_id,
            status=JobStatus.FAILED.value,
            error_message=str(exc)[:4000],
        )
        await post_job_event(settings, job_id=job_id, event="failed", error_message=str(exc))


async def publish_job(ctx: dict[str, Any], job_id: str) -> None:
    """Migrate generated files and open or update a pull request."""
    settings: DiscordBotSettings = ctx["settings"]
    store: JobStore = ctx["store"]
    job = await store.get_job(job_id)
    if job is None:
        return
    await store.update_job(job_id, status=JobStatus.MR_CREATING.value)
    try:
        result = await run_publish_for_job(settings=settings, store=store, job=job)
    except Exception as exc:
        logger.exception("Publish failed for job {}", job_id)
        await store.update_job(
            job_id,
            status=JobStatus.FAILED.value,
            error_message=str(exc)[:4000],
        )
        await post_job_event(settings, job_id=job_id, event="failed", error_message=str(exc))
        return
    await store.update_job(
        job_id,
        status=JobStatus.MR_READY.value,
        publish_branch=result.branch,
        publish_pr_url=result.pr_url,
        publish_pr_number=result.pr_number,
        gitlab_mr_url=result.pr_url,
        gitlab_source_branch=result.branch,
    )
    job = await store.get_job(job_id)
    if job is None:
        return
    try:
        repo_key = job.repo_key or await resolve_active_repo_key(
            settings, store, job.discord_user_id
        )
        repo = resolve_repo_config(settings, repo_key)
        feature_slug = job.feature_slug or job.id[:8]
        created = await IssueService(settings).create_feat_issue(
            job=job,
            repo=repo,
            mr_url=result.pr_url,
            feature_slug=feature_slug,
        )
        await store.update_job(
            job_id,
            issue_provider=created.provider,
            issue_project_ref=created.project_ref,
            issue_number=created.number,
            issue_url=created.url,
            issue_kind=IssueKind.FEAT.value,
            gitlab_app_project_id=(
                created.project_ref if created.provider == "gitlab" else job.gitlab_app_project_id
            ),
            gitlab_issue_iid=created.number if created.provider == "gitlab" else job.gitlab_issue_iid,
            gitlab_issue_url=created.url if created.provider == "gitlab" else job.gitlab_issue_url,
            repo_key=repo_key,
            git_provider=repo.provider.value,
        )
    except Exception:
        logger.exception("Feat issue creation failed for publish job {}", job_id)
    await post_job_event(settings, job_id=job_id, event="publish_ready")


async def on_startup(ctx: dict[str, Any]) -> None:
    """Initialize worker dependencies."""
    settings = load_discord_bot_settings(require_discord_token=False)
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    store = JobStore(session_factory)
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    ctx["settings"] = settings
    ctx["store"] = store
    ctx["engine"] = engine
    ctx["redis"] = redis


async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Dispose worker resources."""
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()
    redis = ctx.get("redis")
    if redis is not None:
        await redis.aclose()
