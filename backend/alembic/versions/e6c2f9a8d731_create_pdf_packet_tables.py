"""create pdf packet tables

Revision ID: e6c2f9a8d731
Revises: d5a8c4e1f630
Create Date: 2026-05-07 00:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6c2f9a8d731"
down_revision: str | Sequence[str] | None = "d5a8c4e1f630"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PDF_PACKET_PERMISSIONS = [
    {
        "code": "pdf_packets:read",
        "label": "查看PDF资料包",
        "module": "pdf_packets",
        "description": "",
    },
    {
        "code": "pdf_packets:write",
        "label": "处理PDF资料包",
        "module": "pdf_packets",
        "description": "",
    },
    {
        "code": "pdf_packets:delete",
        "label": "删除PDF资料包",
        "module": "pdf_packets",
        "description": "",
    },
]

DEFAULT_ROLE_PERMISSIONS = {
    "admin": ["pdf_packets:read", "pdf_packets:write", "pdf_packets:delete"],
    "project_manager": ["pdf_packets:read", "pdf_packets:write"],
    "center_manager": ["pdf_packets:read", "pdf_packets:write"],
    "clinical_coordinator": ["pdf_packets:read", "pdf_packets:write"],
    "reviewer": ["pdf_packets:read"],
    "rd_user": ["pdf_packets:read"],
    "readonly": ["pdf_packets:read"],
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "pdf_packets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("packet_id", sa.String(length=36), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("file_ext", sa.String(length=30), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("storage_type", sa.String(length=30), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("screening_no", sa.String(length=80), nullable=False),
        sa.Column("filename_screening_no", sa.String(length=80), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("packet_id"),
    )
    op.create_index(op.f("ix_pdf_packets_center_id"), "pdf_packets", ["center_id"], unique=False)
    op.create_index(
        op.f("ix_pdf_packets_filename_screening_no"),
        "pdf_packets",
        ["filename_screening_no"],
        unique=False,
    )
    op.create_index(op.f("ix_pdf_packets_id"), "pdf_packets", ["id"], unique=False)
    op.create_index(op.f("ix_pdf_packets_packet_id"), "pdf_packets", ["packet_id"], unique=True)
    op.create_index(op.f("ix_pdf_packets_project_id"), "pdf_packets", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_pdf_packets_screening_no"),
        "pdf_packets",
        ["screening_no"],
        unique=False,
    )
    op.create_index(op.f("ix_pdf_packets_subject_id"), "pdf_packets", ["subject_id"], unique=False)

    op.create_table(
        "pdf_packet_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("packet_id", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("detected_name", sa.String(length=150), nullable=True),
        sa.Column("detected_code", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("suggested_subject_item_id", sa.Integer(), nullable=True),
        sa.Column("subject_item_id", sa.Integer(), nullable=True),
        sa.Column("file_asset_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["file_asset_id"], ["files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["packet_id"], ["pdf_packets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_item_id"], ["subject_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["suggested_subject_item_id"],
            ["subject_items.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pdf_packet_segments_file_asset_id"),
        "pdf_packet_segments",
        ["file_asset_id"],
        unique=False,
    )
    op.create_index(op.f("ix_pdf_packet_segments_id"), "pdf_packet_segments", ["id"], unique=False)
    op.create_index(
        op.f("ix_pdf_packet_segments_packet_id"),
        "pdf_packet_segments",
        ["packet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pdf_packet_segments_subject_item_id"),
        "pdf_packet_segments",
        ["subject_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pdf_packet_segments_suggested_subject_item_id"),
        "pdf_packet_segments",
        ["suggested_subject_item_id"],
        unique=False,
    )

    with op.batch_alter_table("files") as batch_op:
        batch_op.add_column(sa.Column("source_pdf_packet_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_page_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_page_end", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_files_source_pdf_packet_id_pdf_packets",
            "pdf_packets",
            ["source_pdf_packet_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_files_source_pdf_packet_id", ["source_pdf_packet_id"])

    with op.batch_alter_table("stage_templates") as batch_op:
        batch_op.add_column(sa.Column("recognition_keywords", sa.Text(), nullable=True))

    ensure_pdf_packet_permissions()


def downgrade() -> None:
    """Downgrade schema."""
    remove_pdf_packet_permissions()
    with op.batch_alter_table("stage_templates") as batch_op:
        batch_op.drop_column("recognition_keywords")
    with op.batch_alter_table("files") as batch_op:
        batch_op.drop_index("ix_files_source_pdf_packet_id")
        batch_op.drop_constraint("fk_files_source_pdf_packet_id_pdf_packets", type_="foreignkey")
        batch_op.drop_column("source_page_end")
        batch_op.drop_column("source_page_start")
        batch_op.drop_column("source_pdf_packet_id")
    op.drop_index(
        op.f("ix_pdf_packet_segments_suggested_subject_item_id"),
        table_name="pdf_packet_segments",
    )
    op.drop_index(op.f("ix_pdf_packet_segments_subject_item_id"), table_name="pdf_packet_segments")
    op.drop_index(op.f("ix_pdf_packet_segments_packet_id"), table_name="pdf_packet_segments")
    op.drop_index(op.f("ix_pdf_packet_segments_id"), table_name="pdf_packet_segments")
    op.drop_index(op.f("ix_pdf_packet_segments_file_asset_id"), table_name="pdf_packet_segments")
    op.drop_table("pdf_packet_segments")
    op.drop_index(op.f("ix_pdf_packets_subject_id"), table_name="pdf_packets")
    op.drop_index(op.f("ix_pdf_packets_screening_no"), table_name="pdf_packets")
    op.drop_index(op.f("ix_pdf_packets_project_id"), table_name="pdf_packets")
    op.drop_index(op.f("ix_pdf_packets_packet_id"), table_name="pdf_packets")
    op.drop_index(op.f("ix_pdf_packets_id"), table_name="pdf_packets")
    op.drop_index(op.f("ix_pdf_packets_filename_screening_no"), table_name="pdf_packets")
    op.drop_index(op.f("ix_pdf_packets_center_id"), table_name="pdf_packets")
    op.drop_table("pdf_packets")


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


def ensure_pdf_packet_permissions() -> None:
    permissions, roles, role_permissions = permission_tables()
    bind = op.get_bind()
    permission_ids: dict[str, int] = {}
    for permission in PDF_PACKET_PERMISSIONS:
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
            existing = bind.scalar(
                sa.select(role_permissions.c.permission_id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            )
            if existing is None:
                bind.execute(
                    role_permissions.insert().values(
                        role_id=role_id,
                        permission_id=permission_id,
                    )
                )


def remove_pdf_packet_permissions() -> None:
    permissions, _, role_permissions = permission_tables()
    bind = op.get_bind()
    permission_ids = list(
        bind.scalars(
            sa.select(permissions.c.id).where(
                permissions.c.code.in_([item["code"] for item in PDF_PACKET_PERMISSIONS])
            )
        )
    )
    if not permission_ids:
        return
    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))
