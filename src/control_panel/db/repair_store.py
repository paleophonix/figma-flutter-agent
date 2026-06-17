"""PostgreSQL persistence for compiler auto-repair jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from control_panel.db.enums import RepairJobStatus, RepairStage
from control_panel.db.models import RepairJobRow


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class RepairJob:
    """Row model for ``repair_jobs``."""

    id: str
    status: RepairJobStatus
    stage: RepairStage | None
    parent_generation_job_id: str | None
    gitlab_project_id: str | None
    gitlab_issue_iid: int | None
    project_slug: str | None
    feature_slug: str | None
    flutter_project_dir: str | None
    worktree_path: str | None
    repair_ticket_json: str | None
    opencode_session_ids: dict[str, str]
    gitlab_mr_url: str | None
    gitlab_mr_iid: int | None
    principal: str | None
    origin: str
    error_message: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: RepairJobRow) -> RepairJob:
        """Build a repair job from an ORM row."""
        sessions: dict[str, str] = {}
        if row.opencode_session_ids:
            try:
                parsed = json.loads(row.opencode_session_ids)
                if isinstance(parsed, dict):
                    sessions = {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                sessions = {}
        stage = RepairStage(row.stage) if row.stage else None
        return cls(
            id=row.id,
            status=RepairJobStatus(row.status),
            stage=stage,
            parent_generation_job_id=row.parent_generation_job_id,
            gitlab_project_id=row.gitlab_project_id,
            gitlab_issue_iid=row.gitlab_issue_iid,
            project_slug=row.project_slug,
            feature_slug=row.feature_slug,
            flutter_project_dir=row.flutter_project_dir,
            worktree_path=row.worktree_path,
            repair_ticket_json=row.repair_ticket_json,
            opencode_session_ids=sessions,
            gitlab_mr_url=row.gitlab_mr_url,
            gitlab_mr_iid=row.gitlab_mr_iid,
            principal=row.principal,
            origin=row.origin,
            error_message=row.error_message,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )


class RepairJobStore:
    """CRUD for repair jobs."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_job(
        self,
        *,
        job_id: str,
        parent_generation_job_id: str | None = None,
        gitlab_project_id: str | None = None,
        gitlab_issue_iid: int | None = None,
        project_slug: str | None = None,
        feature_slug: str | None = None,
        flutter_project_dir: str | None = None,
        principal: str | None = None,
        origin: str = "api",
    ) -> RepairJob:
        """Insert a new repair job in ``queued`` status."""
        now = _utc_now()
        row = RepairJobRow(
            id=job_id,
            status=RepairJobStatus.QUEUED.value,
            parent_generation_job_id=parent_generation_job_id,
            gitlab_project_id=gitlab_project_id,
            gitlab_issue_iid=gitlab_issue_iid,
            project_slug=project_slug,
            feature_slug=feature_slug,
            flutter_project_dir=flutter_project_dir,
            principal=principal,
            origin=origin,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return RepairJob.from_row(row)

    async def get_job(self, job_id: str) -> RepairJob | None:
        """Fetch one repair job by id."""
        async with self._session_factory() as session:
            row = await session.get(RepairJobRow, job_id)
        if row is None:
            return None
        return RepairJob.from_row(row)

    async def update_job(self, job_id: str, **fields: Any) -> RepairJob | None:
        """Update arbitrary repair job columns."""
        if not fields:
            return await self.get_job(job_id)
        if "opencode_session_ids" in fields and isinstance(fields["opencode_session_ids"], dict):
            fields["opencode_session_ids"] = json.dumps(fields["opencode_session_ids"])
        if "status" in fields and isinstance(fields["status"], RepairJobStatus):
            fields["status"] = fields["status"].value
        if "stage" in fields and isinstance(fields["stage"], RepairStage):
            fields["stage"] = fields["stage"].value
        fields["updated_at"] = _utc_now()
        async with self._session_factory() as session:
            await session.execute(
                update(RepairJobRow).where(RepairJobRow.id == job_id).values(**fields)
            )
            await session.commit()
        return await self.get_job(job_id)

    async def list_jobs_by_principal(
        self,
        principal: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RepairJob]:
        """Return repair jobs owned by an API principal."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RepairJobRow)
                .where(RepairJobRow.principal == principal)
                .order_by(RepairJobRow.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = result.scalars().all()
        return [RepairJob.from_row(row) for row in rows]

    async def find_active_job(self) -> RepairJob | None:
        """Return a queued or running repair job if any (serial queue)."""
        active = (RepairJobStatus.QUEUED.value, RepairJobStatus.RUNNING.value)
        async with self._session_factory() as session:
            result = await session.execute(
                select(RepairJobRow)
                .where(RepairJobRow.status.in_(active))
                .order_by(RepairJobRow.created_at)
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return RepairJob.from_row(row)

    async def find_by_issue(
        self,
        project_id: str,
        issue_iid: int,
    ) -> RepairJob | None:
        """Lookup latest repair job for a GitLab issue."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RepairJobRow)
                .where(
                    RepairJobRow.gitlab_project_id == project_id,
                    RepairJobRow.gitlab_issue_iid == issue_iid,
                )
                .order_by(RepairJobRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return RepairJob.from_row(row)

    async def find_next_queued(self) -> RepairJob | None:
        """Return the oldest queued repair job (serial queue)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RepairJobRow)
                .where(RepairJobRow.status == RepairJobStatus.QUEUED.value)
                .order_by(RepairJobRow.created_at)
                .limit(1)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return RepairJob.from_row(row)

    async def count_by_status(self) -> dict[str, int]:
        """Return repair job counts grouped by status."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RepairJobRow.status, func.count()).group_by(RepairJobRow.status)
            )
            rows = result.all()
        return {str(status): int(count) for status, count in rows}

    async def count_queued(self) -> int:
        """Return the number of queued repair jobs."""
        counts = await self.count_by_status()
        return counts.get(RepairJobStatus.QUEUED.value, 0)
