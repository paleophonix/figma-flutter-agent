"""Store Discord message id for user feedback comment."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_feedback_comment_message"
down_revision: str | None = "002_feedback_telegram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add feedback_comment_message_id for threaded close replies."""
    op.add_column(
        "generation_jobs",
        sa.Column("feedback_comment_message_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    """Remove feedback_comment_message_id."""
    op.drop_column("generation_jobs", "feedback_comment_message_id")
