"""SQLAlchemy ORM models for the control plane."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for control plane tables."""


class GenerationJobRow(Base):
    """Persisted generation job."""

    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    figma_url: Mapped[str] = mapped_column(Text, nullable=False)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discord_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discord_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    project_dir: Mapped[str] = mapped_column(Text, nullable=False)
    feature_slug: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    repo_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    git_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixed_preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    adaptive_preview_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_zip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_repo_commit_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitlab_app_project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gitlab_issue_iid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gitlab_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitlab_mr_iid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gitlab_mr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gitlab_source_branch: Mapped[str | None] = mapped_column(String(256), nullable=True)
    publish_branch: Mapped[str | None] = mapped_column(String(256), nullable=True)
    publish_pr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_quality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_comment_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issue_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issue_project_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class AuditEventRow(Base):
    """Audit trail row."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    discord_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class UserPreferenceRow(Base):
    """Per-Discord-user runtime preferences."""

    __tablename__ = "user_preferences"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active_repo_key: Mapped[str] = mapped_column(String(128), nullable=False)
    telegram_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    telegram_channel_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    autoclose_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="developer")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
