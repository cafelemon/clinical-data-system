"""add subject arm and task state fields

Revision ID: 7e1c3f4a9b52
Revises: b2f0c7d8e9a1
Create Date: 2026-05-12 20:30:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "7e1c3f4a9b52"
down_revision = "b2f0c7d8e9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subjects", sa.Column("subject_arm", sa.String(length=20), nullable=True))
    op.add_column(
        "correction_tasks",
        sa.Column("previous_upload_status", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "correction_tasks",
        sa.Column("previous_review_status", sa.String(length=30), nullable=True),
    )
    op.create_index(
        "ix_correction_tasks_file_status",
        "correction_tasks",
        ["file_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_correction_tasks_file_status", table_name="correction_tasks")
    op.drop_column("correction_tasks", "previous_review_status")
    op.drop_column("correction_tasks", "previous_upload_status")
    op.drop_column("subjects", "subject_arm")
