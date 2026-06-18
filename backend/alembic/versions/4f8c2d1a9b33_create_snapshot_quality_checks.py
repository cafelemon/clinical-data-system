"""create snapshot quality checks

Revision ID: 4f8c2d1a9b33
Revises: 1c9a0f7b8d41
Create Date: 2026-06-18 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4f8c2d1a9b33"
down_revision: str | Sequence[str] | None = "1c9a0f7b8d41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snapshot_quality_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("check_run_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("snapshot_type", sa.String(length=30), nullable=False),
        sa.Column("check_code", sa.String(length=80), nullable=False),
        sa.Column("check_status", sa.String(length=30), nullable=False),
        sa.Column("blocking", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "check_status in ('pass', 'warn', 'fail', 'not_supported')",
            name="ck_snapshot_quality_checks_status",
        ),
        sa.CheckConstraint(
            "snapshot_type in ('draft_snapshot', 'released_snapshot')",
            name="ck_snapshot_quality_checks_snapshot_type",
        ),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["subject_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_center_id"),
        "snapshot_quality_checks",
        ["center_id"],
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_check_code"),
        "snapshot_quality_checks",
        ["check_code"],
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_check_run_id"),
        "snapshot_quality_checks",
        ["check_run_id"],
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_check_status"),
        "snapshot_quality_checks",
        ["check_status"],
    )
    op.create_index(op.f("ix_snapshot_quality_checks_id"), "snapshot_quality_checks", ["id"])
    op.create_index(
        op.f("ix_snapshot_quality_checks_project_id"),
        "snapshot_quality_checks",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_snapshot_id"),
        "snapshot_quality_checks",
        ["snapshot_id"],
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_snapshot_type"),
        "snapshot_quality_checks",
        ["snapshot_type"],
    )
    op.create_index(
        op.f("ix_snapshot_quality_checks_subject_id"),
        "snapshot_quality_checks",
        ["subject_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_snapshot_quality_checks_subject_id"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(
        op.f("ix_snapshot_quality_checks_snapshot_type"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(
        op.f("ix_snapshot_quality_checks_snapshot_id"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(
        op.f("ix_snapshot_quality_checks_project_id"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(op.f("ix_snapshot_quality_checks_id"), table_name="snapshot_quality_checks")
    op.drop_index(
        op.f("ix_snapshot_quality_checks_check_status"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(
        op.f("ix_snapshot_quality_checks_check_run_id"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(
        op.f("ix_snapshot_quality_checks_check_code"),
        table_name="snapshot_quality_checks",
    )
    op.drop_index(
        op.f("ix_snapshot_quality_checks_center_id"),
        table_name="snapshot_quality_checks",
    )
    op.drop_table("snapshot_quality_checks")
