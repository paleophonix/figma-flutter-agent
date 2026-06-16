"""Initial control plane schema."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create control plane tables."""
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=128), nullable=True),
        sa.Column("figma_url", sa.Text(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_message_id", sa.BigInteger(), nullable=True),
        sa.Column("review_message_id", sa.BigInteger(), nullable=True),
        sa.Column("project_dir", sa.Text(), nullable=False),
        sa.Column("feature_slug", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("repo_key", sa.String(length=128), nullable=True),
        sa.Column("git_provider", sa.String(length=32), nullable=True),
        sa.Column("target_mode", sa.String(length=32), nullable=True),
        sa.Column("target_file_path", sa.Text(), nullable=True),
        sa.Column("fixed_preview_url", sa.Text(), nullable=True),
        sa.Column("adaptive_preview_url", sa.Text(), nullable=True),
        sa.Column("preview_token_hash", sa.String(length=128), nullable=True),
        sa.Column("artifact_zip_path", sa.Text(), nullable=True),
        sa.Column("artifact_repo_commit_url", sa.Text(), nullable=True),
        sa.Column("gitlab_app_project_id", sa.String(length=128), nullable=True),
        sa.Column("gitlab_issue_iid", sa.Integer(), nullable=True),
        sa.Column("gitlab_issue_url", sa.Text(), nullable=True),
        sa.Column("gitlab_mr_iid", sa.Integer(), nullable=True),
        sa.Column("gitlab_mr_url", sa.Text(), nullable=True),
        sa.Column("gitlab_source_branch", sa.String(length=256), nullable=True),
        sa.Column("publish_branch", sa.String(length=256), nullable=True),
        sa.Column("publish_pr_url", sa.Text(), nullable=True),
        sa.Column("publish_pr_number", sa.Integer(), nullable=True),
        sa.Column("feedback_quality", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_generation_jobs_status", "generation_jobs", ["status"])
    op.create_index("idx_generation_jobs_discord_user", "generation_jobs", ["discord_user_id"])
    op.create_index(
        "idx_generation_jobs_issue",
        "generation_jobs",
        ["gitlab_app_project_id", "gitlab_issue_iid"],
    )
    op.create_index(
        "idx_generation_jobs_mr",
        "generation_jobs",
        ["gitlab_app_project_id", "gitlab_mr_iid"],
    )
    op.create_index("idx_generation_jobs_branch", "generation_jobs", ["gitlab_source_branch"])
    op.create_index("idx_generation_jobs_publish_branch", "generation_jobs", ["publish_branch"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_events_job", "audit_events", ["job_id"])

    op.create_table(
        "user_preferences",
        sa.Column("discord_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("active_repo_key", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Drop control plane tables."""
    op.drop_table("user_preferences")
    op.drop_index("idx_audit_events_job", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("idx_generation_jobs_publish_branch", table_name="generation_jobs")
    op.drop_index("idx_generation_jobs_branch", table_name="generation_jobs")
    op.drop_index("idx_generation_jobs_mr", table_name="generation_jobs")
    op.drop_index("idx_generation_jobs_issue", table_name="generation_jobs")
    op.drop_index("idx_generation_jobs_discord_user", table_name="generation_jobs")
    op.drop_index("idx_generation_jobs_status", table_name="generation_jobs")
    op.drop_table("generation_jobs")
