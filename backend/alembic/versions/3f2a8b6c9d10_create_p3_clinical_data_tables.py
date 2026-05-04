"""create p3 clinical data tables

Revision ID: 3f2a8b6c9d10
Revises: a40faf22c17f
Create Date: 2026-05-04 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f2a8b6c9d10"
down_revision: str | Sequence[str] | None = "a40faf22c17f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("screening_no", sa.String(length=80), nullable=False),
        sa.Column("gender", sa.String(length=30), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("enrolled_at", sa.Date(), nullable=True),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("data_status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "center_id",
            "screening_no",
            name="uq_subjects_project_center_screening_no",
        ),
    )
    op.create_index(op.f("ix_subjects_center_id"), "subjects", ["center_id"], unique=False)
    op.create_index(op.f("ix_subjects_id"), "subjects", ["id"], unique=False)
    op.create_index(op.f("ix_subjects_project_id"), "subjects", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_subjects_screening_no"),
        "subjects",
        ["screening_no"],
        unique=False,
    )
    op.create_table(
        "subject_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("section_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("visit_name", sa.String(length=100), nullable=True),
        sa.Column("time_window", sa.String(length=100), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subject_id",
            "section_code",
            name="uq_subject_sections_subject_code",
        ),
    )
    op.create_index(
        op.f("ix_subject_sections_id"),
        "subject_sections",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subject_sections_project_id"),
        "subject_sections",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subject_sections_subject_id"),
        "subject_sections",
        ["subject_id"],
        unique=False,
    )
    op.create_table(
        "stage_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("stage_id", sa.Integer(), nullable=False),
        sa.Column("stage_template_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=150), nullable=False),
        sa.Column("file_type", sa.String(length=80), nullable=True),
        sa.Column("upload_status", sa.String(length=30), nullable=False),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["stage_template_id"],
            ["stage_templates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "center_id",
            "stage_id",
            "stage_template_id",
            name="uq_stage_files_template_scope",
        ),
    )
    op.create_index(op.f("ix_stage_files_center_id"), "stage_files", ["center_id"], unique=False)
    op.create_index(op.f("ix_stage_files_id"), "stage_files", ["id"], unique=False)
    op.create_index(op.f("ix_stage_files_project_id"), "stage_files", ["project_id"], unique=False)
    op.create_index(op.f("ix_stage_files_stage_id"), "stage_files", ["stage_id"], unique=False)
    op.create_index(
        op.f("ix_stage_files_stage_template_id"),
        "stage_files",
        ["stage_template_id"],
        unique=False,
    )
    op.create_table(
        "subject_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(length=150), nullable=False),
        sa.Column("item_code", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("upload_status", sa.String(length=30), nullable=False),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["section_id"], ["subject_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "item_code", name="uq_subject_items_subject_code"),
    )
    op.create_index(op.f("ix_subject_items_id"), "subject_items", ["id"], unique=False)
    op.create_index(
        op.f("ix_subject_items_section_id"),
        "subject_items",
        ["section_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subject_items_subject_id"),
        "subject_items",
        ["subject_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_subject_items_subject_id"), table_name="subject_items")
    op.drop_index(op.f("ix_subject_items_section_id"), table_name="subject_items")
    op.drop_index(op.f("ix_subject_items_id"), table_name="subject_items")
    op.drop_table("subject_items")
    op.drop_index(op.f("ix_stage_files_stage_template_id"), table_name="stage_files")
    op.drop_index(op.f("ix_stage_files_stage_id"), table_name="stage_files")
    op.drop_index(op.f("ix_stage_files_project_id"), table_name="stage_files")
    op.drop_index(op.f("ix_stage_files_id"), table_name="stage_files")
    op.drop_index(op.f("ix_stage_files_center_id"), table_name="stage_files")
    op.drop_table("stage_files")
    op.drop_index(op.f("ix_subject_sections_subject_id"), table_name="subject_sections")
    op.drop_index(op.f("ix_subject_sections_project_id"), table_name="subject_sections")
    op.drop_index(op.f("ix_subject_sections_id"), table_name="subject_sections")
    op.drop_table("subject_sections")
    op.drop_index(op.f("ix_subjects_screening_no"), table_name="subjects")
    op.drop_index(op.f("ix_subjects_project_id"), table_name="subjects")
    op.drop_index(op.f("ix_subjects_id"), table_name="subjects")
    op.drop_index(op.f("ix_subjects_center_id"), table_name="subjects")
    op.drop_table("subjects")
