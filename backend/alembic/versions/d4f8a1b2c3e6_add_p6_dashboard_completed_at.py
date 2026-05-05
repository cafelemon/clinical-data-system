"""add p6 dashboard completed at

Revision ID: d4f8a1b2c3e6
Revises: c6b2f4e1a905
Create Date: 2026-05-05 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8a1b2c3e6"
down_revision: str | Sequence[str] | None = "c6b2f4e1a905"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("subjects", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            """
            update subjects
            set completed_at = updated_at
            where data_status = 'complete' and completed_at is null
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("subjects", "completed_at")
