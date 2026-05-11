"""sync 010001 subject item templates

Revision ID: a7c9d2e4f601
Revises: e6c2f9a8d731
Create Date: 2026-05-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c9d2e4f601"
down_revision: str | Sequence[str] | None = "e6c2f9a8d731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_SUBJECT_ITEM_CODES = (
    "SCREENING_CONSENT",
    "SCREENING_ASSESSMENT",
    "SCREENING_CRITERIA",
    "ENROLLMENT_REGISTRATION",
    "BASELINE_INFORMATION",
    "EXAM_PREPARATION",
    "EXAM_EXECUTION_RECORD",
    "EXAM_RAW_DATA",
    "EXAM_SUMMARY",
    "EARLY_FOLLOWUP_RECORD",
    "ADVERSE_EVENT_CHECK",
    "EXCEPTION_HANDLING",
    "DELAYED_FOLLOWUP_RECORD",
    "COMPLETION_OR_EXIT",
    "DATA_COMPLETENESS_CONFIRM",
)

NEW_SUBJECT_ITEMS = (
    ("SCREENING", "知情同意书", "知情同意书", 0),
    ("SCREENING", "知情同意书交接表", "知情同意书交接表", 1),
    ("SCREENING", "生命体征记录表", "生命体征记录表", 2),
    ("SCREENING", "CT报告", "CT报告", 3),
    ("SCREENING", "胃肠镜检查报告", "胃肠镜检查报告", 4),
    ("SCREENING", "入组审核记录表", "入组审核记录表", 5),
    ("SCREENING", "其他辅助检查结果", "其他辅助检查结果", 6),
    ("SCREENING", "HIS记录", "HIS记录", 7),
    ("ENROLLMENT_PREP", "随机记录表", "随机记录表", 0),
    ("ENROLLMENT_PREP", "肠道准备情况", "肠道准备情况", 1),
    ("EXAM_EXECUTION", "舒适度评价表", "舒适度评价表", 0),
    ("EXAM_EXECUTION", "设备常用功能评价表", "设备常用功能评价表", 1),
    ("EXAM_EXECUTION", "图像质量评价表", "图像质量评价表", 2),
    ("EXAM_EXECUTION", "其他次要指标评价表", "其他次要指标评价表", 3),
    ("EXAM_EXECUTION", "胶囊内镜报告", "胶囊内镜报告", 4),
    ("DELAYED_FOLLOWUP", "X线检查报告", "X线检查报告", 0),
    ("COMPLETION", "中心阅片评价结果表", "中心阅片评价结果表", 0),
    ("COMPLETION", "安全事件", "安全事件", 1),
    ("COMPLETION", "器械缺陷", "器械缺陷", 2),
)


def upgrade() -> None:
    connection = op.get_bind()
    projects = connection.execute(sa.text("SELECT id FROM projects")).mappings().all()
    for project in projects:
        project_id = project["id"]
        stage_codes = tuple({item[0] for item in NEW_SUBJECT_ITEMS})
        stages = {
            row["code"]: row["id"]
            for row in connection.execute(
                sa.text(
                    """
                    SELECT id, code
                    FROM stages
                    WHERE project_id = :project_id
                      AND code IN :stage_codes
                    """
                ).bindparams(sa.bindparam("stage_codes", expanding=True)),
                {"project_id": project_id, "stage_codes": stage_codes},
            ).mappings()
        }

        for stage_code, item_name, item_code, sort_order in NEW_SUBJECT_ITEMS:
            stage_id = stages.get(stage_code)
            if stage_id is None:
                continue
            existing = connection.execute(
                sa.text(
                    """
                    SELECT id
                    FROM stage_templates
                    WHERE project_id = :project_id
                      AND stage_id = :stage_id
                      AND template_scope = 'subject_item'
                      AND item_code = :item_code
                    """
                ),
                {"project_id": project_id, "stage_id": stage_id, "item_code": item_code},
            ).scalar_one_or_none()
            if existing is None:
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO stage_templates (
                            project_id, stage_id, item_name, item_code, template_scope,
                            required, sort_order, recognition_keywords, description,
                            created_at, updated_at
                        )
                        VALUES (
                            :project_id, :stage_id, :item_name, :item_code, 'subject_item',
                            TRUE, :sort_order, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "project_id": project_id,
                        "stage_id": stage_id,
                        "item_name": item_name,
                        "item_code": item_code,
                        "sort_order": sort_order,
                    },
                )
            else:
                connection.execute(
                    sa.text(
                        """
                        UPDATE stage_templates
                        SET item_name = :item_name,
                            required = TRUE,
                            sort_order = :sort_order,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :template_id
                        """
                    ),
                    {
                        "template_id": existing,
                        "item_name": item_name,
                        "sort_order": sort_order,
                    },
                )

    connection.execute(
        sa.text(
            """
            DELETE FROM stage_templates
            WHERE template_scope = 'subject_item'
              AND item_code IN :old_codes
            """
        ).bindparams(sa.bindparam("old_codes", expanding=True)),
        {"old_codes": OLD_SUBJECT_ITEM_CODES},
    )


def downgrade() -> None:
    pass
