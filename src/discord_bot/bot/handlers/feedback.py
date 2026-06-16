"""Handle Discord quality feedback button interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import disnake

from discord_bot.config import DiscordBotSettings
from discord_bot.db import (
    FEEDBACK_LABELS,
    QUALITY_LABELS,
    GenerationJob,
    JobStatus,
    JobStore,
    Quality,
    job_marker,
)
from discord_bot.runner.review import generate_feedback_review
from discord_bot.services.gitlab import GitLabClient
from discord_bot.services.notify import send_issue_created_notice

if TYPE_CHECKING:
    from discord_bot.bot.app import DiscordControlBot


async def handle_feedback(
    *,
    inter: disnake.MessageInteraction,
    job_id: str,
    quality: Quality,
) -> None:
    """Route quality feedback to GitLab issue or publish queue."""
    bot = inter.bot
    if not isinstance(bot, DiscordControlBot):
        await inter.response.send_message("Bot context unavailable.", ephemeral=True)
        return
    store = bot.job_store
    settings = bot.settings
    job = await store.get_job(job_id)
    if job is None:
        await inter.response.send_message("Job not found.", ephemeral=True)
        return
    if inter.author.id != job.discord_user_id:
        await inter.response.send_message(
            "Only the /generate author can rate this layout.",
            ephemeral=True,
        )
        return
    if job.status != JobStatus.PREVIEW_READY:
        await inter.response.send_message("Feedback already handled.", ephemeral=True)
        return

    await inter.response.defer(ephemeral=True)
    await store.append_audit(
        job_id=job_id,
        discord_user_id=inter.author.id,
        action="feedback",
        payload={"quality": quality.value},
    )

    if quality == Quality.GOOD:
        await _enqueue_publish(
            inter=inter,
            bot=bot,
            store=store,
            job=job,
        )
        return
    await _create_feedback_issue(
        inter=inter,
        bot=bot,
        store=store,
        settings=settings,
        job=job,
        quality=quality,
    )


async def _enqueue_publish(
    *,
    inter: disnake.MessageInteraction,
    bot: DiscordControlBot,
    store: JobStore,
    job: GenerationJob,
) -> None:
    await store.update_job(job.id, status=JobStatus.ACCEPTED.value, feedback_quality=Quality.GOOD.value)
    pool = bot.arq_pool
    if pool is None:
        await inter.edit_original_response(content="Publish queue unavailable.")
        return
    await pool.enqueue_job("publish_job", job.id)
    await inter.edit_original_response(content="Publish queued. You will be notified when the PR is ready.")


async def _create_feedback_issue(
    *,
    inter: disnake.MessageInteraction,
    bot: DiscordControlBot,
    store: JobStore,
    settings: DiscordBotSettings,
    job: GenerationJob,
    quality: Quality,
) -> None:
    gitlab = GitLabClient(
        base_url=settings.yaml.gitlab.base_url,
        token=settings.gitlab_private_token.get_secret_value(),
    )
    project_id = settings.yaml.gitlab.app_project_id
    review = await generate_feedback_review(
        job_id=job.id,
        figma_url=job.figma_url,
        quality_label=QUALITY_LABELS[quality],
        warnings=[],
        feature_slug=job.feature_slug,
    )
    description = (
        f"{job_marker(job.id)}\n\n"
        f"{review.body}\n\n"
        f"## Previews\n"
        f"- Fixed: {job.fixed_preview_url}\n"
        f"- Adaptive: {job.adaptive_preview_url}\n\n"
        f"## Artifacts\n"
        f"- Zip: {job.artifact_zip_path or '(local)'}\n"
        f"- Repo: {job.artifact_repo_commit_url or '(none)'}\n"
    )
    labels = ["agent-feedback", FEEDBACK_LABELS[quality], "generated-layout"]
    issue = await gitlab.create_issue(
        project_id=project_id,
        title=review.title,
        description=description,
        labels=labels,
        assignee_username=settings.yaml.gitlab.assignee_username,
    )
    if job.artifact_zip_path:
        from pathlib import Path

        await gitlab.create_issue_note_with_upload(
            project_id=project_id,
            issue_iid=int(issue["iid"]),
            body="Artifact bundle attached.",
            upload_path=Path(job.artifact_zip_path),
        )
    await store.update_job(
        job.id,
        status=JobStatus.FEEDBACK_ISSUE_CREATED.value,
        feedback_quality=quality.value,
        gitlab_issue_iid=int(issue["iid"]),
        gitlab_issue_url=str(issue.get("web_url") or ""),
    )
    updated = await store.get_job(job.id)
    if updated is not None:
        await send_issue_created_notice(
            bot,
            updated,
            issue_url=str(issue.get("web_url") or ""),
        )
    await inter.edit_original_response(content=f"Issue created: {issue.get('web_url', '')}")
