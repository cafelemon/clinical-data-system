"""create trial protocol versions

Revision ID: f2a4c6d8e013
Revises: 9c1e7a4b8d22
Create Date: 2026-06-01 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a4c6d8e013"
down_revision: str | Sequence[str] | None = "9c1e7a4b8d22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trial_protocol_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsing_status", sa.String(length=30), nullable=False, server_default="parsed"),
        sa.Column("protocol_no", sa.String(length=80), nullable=True),
        sa.Column("protocol_version", sa.String(length=80), nullable=True),
        sa.Column("protocol_date", sa.String(length=80), nullable=True),
        sa.Column("draft_json", sa.JSON(), nullable=False),
        sa.Column("apply_result_json", sa.JSON(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("applied_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["applied_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_trial_protocol_project_version"),
    )
    op.create_index(
        op.f("ix_trial_protocol_versions_id"),
        "trial_protocol_versions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trial_protocol_versions_project_id"),
        "trial_protocol_versions",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_trial_protocol_versions_project_id"), table_name="trial_protocol_versions")
    op.drop_index(op.f("ix_trial_protocol_versions_id"), table_name="trial_protocol_versions")
    op.drop_table("trial_protocol_versions")
