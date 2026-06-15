"""merge v3 trial cleanup and image data heads

Revision ID: c4f7a2e9d610
Revises: d1f0a4b9c322, a3d5e7f9b104
Create Date: 2026-06-02 10:10:00.000000
"""

from collections.abc import Sequence

revision: str = "c4f7a2e9d610"
down_revision: str | Sequence[str] | None = (
    "d1f0a4b9c322",
    "a3d5e7f9b104",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
