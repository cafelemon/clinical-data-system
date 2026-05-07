"""add subject delete permission

Revision ID: c3e7b9d5a214
Revises: b8d4a6e2c913
Create Date: 2026-05-06 00:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e7b9d5a214"
down_revision: str | Sequence[str] | None = "b8d4a6e2c913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBJECT_DELETE_PERMISSION = {
    "code": "clinical_data:delete",
    "label": "删除受试者",
    "module": "clinical_data",
    "description": "",
}


def upgrade() -> None:
    """Upgrade schema."""
    ensure_subject_delete_permission()


def downgrade() -> None:
    """Downgrade schema."""
    remove_subject_delete_permission()


def permission_tables():
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("module", sa.String),
        sa.column("description", sa.Text),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    return permissions, roles, role_permissions


def ensure_subject_delete_permission() -> None:
    permissions, roles, role_permissions = permission_tables()
    bind = op.get_bind()
    permission_id = bind.scalar(
        sa.select(permissions.c.id).where(
            permissions.c.code == SUBJECT_DELETE_PERMISSION["code"],
        )
    )
    if permission_id is None:
        bind.execute(permissions.insert().values(**SUBJECT_DELETE_PERMISSION))
        permission_id = bind.scalar(
            sa.select(permissions.c.id).where(
                permissions.c.code == SUBJECT_DELETE_PERMISSION["code"],
            )
        )
    admin_role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.name == "admin"))
    if admin_role_id is None or permission_id is None:
        return
    existing = bind.scalar(
        sa.select(role_permissions.c.permission_id).where(
            role_permissions.c.role_id == admin_role_id,
            role_permissions.c.permission_id == permission_id,
        )
    )
    if existing is None:
        bind.execute(
            role_permissions.insert().values(
                role_id=admin_role_id,
                permission_id=permission_id,
            )
        )


def remove_subject_delete_permission() -> None:
    permissions, _, role_permissions = permission_tables()
    bind = op.get_bind()
    permission_id = bind.scalar(
        sa.select(permissions.c.id).where(
            permissions.c.code == SUBJECT_DELETE_PERMISSION["code"],
        )
    )
    if permission_id is None:
        return
    bind.execute(
        role_permissions.delete().where(role_permissions.c.permission_id == permission_id)
    )
    bind.execute(permissions.delete().where(permissions.c.id == permission_id))
