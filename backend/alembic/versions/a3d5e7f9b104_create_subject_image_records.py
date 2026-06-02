"""create subject image records

Revision ID: a3d5e7f9b104
Revises: f2a4c6d8e013
Create Date: 2026-06-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3d5e7f9b104"
down_revision: str | Sequence[str] | None = "f2a4c6d8e013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subject_image_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("image_type", sa.String(length=30), nullable=False),
        sa.Column("screening_no_snapshot", sa.String(length=80), nullable=False),
        sa.Column(
            "upload_status",
            sa.String(length=30),
            nullable=False,
            server_default="not_uploaded",
        ),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column("stored_name", sa.String(length=255), nullable=True),
        sa.Column("file_ext", sa.String(length=30), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("extracted_dir", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_total_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("image_extensions_json", sa.JSON(), nullable=True),
        sa.Column("parse_warning", sa.Text(), nullable=True),
        sa.Column("source_raw_record_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("copied_by", sa.Integer(), nullable=True),
        sa.Column("copied_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["copied_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_raw_record_id"],
            ["subject_image_records.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_id",
            "image_type",
            name="uq_subject_image_records_subject_type",
        ),
    )
    op.create_index(
        op.f("ix_subject_image_records_center_id"),
        "subject_image_records",
        ["center_id"],
    )
    op.create_index(op.f("ix_subject_image_records_id"), "subject_image_records", ["id"])
    op.create_index(
        op.f("ix_subject_image_records_image_type"),
        "subject_image_records",
        ["image_type"],
    )
    op.create_index(
        op.f("ix_subject_image_records_project_id"),
        "subject_image_records",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_subject_image_records_source_raw_record_id"),
        "subject_image_records",
        ["source_raw_record_id"],
    )
    op.create_index(
        op.f("ix_subject_image_records_subject_id"),
        "subject_image_records",
        ["subject_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_subject_image_records_subject_id"), table_name="subject_image_records")
    op.drop_index(
        op.f("ix_subject_image_records_source_raw_record_id"),
        table_name="subject_image_records",
    )
    op.drop_index(
        op.f("ix_subject_image_records_project_id"),
        table_name="subject_image_records",
    )
    op.drop_index(
        op.f("ix_subject_image_records_image_type"),
        table_name="subject_image_records",
    )
    op.drop_index(op.f("ix_subject_image_records_id"), table_name="subject_image_records")
    op.drop_index(op.f("ix_subject_image_records_center_id"), table_name="subject_image_records")
    op.drop_table("subject_image_records")
