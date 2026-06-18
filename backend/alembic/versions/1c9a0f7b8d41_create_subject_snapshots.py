"""create subject snapshots

Revision ID: 1c9a0f7b8d41
Revises: 7b6e9a1c2d44
Create Date: 2026-06-18 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1c9a0f7b8d41"
down_revision: str | Sequence[str] | None = "7b6e9a1c2d44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subject_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("screening_no_snapshot", sa.String(length=80), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=80),
            nullable=False,
            server_default="subject-snapshot-json/v0",
        ),
        sa.Column("snapshot_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "snapshot_type",
            sa.String(length=30),
            nullable=False,
            server_default="draft_snapshot",
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("generated_by", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "snapshot_type in ('draft_snapshot', 'released_snapshot')",
            name="ck_subject_snapshots_snapshot_type",
        ),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_id",
            "snapshot_version",
            name="uq_subject_snapshots_subject_version",
        ),
    )
    op.create_index(op.f("ix_subject_snapshots_center_id"), "subject_snapshots", ["center_id"])
    op.create_index(
        op.f("ix_subject_snapshots_generated_by"), "subject_snapshots", ["generated_by"]
    )
    op.create_index(op.f("ix_subject_snapshots_id"), "subject_snapshots", ["id"])
    op.create_index(op.f("ix_subject_snapshots_project_id"), "subject_snapshots", ["project_id"])
    op.create_index(
        op.f("ix_subject_snapshots_snapshot_type"),
        "subject_snapshots",
        ["snapshot_type"],
    )
    op.create_index(op.f("ix_subject_snapshots_status"), "subject_snapshots", ["status"])
    op.create_index(op.f("ix_subject_snapshots_subject_id"), "subject_snapshots", ["subject_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_subject_snapshots_subject_id"), table_name="subject_snapshots")
    op.drop_index(op.f("ix_subject_snapshots_status"), table_name="subject_snapshots")
    op.drop_index(op.f("ix_subject_snapshots_snapshot_type"), table_name="subject_snapshots")
    op.drop_index(op.f("ix_subject_snapshots_project_id"), table_name="subject_snapshots")
    op.drop_index(op.f("ix_subject_snapshots_id"), table_name="subject_snapshots")
    op.drop_index(op.f("ix_subject_snapshots_generated_by"), table_name="subject_snapshots")
    op.drop_index(op.f("ix_subject_snapshots_center_id"), table_name="subject_snapshots")
    op.drop_table("subject_snapshots")
