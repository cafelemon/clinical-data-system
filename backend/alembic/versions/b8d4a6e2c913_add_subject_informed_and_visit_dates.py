"""add subject informed and visit dates

Revision ID: b8d4a6e2c913
Revises: f7b1c2d3e4f5
Create Date: 2026-05-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4a6e2c913"
down_revision: str | Sequence[str] | None = "f7b1c2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "subjects",
        sa.Column("informed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column_name in (
        "visit1_date",
        "visit2_date",
        "visit3_date",
        "visit4_date",
        "visit5_date",
    ):
        op.add_column("subjects", sa.Column(column_name, sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for column_name in (
        "visit5_date",
        "visit4_date",
        "visit3_date",
        "visit2_date",
        "visit1_date",
    ):
        op.drop_column("subjects", column_name)
    op.drop_column("subjects", "informed_at")
