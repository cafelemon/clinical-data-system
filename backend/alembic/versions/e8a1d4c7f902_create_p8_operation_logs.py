"""create p8 operation logs

Revision ID: e8a1d4c7f902
Revises: d4f8a1b2c3e6
Create Date: 2026-05-06 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8a1d4c7f902"
down_revision: str | Sequence[str] | None = "d4f8a1b2c3e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("center_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operation_logs_action"), "operation_logs", ["action"], unique=False)
    op.create_index(op.f("ix_operation_logs_center_id"), "operation_logs", ["center_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_created_at"), "operation_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_operation_logs_id"), "operation_logs", ["id"], unique=False)
    op.create_index(op.f("ix_operation_logs_project_id"), "operation_logs", ["project_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_target_id"), "operation_logs", ["target_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_target_type"), "operation_logs", ["target_type"], unique=False)
    op.create_index(op.f("ix_operation_logs_user_id"), "operation_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_operation_logs_username"), "operation_logs", ["username"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_operation_logs_username"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_user_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_target_type"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_target_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_project_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_created_at"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_center_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_action"), table_name="operation_logs")
    op.drop_table("operation_logs")
