"""remove legacy trial subject stages

Revision ID: d1f0a4b9c322
Revises: 9c1e7a4b8d22
Create Date: 2026-05-25 21:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f0a4b9c322"
down_revision: str | Sequence[str] | None = "9c1e7a4b8d22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_TRIAL_STAGE_CODES = (
    "SCREENING",
    "ENROLLMENT_PREP",
    "EXAM_EXECUTION",
    "EARLY_FOLLOWUP",
    "DELAYED_FOLLOWUP",
    "COMPLETION",
)

ARM_SPECIFIC_DESTINATIONS = {
    "肠道准备情况": {
        "experimental": "V2_BOWEL_PREPARATION",
        "control": "V3_BOWEL_PREPARATION",
    },
    "舒适度评价表": {
        "experimental": "V2_PRIMARY_ENDPOINT_RESULT",
        "control": "V3_PRIMARY_ENDPOINT_RESULT",
    },
    "设备常用功能评价表": {
        "experimental": "V2_PRIMARY_ENDPOINT_RESULT",
        "control": "V3_PRIMARY_ENDPOINT_RESULT",
    },
    "图像质量评价表": {
        "experimental": "V2_PRIMARY_ENDPOINT_RESULT",
        "control": "V3_PRIMARY_ENDPOINT_RESULT",
    },
    "其他次要指标评价表": {
        "experimental": "V2_SECONDARY_ENDPOINT_RESULT",
        "control": "V3_SECONDARY_ENDPOINT_RESULT",
    },
    "中心阅片评价结果表": {
        "experimental": "V2_PRIMARY_ENDPOINT_RESULT",
        "control": "V3_PRIMARY_ENDPOINT_RESULT",
    },
}

FIXED_DESTINATIONS = {
    "知情同意书": "V1_INFORMED_CONSENT",
    "知情同意书交接表": "V1_INFORMED_CONSENT_HANDOVER",
    "知情同意书交接表（若有）": "V1_INFORMED_CONSENT_HANDOVER",
    "生命体征记录": "V1_VITAL_SIGNS",
    "生命体征记录表": "V1_VITAL_SIGNS",
    "CT报告": "V1_CT_REPORT",
    "CT检查报告": "V1_CT_REPORT",
    "胃肠镜检查报告": "V1_GASTROINTESTINAL_ENDOSCOPY_REPORT",
    "入组审核记录表": "V1_ENROLLMENT_REVIEW",
    "其他辅助检查结果": "V1_AUXILIARY_EXAM_RESULTS",
    "HIS记录": "V1_HIS_DESCRIPTION",
    "HIS描述": "V1_HIS_DESCRIPTION",
    "随机记录表": "V1_RANDOMIZATION_PACKET",
    "随机记录包": "V1_RANDOMIZATION_PACKET",
    "随机记录包（若有）": "V1_RANDOMIZATION_PACKET",
    "胶囊内镜报告": "V2_CAPSULE_ENDOSCOPY_REPORT",
    "对照组报告": "V3_CONTROL_REPORT",
}


def upgrade() -> None:
    connection = op.get_bind()
    _clear_review_tasks_and_annotations(connection)
    _move_legacy_subject_files(connection)
    _delete_legacy_stage_records(connection)


def downgrade() -> None:
    pass


def _clear_review_tasks_and_annotations(connection) -> None:
    connection.execute(sa.text("DELETE FROM correction_task_annotations"))
    connection.execute(sa.text("DELETE FROM correction_tasks"))
    connection.execute(sa.text("DELETE FROM pdf_annotations"))


def _move_legacy_subject_files(connection) -> None:
    legacy_items = connection.execute(
        sa.text(
            """
            SELECT
                subject_items.id AS old_item_id,
                subject_items.subject_id AS subject_id,
                subject_items.item_name AS item_name,
                subject_sections.section_code AS section_code,
                subjects.subject_arm AS subject_arm
            FROM subject_items
            JOIN subject_sections ON subject_sections.id = subject_items.section_id
            JOIN subjects ON subjects.id = subject_items.subject_id
            WHERE subject_sections.section_code IN :old_codes
            ORDER BY subject_items.id
            """
        ).bindparams(sa.bindparam("old_codes", expanding=True)),
        {"old_codes": OLD_TRIAL_STAGE_CODES},
    ).mappings()

    old_item_ids: list[int] = []
    moved_destination_ids: set[int] = set()
    for legacy_item in legacy_items:
        old_item_id = legacy_item["old_item_id"]
        old_item_ids.append(old_item_id)
        destination_code = _destination_code_for(
            legacy_item["item_name"],
            legacy_item["section_code"],
            legacy_item["subject_arm"],
        )
        if destination_code is None:
            continue
        destination_item = connection.execute(
            sa.text(
                """
                SELECT id
                FROM subject_items
                WHERE subject_id = :subject_id AND item_code = :item_code
                """
            ),
            {"subject_id": legacy_item["subject_id"], "item_code": destination_code},
        ).mappings().first()
        if destination_item is None:
            continue

        new_item_id = destination_item["id"]
        moved_destination_ids.add(new_item_id)
        connection.execute(
            sa.text(
                """
                UPDATE files
                SET subject_item_id = :new_item_id,
                    subject_id = :subject_id,
                    stage_id = NULL,
                    stage_file_id = NULL
                WHERE subject_item_id = :old_item_id
                """
            ),
            {
                "new_item_id": new_item_id,
                "subject_id": legacy_item["subject_id"],
                "old_item_id": old_item_id,
            },
        )
        connection.execute(
            sa.text(
                """
                UPDATE pdf_packet_segments
                SET subject_item_id = :new_item_id
                WHERE subject_item_id = :old_item_id
                """
            ),
            {"new_item_id": new_item_id, "old_item_id": old_item_id},
        )
        connection.execute(
            sa.text(
                """
                UPDATE pdf_packet_segments
                SET suggested_subject_item_id = :new_item_id
                WHERE suggested_subject_item_id = :old_item_id
                """
            ),
            {"new_item_id": new_item_id, "old_item_id": old_item_id},
        )

    if old_item_ids:
        connection.execute(
            sa.text(
                """
                DELETE FROM review_records
                WHERE target_type = 'subject_item' AND target_id IN :old_item_ids
                """
            ).bindparams(sa.bindparam("old_item_ids", expanding=True)),
            {"old_item_ids": old_item_ids},
        )
    for item_id in moved_destination_ids:
        connection.execute(
            sa.text(
                """
                UPDATE subject_items
                SET upload_status = CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM files
                            WHERE files.subject_item_id = subject_items.id
                              AND files.status = 'active'
                        )
                        THEN 'uploaded'
                        ELSE 'not_uploaded'
                    END,
                    review_status = 'unreviewed',
                    remark = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :item_id
                """
            ),
            {"item_id": item_id},
        )


def _destination_code_for(item_name: str, section_code: str, subject_arm: str | None) -> str | None:
    normalized_name = item_name.strip()
    if section_code == "SCREENING" and normalized_name == "HIS记录":
        return "V1_HIS_DESCRIPTION"
    if normalized_name in ARM_SPECIFIC_DESTINATIONS:
        arm = "control" if subject_arm == "control" else "experimental"
        return ARM_SPECIFIC_DESTINATIONS[normalized_name][arm]
    return FIXED_DESTINATIONS.get(normalized_name)


def _delete_legacy_stage_records(connection) -> None:
    old_stage_ids = list(
        connection.execute(
            sa.text("SELECT id FROM stages WHERE code IN :old_codes").bindparams(
                sa.bindparam("old_codes", expanding=True)
            ),
            {"old_codes": OLD_TRIAL_STAGE_CODES},
        ).scalars()
    )
    old_section_ids = list(
        connection.execute(
            sa.text("SELECT id FROM subject_sections WHERE section_code IN :old_codes").bindparams(
                sa.bindparam("old_codes", expanding=True)
            ),
            {"old_codes": OLD_TRIAL_STAGE_CODES},
        ).scalars()
    )
    if old_stage_ids:
        old_stage_file_ids = list(
            connection.execute(
                sa.text("SELECT id FROM stage_files WHERE stage_id IN :old_stage_ids").bindparams(
                    sa.bindparam("old_stage_ids", expanding=True)
                ),
                {"old_stage_ids": old_stage_ids},
            ).scalars()
        )
        if old_stage_file_ids:
            connection.execute(
                sa.text(
                    """
                    DELETE FROM review_records
                    WHERE target_type = 'stage_file' AND target_id IN :old_stage_file_ids
                    """
                ).bindparams(sa.bindparam("old_stage_file_ids", expanding=True)),
                {"old_stage_file_ids": old_stage_file_ids},
            )
        connection.execute(
            sa.text("DELETE FROM stage_files WHERE stage_id IN :old_stage_ids").bindparams(
                sa.bindparam("old_stage_ids", expanding=True)
            ),
            {"old_stage_ids": old_stage_ids},
        )
        connection.execute(
            sa.text("DELETE FROM stage_templates WHERE stage_id IN :old_stage_ids").bindparams(
                sa.bindparam("old_stage_ids", expanding=True)
            ),
            {"old_stage_ids": old_stage_ids},
        )
    if old_section_ids:
        connection.execute(
            sa.text("DELETE FROM subject_items WHERE section_id IN :old_section_ids").bindparams(
                sa.bindparam("old_section_ids", expanding=True)
            ),
            {"old_section_ids": old_section_ids},
        )
        connection.execute(
            sa.text("DELETE FROM subject_sections WHERE id IN :old_section_ids").bindparams(
                sa.bindparam("old_section_ids", expanding=True)
            ),
            {"old_section_ids": old_section_ids},
        )
    if old_stage_ids:
        connection.execute(
            sa.text("DELETE FROM stages WHERE id IN :old_stage_ids").bindparams(
                sa.bindparam("old_stage_ids", expanding=True)
            ),
            {"old_stage_ids": old_stage_ids},
        )
