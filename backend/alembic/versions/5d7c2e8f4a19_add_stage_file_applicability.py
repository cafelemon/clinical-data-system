"""add stage file applicability

Revision ID: 5d7c2e8f4a19
Revises: 2f4a9c8d7e12
Create Date: 2026-05-25 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d7c2e8f4a19"
down_revision: str | Sequence[str] | None = "2f4a9c8d7e12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "stage_files",
        sa.Column(
            "not_applicable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("stage_files", sa.Column("not_applicable_reason", sa.Text(), nullable=True))
    op.add_column("stage_files", sa.Column("not_applicable_by", sa.Integer(), nullable=True))
    op.add_column(
        "stage_files",
        sa.Column("not_applicable_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_stage_files_not_applicable_by_users",
        "stage_files",
        "users",
        ["not_applicable_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("stage_files", "not_applicable", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_stage_files_not_applicable_by_users",
        "stage_files",
        type_="foreignkey",
    )
    op.drop_column("stage_files", "not_applicable_at")
    op.drop_column("stage_files", "not_applicable_by")
    op.drop_column("stage_files", "not_applicable_reason")
    op.drop_column("stage_files", "not_applicable")
