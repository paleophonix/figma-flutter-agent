"""Add origin/principal and nullable Discord columns."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_origin_principal"
down_revision: str | None = "004_issue_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add api-origin fields and relax Discord column nullability."""
    op.add_column(
        "generation_jobs",
        sa.Column("origin", sa.String(length=16), nullable=False, server_default="discord"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("principal", sa.String(length=128), nullable=True),
    )
    op.alter_column("generation_jobs", "discord_user_id", existing_type=sa.BigInteger(), nullable=True)
    op.alter_column("generation_jobs", "discord_channel_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    """Revert origin/principal and Discord nullability."""
    op.alter_column("generation_jobs", "discord_channel_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("generation_jobs", "discord_user_id", existing_type=sa.BigInteger(), nullable=False)
    op.drop_column("generation_jobs", "principal")
    op.drop_column("generation_jobs", "origin")
