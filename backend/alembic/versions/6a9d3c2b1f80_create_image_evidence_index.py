"""create image evidence index

Revision ID: 6a9d3c2b1f80
Revises: 4f8c2d1a9b33
Create Date: 2026-06-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6a9d3c2b1f80"
down_revision: str | Sequence[str] | None = "4f8c2d1a9b33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_evidence_index",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("subject_image_record_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("evidence_source", sa.String(length=80), nullable=True),
        sa.Column("relative_path", sa.Text(), nullable=True),
        sa.Column("match_status", sa.String(length=30), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("gastrointestinal_location", sa.String(length=120), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("indexed_by", sa.Integer(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
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
            "evidence_type in ("
            "'raw_package', 'enhanced_package', 'report_package', "
            "'report_image', 'marked_image', 'landmark_image'"
            ")",
            name="ck_image_evidence_index_evidence_type",
        ),
        sa.CheckConstraint(
            "match_status is null or match_status in ("
            "'resolved', 'approx_matched', 'unresolved', 'not_supported'"
            ")",
            name="ck_image_evidence_index_match_status",
        ),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["indexed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subject_image_record_id"],
            ["subject_image_records.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_image_evidence_index_center_id"),
        "image_evidence_index",
        ["center_id"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_evidence_source"),
        "image_evidence_index",
        ["evidence_source"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_evidence_type"),
        "image_evidence_index",
        ["evidence_type"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_gastrointestinal_location"),
        "image_evidence_index",
        ["gastrointestinal_location"],
    )
    op.create_index(op.f("ix_image_evidence_index_id"), "image_evidence_index", ["id"])
    op.create_index(
        op.f("ix_image_evidence_index_indexed_by"),
        "image_evidence_index",
        ["indexed_by"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_match_status"),
        "image_evidence_index",
        ["match_status"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_project_id"),
        "image_evidence_index",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_subject_id"),
        "image_evidence_index",
        ["subject_id"],
    )
    op.create_index(
        op.f("ix_image_evidence_index_subject_image_record_id"),
        "image_evidence_index",
        ["subject_image_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_image_evidence_index_subject_image_record_id"),
        table_name="image_evidence_index",
    )
    op.drop_index(op.f("ix_image_evidence_index_subject_id"), table_name="image_evidence_index")
    op.drop_index(op.f("ix_image_evidence_index_project_id"), table_name="image_evidence_index")
    op.drop_index(op.f("ix_image_evidence_index_match_status"), table_name="image_evidence_index")
    op.drop_index(op.f("ix_image_evidence_index_indexed_by"), table_name="image_evidence_index")
    op.drop_index(op.f("ix_image_evidence_index_id"), table_name="image_evidence_index")
    op.drop_index(
        op.f("ix_image_evidence_index_gastrointestinal_location"),
        table_name="image_evidence_index",
    )
    op.drop_index(op.f("ix_image_evidence_index_evidence_type"), table_name="image_evidence_index")
    op.drop_index(
        op.f("ix_image_evidence_index_evidence_source"),
        table_name="image_evidence_index",
    )
    op.drop_index(op.f("ix_image_evidence_index_center_id"), table_name="image_evidence_index")
    op.drop_table("image_evidence_index")
