"""Store tracker issue kind (bug vs feat)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_issue_kind"
down_revision: str | None = "003_feedback_comment_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add issue_kind for close routing."""
    op.add_column(
        "generation_jobs",
        sa.Column("issue_kind", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    """Remove issue_kind."""
    op.drop_column("generation_jobs", "issue_kind")
