"""create document extracted fields

Revision ID: 0f4e3d2c1b90
Revises: c4f7a2e9d610
Create Date: 2026-06-04 17:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0f4e3d2c1b90"
down_revision: str | Sequence[str] | None = "c4f7a2e9d610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_extracted_fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_version_id", sa.Integer(), nullable=True),
        sa.Column("pdf_packet_segment_id", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("field_label", sa.String(length=120), nullable=False),
        sa.Column("value_type", sa.String(length=30), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("source_page_no", sa.Integer(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("manually_edited", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_version_id"], ["file_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["pdf_packet_segment_id"],
            ["pdf_packet_segments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "file_version_id",
            "field_key",
            name="uq_document_fields_file_version_key",
        ),
        sa.UniqueConstraint(
            "pdf_packet_segment_id",
            "field_key",
            name="uq_document_fields_segment_key",
        ),
    )
    op.create_index(
        op.f("ix_document_extracted_fields_document_type"),
        "document_extracted_fields",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_extracted_fields_file_version_id"),
        "document_extracted_fields",
        ["file_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_extracted_fields_id"),
        "document_extracted_fields",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_extracted_fields_pdf_packet_segment_id"),
        "document_extracted_fields",
        ["pdf_packet_segment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_extracted_fields_pdf_packet_segment_id"),
        table_name="document_extracted_fields",
    )
    op.drop_index(op.f("ix_document_extracted_fields_id"), table_name="document_extracted_fields")
    op.drop_index(
        op.f("ix_document_extracted_fields_file_version_id"),
        table_name="document_extracted_fields",
    )
    op.drop_index(
        op.f("ix_document_extracted_fields_document_type"),
        table_name="document_extracted_fields",
    )
    op.drop_table("document_extracted_fields")
