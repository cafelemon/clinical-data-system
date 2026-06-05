"""add ssu progress file binding

Revision ID: 7b6e9a1c2d44
Revises: 0f4e3d2c1b90
Create Date: 2026-06-04 22:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b6e9a1c2d44"
down_revision: str | Sequence[str] | None = "0f4e3d2c1b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("files", sa.Column("ssu_progress_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_files_ssu_progress_id"),
        "files",
        ["ssu_progress_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_files_ssu_progress_id_clinical_ssu_progress"),
        "files",
        "clinical_ssu_progress",
        ["ssu_progress_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_files_ssu_progress_id_clinical_ssu_progress"),
        "files",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_files_ssu_progress_id"), table_name="files")
    op.drop_column("files", "ssu_progress_id")
