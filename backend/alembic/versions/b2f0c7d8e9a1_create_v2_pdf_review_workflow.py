"""create v2 pdf review workflow

Revision ID: b2f0c7d8e9a1
Revises: a7c9d2e4f601
Create Date: 2026-05-12 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f0c7d8e9a1"
down_revision: str | Sequence[str] | None = "a7c9d2e4f601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

V2_PERMISSIONS = [
    {
        "code": "pdf_review:read",
        "label": "查看PDF在线审阅",
        "module": "pdf_review",
        "description": "",
    },
    {
        "code": "pdf_review:annotate",
        "label": "维护PDF批注",
        "module": "pdf_review",
        "description": "",
    },
    {
        "code": "pdf_review:manage",
        "label": "管理PDF审阅",
        "module": "pdf_review",
        "description": "",
    },
    {
        "code": "correction_tasks:read",
        "label": "查看整改任务",
        "module": "correction_tasks",
        "description": "",
    },
    {
        "code": "correction_tasks:create",
        "label": "创建整改任务",
        "module": "correction_tasks",
        "description": "",
    },
    {
        "code": "correction_tasks:submit",
        "label": "提交整改资料",
        "module": "correction_tasks",
        "description": "",
    },
    {
        "code": "correction_tasks:review",
        "label": "复审整改任务",
        "module": "correction_tasks",
        "description": "",
    },
]

DEFAULT_ROLE_PERMISSIONS = {
    "admin": [permission["code"] for permission in V2_PERMISSIONS],
    "project_manager": [permission["code"] for permission in V2_PERMISSIONS],
    "center_manager": [permission["code"] for permission in V2_PERMISSIONS],
    "clinical_coordinator": [
        "pdf_review:read",
        "correction_tasks:read",
        "correction_tasks:submit",
    ],
    "reviewer": [
        "pdf_review:read",
        "pdf_review:annotate",
        "correction_tasks:read",
        "correction_tasks:create",
        "correction_tasks:review",
    ],
    "rd_user": ["pdf_review:read"],
    "readonly": ["pdf_review:read"],
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pdf_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("file_version_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("subject_item_id", sa.Integer(), nullable=True),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("issue_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
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
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_version_id"], ["file_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_item_id"], ["subject_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pdf_annotations_center_id"), "pdf_annotations", ["center_id"])
    op.create_index(op.f("ix_pdf_annotations_file_id"), "pdf_annotations", ["file_id"])
    op.create_index(
        op.f("ix_pdf_annotations_file_version_id"),
        "pdf_annotations",
        ["file_version_id"],
    )
    op.create_index(op.f("ix_pdf_annotations_id"), "pdf_annotations", ["id"])
    op.create_index(op.f("ix_pdf_annotations_project_id"), "pdf_annotations", ["project_id"])
    op.create_index(op.f("ix_pdf_annotations_subject_id"), "pdf_annotations", ["subject_id"])
    op.create_index(
        op.f("ix_pdf_annotations_subject_item_id"),
        "pdf_annotations",
        ["subject_item_id"],
    )

    op.create_table(
        "correction_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_no", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("subject_item_id", sa.Integer(), nullable=True),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("source_file_version_id", sa.Integer(), nullable=False),
        sa.Column("latest_file_version_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_remark", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("review_result", sa.String(length=30), nullable=True),
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
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["latest_file_version_id"],
            ["file_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_file_version_id"],
            ["file_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_item_id"], ["subject_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_no"),
    )
    op.create_index(op.f("ix_correction_tasks_assigned_to"), "correction_tasks", ["assigned_to"])
    op.create_index(op.f("ix_correction_tasks_center_id"), "correction_tasks", ["center_id"])
    op.create_index(op.f("ix_correction_tasks_file_id"), "correction_tasks", ["file_id"])
    op.create_index(op.f("ix_correction_tasks_id"), "correction_tasks", ["id"])
    op.create_index(
        op.f("ix_correction_tasks_latest_file_version_id"),
        "correction_tasks",
        ["latest_file_version_id"],
    )
    op.create_index(op.f("ix_correction_tasks_project_id"), "correction_tasks", ["project_id"])
    op.create_index(
        op.f("ix_correction_tasks_source_file_version_id"),
        "correction_tasks",
        ["source_file_version_id"],
    )
    op.create_index(op.f("ix_correction_tasks_subject_id"), "correction_tasks", ["subject_id"])
    op.create_index(
        op.f("ix_correction_tasks_subject_item_id"),
        "correction_tasks",
        ["subject_item_id"],
    )
    op.create_index(
        op.f("ix_correction_tasks_task_no"),
        "correction_tasks",
        ["task_no"],
        unique=True,
    )

    op.create_table(
        "correction_task_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("annotation_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["annotation_id"], ["pdf_annotations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["correction_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "annotation_id", name="uq_correction_task_annotation"),
    )
    op.create_index(
        op.f("ix_correction_task_annotations_annotation_id"),
        "correction_task_annotations",
        ["annotation_id"],
    )
    op.create_index(
        op.f("ix_correction_task_annotations_id"),
        "correction_task_annotations",
        ["id"],
    )
    op.create_index(
        op.f("ix_correction_task_annotations_task_id"),
        "correction_task_annotations",
        ["task_id"],
    )

    ensure_v2_permissions()


def downgrade() -> None:
    """Downgrade schema."""
    remove_v2_permissions()
    op.drop_index(
        op.f("ix_correction_task_annotations_task_id"),
        table_name="correction_task_annotations",
    )
    op.drop_index(
        op.f("ix_correction_task_annotations_id"),
        table_name="correction_task_annotations",
    )
    op.drop_index(
        op.f("ix_correction_task_annotations_annotation_id"),
        table_name="correction_task_annotations",
    )
    op.drop_table("correction_task_annotations")
    op.drop_index(op.f("ix_correction_tasks_task_no"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_subject_item_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_subject_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_source_file_version_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_project_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_latest_file_version_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_file_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_center_id"), table_name="correction_tasks")
    op.drop_index(op.f("ix_correction_tasks_assigned_to"), table_name="correction_tasks")
    op.drop_table("correction_tasks")
    op.drop_index(op.f("ix_pdf_annotations_subject_item_id"), table_name="pdf_annotations")
    op.drop_index(op.f("ix_pdf_annotations_subject_id"), table_name="pdf_annotations")
    op.drop_index(op.f("ix_pdf_annotations_project_id"), table_name="pdf_annotations")
    op.drop_index(op.f("ix_pdf_annotations_id"), table_name="pdf_annotations")
    op.drop_index(op.f("ix_pdf_annotations_file_version_id"), table_name="pdf_annotations")
    op.drop_index(op.f("ix_pdf_annotations_file_id"), table_name="pdf_annotations")
    op.drop_index(op.f("ix_pdf_annotations_center_id"), table_name="pdf_annotations")
    op.drop_table("pdf_annotations")


def permission_tables():
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("module", sa.String),
        sa.column("description", sa.Text),
    )
    roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String))
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    return permissions, roles, role_permissions


def ensure_v2_permissions() -> None:
    permissions, roles, role_permissions = permission_tables()
    bind = op.get_bind()
    permission_ids: dict[str, int] = {}
    for permission in V2_PERMISSIONS:
        permission_id = bind.scalar(
            sa.select(permissions.c.id).where(permissions.c.code == permission["code"])
        )
        if permission_id is None:
            bind.execute(permissions.insert().values(**permission))
            permission_id = bind.scalar(
                sa.select(permissions.c.id).where(permissions.c.code == permission["code"])
            )
        if permission_id is not None:
            permission_ids[permission["code"]] = permission_id
    for role_name, codes in DEFAULT_ROLE_PERMISSIONS.items():
        role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.name == role_name))
        if role_id is None:
            continue
        for code in codes:
            permission_id = permission_ids.get(code)
            if permission_id is None:
                continue
            exists = bind.scalar(
                sa.select(role_permissions.c.role_id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            )
            if exists is None:
                bind.execute(
                    role_permissions.insert().values(
                        role_id=role_id,
                        permission_id=permission_id,
                    )
                )


def remove_v2_permissions() -> None:
    permissions, _, role_permissions = permission_tables()
    bind = op.get_bind()
    permission_ids = [
        permission_id
        for permission_id in bind.scalars(
            sa.select(permissions.c.id).where(
                permissions.c.code.in_([permission["code"] for permission in V2_PERMISSIONS])
            )
        )
    ]
    if permission_ids:
        bind.execute(
            role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids))
        )
        bind.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))
