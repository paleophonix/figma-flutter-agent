"""SQLite persistence for generation jobs and audit events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from discord_bot.db.enums import JobStatus, Quality

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
    feedback_quality: Quality | None
    error_message: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> GenerationJob:
        """Build a job from a SQLite row."""
        status = JobStatus(row["status"])
        feedback = row["feedback_quality"]
        return cls(
            id=row["id"],
            run_id=row["run_id"],
            figma_url=row["figma_url"],
            discord_user_id=row["discord_user_id"],
            discord_channel_id=row["discord_channel_id"],
            discord_message_id=row["discord_message_id"],
            review_message_id=row["review_message_id"],
            project_dir=row["project_dir"],
            feature_slug=row["feature_slug"],
            status=status,
            fixed_preview_url=row["fixed_preview_url"],
            adaptive_preview_url=row["adaptive_preview_url"],
            preview_token_hash=row["preview_token_hash"],
            artifact_zip_path=row["artifact_zip_path"],
            artifact_repo_commit_url=row["artifact_repo_commit_url"],
            gitlab_app_project_id=row["gitlab_app_project_id"],
            gitlab_issue_iid=row["gitlab_issue_iid"],
            gitlab_issue_url=row["gitlab_issue_url"],
            gitlab_mr_iid=row["gitlab_mr_iid"],
            gitlab_mr_url=row["gitlab_mr_url"],
            gitlab_source_branch=row["gitlab_source_branch"],
            feedback_quality=Quality(feedback) if feedback else None,
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class JobStore:
    """Async SQLite store for jobs and audit trail."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path.expanduser().resolve()

    @property
    def db_path(self) -> Path:
        """Return the database file path."""
        return self._db_path

    async def connect(self) -> aiosqlite.Connection:
        """Open a connection with schema applied."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        await conn.executescript(schema)
        await conn.commit()
        return conn

    async def create_job(
        self,
        *,
        job_id: str,
        figma_url: str,
        discord_user_id: int,
        discord_channel_id: int,
        project_dir: Path,
        gitlab_app_project_id: str,
    ) -> GenerationJob:
        """Insert a new job in ``created`` status."""
        now = _utc_now()
        async with await self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO generation_jobs (
                    id, figma_url, discord_user_id, discord_channel_id,
                    project_dir, status, gitlab_app_project_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    figma_url,
                    discord_user_id,
                    discord_channel_id,
                    project_dir.as_posix(),
                    JobStatus.CREATED.value,
                    gitlab_app_project_id,
                    now,
                    now,
                ),
            )
            await conn.commit()
        job = await self.get_job(job_id)
        assert job is not None
        return job

    async def get_job(self, job_id: str) -> GenerationJob | None:
        """Fetch one job by id."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM generation_jobs WHERE id = ?",
                (job_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def update_job(self, job_id: str, **fields: Any) -> GenerationJob | None:
        """Update arbitrary job columns."""
        if not fields:
            return await self.get_job(job_id)
        fields["updated_at"] = _utc_now()
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [job_id]
        async with await self.connect() as conn:
            await conn.execute(
                f"UPDATE generation_jobs SET {columns} WHERE id = ?",
                values,
            )
            await conn.commit()
        return await self.get_job(job_id)

    async def list_jobs_by_status(self, *statuses: JobStatus) -> list[GenerationJob]:
        """Return jobs matching any of the given statuses."""
        if not statuses:
            return []
        placeholders = ", ".join("?" for _ in statuses)
        values = [status.value for status in statuses]
        async with await self.connect() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM generation_jobs WHERE status IN ({placeholders}) ORDER BY created_at",
                values,
            )
            rows = await cursor.fetchall()
        return [GenerationJob.from_row(row) for row in rows]

    async def find_job_by_issue(
        self,
        project_id: str,
        issue_iid: int,
    ) -> GenerationJob | None:
        """Lookup job by GitLab issue."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM generation_jobs
                WHERE gitlab_app_project_id = ? AND gitlab_issue_iid = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id, issue_iid),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def find_job_by_branch(self, branch: str) -> GenerationJob | None:
        """Lookup job by GitLab source branch name."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM generation_jobs
                WHERE gitlab_source_branch = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (branch,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return GenerationJob.from_row(row)

    async def find_job_by_mr(
        self,
        project_id: str,
        mr_iid: int,
    ) -> GenerationJob | None:
        """Lookup job by GitLab merge request."""
        async with await self.connect() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM generation_jobs
                WHERE gitlab_app_project_id = ? AND gitlab_mr_iid = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id, mr_iid),
            )
            row = await cursor.fetchone()
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
        async with await self.connect() as conn:
            await conn.execute(
                """
                INSERT INTO audit_events (job_id, discord_user_id, action, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    discord_user_id,
                    action,
                    json.dumps(payload or {}, ensure_ascii=False),
                    _utc_now(),
                ),
            )
            await conn.commit()


def job_marker(job_id: str) -> str:
    """Return an HTML comment marker embedded in GitLab descriptions."""
    return f"<!-- figma-flutter-agent-job: {job_id} -->"
