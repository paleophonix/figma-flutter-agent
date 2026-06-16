"""PostgreSQL persistence for generation jobs and audit events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from discord_bot.db.enums import JobStatus, Quality
from discord_bot.db.models import AuditEventRow, GenerationJobRow, UserPreferenceRow


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class GenerationJob:
    """Row model for ``generation_jobs``."""

    id: str
    run_id: str | None
    figma_url: str
    discord_user_id: int
    discord_channel_id: int
    discord_message_id: int | None
    review_message_id: int | None
    project_dir: str
    feature_slug: str | None
    status: JobStatus
    repo_key: str | None
    git_provider: str | None
    target_mode: str | None
    target_file_path: str | None
    fixed_preview_url: str | None
    adaptive_preview_url: str | None
    preview_token_hash: str | None
    artifact_zip_path: str | None
    artifact_repo_commit_url: str | None
    gitlab_app_project_id: str | None
    gitlab_issue_iid: int | None
    gitlab_issue_url: str | None
    gitlab_mr_iid: int | None
    gitlab_mr_url: str | None
    gitlab_source_branch: str | None
    publish_branch: str | None
    publish_pr_url: str | None
    publish_pr_number: int | None
    feedback_quality: Quality | None
    error_message: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: GenerationJobRow) -> GenerationJob:
        """Build a job from an ORM row."""
        feedback = row.feedback_quality
        return cls(
            id=row.id,
            run_id=row.run_id,
            figma_url=row.figma_url,
            discord_user_id=row.discord_user_id,
            discord_channel_id=row.discord_channel_id,
            discord_message_id=row.discord_message_id,
            review_message_id=row.review_message_id,
            project_dir=row.project_dir,
            feature_slug=row.feature_slug,
            status=JobStatus(row.status),
            repo_key=row.repo_key,
            git_provider=row.git_provider,
            target_mode=row.target_mode,
            target_file_path=row.target_file_path,
            fixed_preview_url=row.fixed_preview_url,
            adaptive_preview_url=row.adaptive_preview_url,
            preview_token_hash=row.preview_token_hash,
            artifact_zip_path=row.artifact_zip_path,
            artifact_repo_commit_url=row.artifact_repo_commit_url,
            gitlab_app_project_id=row.gitlab_app_project_id,
            gitlab_issue_iid=row.gitlab_issue_iid,
            gitlab_issue_url=row.gitlab_issue_url,
            gitlab_mr_iid=row.gitlab_mr_iid,
            gitlab_mr_url=row.gitlab_mr_url,
            gitlab_source_branch=row.gitlab_source_branch,
            publish_branch=row.publish_branch,
            publish_pr_url=row.publish_pr_url,
            publish_pr_number=row.publish_pr_number,
            feedback_quality=Quality(feedback) if feedback else None,
            error_message=row.error_message,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )


class JobStore:
    """Async PostgreSQL store for jobs and audit trail."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_job(
        self,
        *,
        job_id: str,
        figma_url: str,
        discord_user_id: int,
        discord_channel_id: int,
        project_dir: Path,
        gitlab_app_project_id: str = "",
        repo_key: str | None = None,
        git_provider: str | None = None,
        target_mode: str | None = None,
        target_file_path: str | None = None,
    ) -> GenerationJob:
        """Insert a new job in ``created`` status."""
        now = _utc_now()
        row = GenerationJobRow(
            id=job_id,
            figma_url=figma_url,
            discord_user_id=discord_user_id,
            discord_channel_id=discord_channel_id,
            project_dir=project_dir.as_posix(),
            status=JobStatus.CREATED.value,
            gitlab_app_project_id=gitlab_app_project_id or None,
            repo_key=repo_key,
            git_provider=git_provider,
            target_mode=target_mode,
            target_file_path=target_file_path,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return GenerationJob.from_row(row)

    async def get_job(self, job_id: str) -> GenerationJob | None:
        """Fetch one job by id."""
        async with self._session_factory() as session:
            row = await session.get(GenerationJobRow, job_id)
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def update_job(self, job_id: str, **fields: Any) -> GenerationJob | None:
        """Update arbitrary job columns."""
        if not fields:
            return await self.get_job(job_id)
        fields["updated_at"] = _utc_now()
        async with self._session_factory() as session:
            await session.execute(
                update(GenerationJobRow).where(GenerationJobRow.id == job_id).values(**fields)
            )
            await session.commit()
        return await self.get_job(job_id)

    async def list_jobs_by_status(self, *statuses: JobStatus) -> list[GenerationJob]:
        """Return jobs matching any of the given statuses."""
        if not statuses:
            return []
        values = [status.value for status in statuses]
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationJobRow)
                .where(GenerationJobRow.status.in_(values))
                .order_by(GenerationJobRow.created_at)
            )
            rows = result.scalars().all()
        return [GenerationJob.from_row(row) for row in rows]

    async def find_job_by_issue(
        self,
        project_id: str,
        issue_iid: int,
    ) -> GenerationJob | None:
        """Lookup job by GitLab issue."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationJobRow)
                .where(
                    GenerationJobRow.gitlab_app_project_id == project_id,
                    GenerationJobRow.gitlab_issue_iid == issue_iid,
                )
                .order_by(GenerationJobRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def find_job_by_branch(self, branch: str) -> GenerationJob | None:
        """Lookup job by publish or GitLab source branch name."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationJobRow)
                .where(
                    (GenerationJobRow.gitlab_source_branch == branch)
                    | (GenerationJobRow.publish_branch == branch)
                )
                .order_by(GenerationJobRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def find_job_by_mr(
        self,
        project_id: str,
        mr_iid: int,
    ) -> GenerationJob | None:
        """Lookup job by GitLab merge request."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationJobRow)
                .where(
                    GenerationJobRow.gitlab_app_project_id == project_id,
                    GenerationJobRow.gitlab_mr_iid == mr_iid,
                )
                .order_by(GenerationJobRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def find_open_publish_job(
        self,
        *,
        repo_key: str,
        target_file_path: str,
    ) -> GenerationJob | None:
        """Return the latest open publish job for the same screen target."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationJobRow)
                .where(
                    GenerationJobRow.repo_key == repo_key,
                    GenerationJobRow.target_file_path == target_file_path,
                    GenerationJobRow.publish_pr_url.is_not(None),
                    GenerationJobRow.status.in_(
                        [
                            JobStatus.MR_READY.value,
                            JobStatus.MR_CREATING.value,
                            JobStatus.ACCEPTED.value,
                        ]
                    ),
                )
                .order_by(GenerationJobRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def append_audit(
        self,
        *,
        job_id: str | None,
        discord_user_id: int | None,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Record an audit event."""
        event = AuditEventRow(
            job_id=job_id,
            discord_user_id=discord_user_id,
            action=action,
            payload=json.dumps(payload or {}, ensure_ascii=False),
            created_at=_utc_now(),
        )
        async with self._session_factory() as session:
            session.add(event)
            await session.commit()

    async def get_active_repo_key(self, discord_user_id: int, default: str) -> str:
        """Return the user's active repository key."""
        async with self._session_factory() as session:
            row = await session.get(UserPreferenceRow, discord_user_id)
        if row is not None:
            return row.active_repo_key
        return default

    async def set_active_repo_key(self, discord_user_id: int, repo_key: str) -> None:
        """Persist the user's active repository key."""
        now = _utc_now()
        async with self._session_factory() as session:
            row = await session.get(UserPreferenceRow, discord_user_id)
            if row is None:
                session.add(
                    UserPreferenceRow(
                        discord_user_id=discord_user_id,
                        active_repo_key=repo_key,
                        updated_at=now,
                    )
                )
            else:
                row.active_repo_key = repo_key
                row.updated_at = now
            await session.commit()


def job_marker(job_id: str) -> str:
    """Return an HTML comment marker embedded in Git descriptions."""
    return f"<!-- figma-flutter-agent-job: {job_id} -->"
