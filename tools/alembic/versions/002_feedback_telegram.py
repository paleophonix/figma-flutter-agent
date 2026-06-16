"""Feedback comment, universal issue fields, Telegram user prefs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_feedback_telegram"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add feedback issue and Telegram preference columns."""
    op.add_column("generation_jobs", sa.Column("feedback_comment", sa.Text(), nullable=True))
    op.add_column(
        "generation_jobs",
        sa.Column("issue_provider", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("issue_project_ref", sa.String(length=256), nullable=True),
    )
    op.add_column("generation_jobs", sa.Column("issue_number", sa.Integer(), nullable=True))
    op.add_column("generation_jobs", sa.Column("issue_url", sa.Text(), nullable=True))
    op.create_index(
        "idx_generation_jobs_universal_issue",
        "generation_jobs",
        ["issue_provider", "issue_project_ref", "issue_number"],
    )

    op.add_column(
        "user_preferences",
        sa.Column(
            "telegram_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "user_preferences",
        sa.Column("telegram_channel_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "autoclose_mode",
            sa.String(length=32),
            nullable=False,
            server_default="developer",
        ),
    )

    op.execute(
        """
        UPDATE generation_jobs
        SET issue_provider = 'gitlab',
            issue_project_ref = gitlab_app_project_id,
            issue_number = gitlab_issue_iid,
            issue_url = gitlab_issue_url
        WHERE gitlab_issue_iid IS NOT NULL
          AND issue_number IS NULL
        """
    )


def downgrade() -> None:
    """Remove feedback issue and Telegram preference columns."""
    op.drop_column("user_preferences", "autoclose_mode")
    op.drop_column("user_preferences", "telegram_channel_key")
    op.drop_column("user_preferences", "telegram_enabled")
    op.drop_index("idx_generation_jobs_universal_issue", table_name="generation_jobs")
    op.drop_column("generation_jobs", "issue_url")
    op.drop_column("generation_jobs", "issue_number")
    op.drop_column("generation_jobs", "issue_project_ref")
    op.drop_column("generation_jobs", "issue_provider")
    op.drop_column("generation_jobs", "feedback_comment")
