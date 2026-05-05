"""create p5 review and completeness

Revision ID: c6b2f4e1a905
Revises: 78e42a9f0b31
Create Date: 2026-05-04 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6b2f4e1a905"
down_revision: str | Sequence[str] | None = "78e42a9f0b31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "subject_items",
        sa.Column("required", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.alter_column("subject_items", "required", server_default=None)
    op.create_table(
        "review_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("review_status", sa.String(length=30), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_records_id"), "review_records", ["id"], unique=False)
    op.create_index(
        op.f("ix_review_records_target_id"),
        "review_records",
        ["target_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_records_target_type"),
        "review_records",
        ["target_type"],
        unique=False,
    )
    _migrate_status_values()


def downgrade() -> None:
    """Downgrade schema."""
    _rollback_status_values()
    op.drop_index(op.f("ix_review_records_target_type"), table_name="review_records")
    op.drop_index(op.f("ix_review_records_target_id"), table_name="review_records")
    op.drop_index(op.f("ix_review_records_id"), table_name="review_records")
    op.drop_table("review_records")
    op.drop_column("subject_items", "required")


def _migrate_status_values() -> None:
    for table in ("subjects", "subject_items", "stage_files"):
        op.execute(
            sa.text(
                f"""
                update {table}
                set review_status = 'pending'
                where review_status = 'pending_review'
                """
            )
        )
    op.execute(
        sa.text(
            """
            update subjects
            set data_status = case data_status
                when 'not_started' then 'incomplete'
                when 'in_progress' then 'checking'
                else data_status
            end
            """
        )
    )


def _rollback_status_values() -> None:
    for table in ("subjects", "subject_items", "stage_files"):
        op.execute(
            sa.text(
                f"""
                update {table}
                set review_status = 'pending_review'
                where review_status = 'pending'
                """
            )
        )
    op.execute(
        sa.text(
            """
            update subjects
            set data_status = case data_status
                when 'incomplete' then 'not_started'
                when 'checking' then 'in_progress'
                else data_status
            end
            """
        )
    )
