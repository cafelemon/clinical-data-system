"""add stage template defaults initialized flag

Revision ID: d5a8c4e1f630
Revises: c3e7b9d5a214
Create Date: 2026-05-06 00:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a8c4e1f630"
down_revision: str | Sequence[str] | None = "c3e7b9d5a214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "projects",
        sa.Column(
            "stage_template_defaults_initialized",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute("update projects set stage_template_defaults_initialized = true")
    op.alter_column("projects", "stage_template_defaults_initialized", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "stage_template_defaults_initialized")
