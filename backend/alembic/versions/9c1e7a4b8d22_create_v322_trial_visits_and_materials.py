"""create v322 trial visits and materials

Revision ID: 9c1e7a4b8d22
Revises: 5d7c2e8f4a19
Create Date: 2026-05-25 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c1e7a4b8d22"
down_revision: str | Sequence[str] | None = "5d7c2e8f4a19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PARENT_STAGES = (
    ("STARTUP", "试验准备阶段", 1, "试验准备资料、SSU进展和启动会相关资料。"),
    ("TRIAL", "试验进行阶段", 2, "试验进行资料准备和受试者试验实施访视资料。"),
    ("CLOSEOUT", "试验结束阶段", 3, "试验完成、终止后资料准备和归档资料。"),
)

TRIAL_STAGE_OPTIONS = (
    ("TRIAL_MATERIALS", "资料准备", 1, "试验进行阶段中心级资料准备。"),
    ("V1_SCREENING_VISIT", "V1筛选访视阶段", 2, "完成知情同意、筛选评估和入组前资料收集。"),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2试验组随访访视", 3, "完成试验组随访访视资料收集。"),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3对照组随访访视（若有）", 4, "完成对照组随访访视资料收集。"),
    ("V4_UNSCHEDULED_VISIT", "V4非预期访视（若有）", 5, "按需记录非预期访视资料。"),
)

OLD_TRIAL_STAGE_CODES = (
    "SCREENING",
    "ENROLLMENT_PREP",
    "EXAM_EXECUTION",
    "EARLY_FOLLOWUP",
    "DELAYED_FOLLOWUP",
    "COMPLETION",
)

TRIAL_MATERIAL_TEMPLATES = (
    ("TRIAL_027_INVESTIGATOR_BROCHURE_UPDATE", "研究者手册更新件（若有）", 27, False),
    ("TRIAL_028_PROTOCOL_UPDATE", "临床试验方案更新件（若有）", 28, False),
    (
        "TRIAL_029_OTHER_DOCUMENT_UPDATES",
        "其他文件（病例报告表、知情同意书、书面情况通知）的更新（若有）",
        29,
        False,
    ),
    ("TRIAL_030_PRODUCT_TEST_REPORT_UPDATE", "试验医疗器械产品检验报告的更新（若有）", 30, False),
    ("TRIAL_031_ETHICS_UPDATE_OPINION", "伦理委员会对更新文件的书面审查意见（若有）", 31, False),
    ("TRIAL_032_INVESTIGATOR_QUALIFICATION_UPDATE", "研究者简历以及资格证明文件的更新（若有）", 32, False),
    ("TRIAL_033_LAB_NORMAL_RANGE_UPDATE", "临床试验有关的实验室检测正常值范围更新（若有）", 33, False),
    ("TRIAL_034_LAB_QC_CERTIFICATE_UPDATE", "医学或者实验室室间质控证明更新（若有）", 34, False),
    ("TRIAL_035_DEVICE_HANDOVER", "试验医疗器械与试验相关物资的交接单（若有）", 35, False),
    ("TRIAL_036_SIGNED_INFORMED_CONSENT", "已签名的知情同意书（若有）", 36, False),
    ("TRIAL_037_SOURCE_MEDICAL_DOCUMENTS", "原始医疗文件（若有）", 37, False),
    ("TRIAL_038_SIGNED_CRF", "已填并签字的病例报告表", 38, True),
    ("TRIAL_039_INVESTIGATOR_SAE_REPORT", "研究者对严重不良事件的报告（若有）", 39, False),
    (
        "TRIAL_040_SPONSOR_DEVICE_RELATED_SAE_REPORT",
        "申办者对试验医疗器械相关严重不良事件的报告（若有）",
        40,
        False,
    ),
    ("TRIAL_041_OTHER_SAFETY_RISK_REPORT", "其他严重安全性风险信息的报告（若有）", 41, False),
    ("TRIAL_042_SUBJECT_IDENTIFICATION_CODE_LIST", "受试者鉴认代码表", 42, True),
    ("TRIAL_043_SUBJECT_SCREENING_AND_ENROLLMENT_TABLE", "受试者筛选表与入选表", 43, True),
    ("TRIAL_044_SIGNATURE_AUTHORIZATION_UPDATE", "研究者签名样张以及研究者授权表更新文件（若有）", 44, False),
    ("TRIAL_045_MONITORING_REPORT", "监查员监查报告", 45, True),
)

SUBJECT_ITEM_TEMPLATES = (
    ("V1_SCREENING_VISIT", "V1_INFORMED_CONSENT", "知情同意书", 0, True),
    ("V1_SCREENING_VISIT", "V1_INFORMED_CONSENT_HANDOVER", "知情同意书交接表（若有）", 1, False),
    ("V1_SCREENING_VISIT", "V1_VITAL_SIGNS", "生命体征记录", 2, True),
    ("V1_SCREENING_VISIT", "V1_CT_REPORT", "CT检查报告", 3, True),
    ("V1_SCREENING_VISIT", "V1_GASTROINTESTINAL_ENDOSCOPY_REPORT", "胃肠镜检查报告", 4, True),
    ("V1_SCREENING_VISIT", "V1_ENROLLMENT_REVIEW", "入组审核记录表", 5, True),
    ("V1_SCREENING_VISIT", "V1_AUXILIARY_EXAM_RESULTS", "其他辅助检查结果", 6, True),
    ("V1_SCREENING_VISIT", "V1_HIS_DESCRIPTION", "HIS描述", 7, True),
    ("V1_SCREENING_VISIT", "V1_RANDOMIZATION_PACKET", "随机记录包（若有）", 8, False),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2_VITAL_SIGNS", "生命体征记录", 0, True),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2_BOWEL_PREPARATION", "肠道准备情况", 1, True),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2_HIS_DESCRIPTION", "HIS描述", 2, True),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2_PRIMARY_ENDPOINT_RESULT", "主要评价指标结果（若有）", 3, False),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2_SECONDARY_ENDPOINT_RESULT", "次要评价指标结果（若有）", 4, False),
    ("V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V2_CAPSULE_ENDOSCOPY_REPORT", "胶囊内镜报告", 5, True),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3_VITAL_SIGNS", "生命体征记录", 0, True),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3_BOWEL_PREPARATION", "肠道准备情况", 1, True),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3_HIS_DESCRIPTION", "HIS描述", 2, True),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3_PRIMARY_ENDPOINT_RESULT", "主要评价指标结果（若有）", 3, False),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3_SECONDARY_ENDPOINT_RESULT", "次要评价指标结果（若有）", 4, False),
    ("V3_CONTROL_FOLLOWUP_VISIT", "V3_CONTROL_REPORT", "对照组报告", 5, True),
    ("V4_UNSCHEDULED_VISIT", "V4_HIS_RECORD", "HIS记录", 0, False),
)

VISITS_BY_ARM = {
    "control": ("V1_SCREENING_VISIT", "V3_CONTROL_FOLLOWUP_VISIT", "V4_UNSCHEDULED_VISIT"),
    "experimental": (
        "V1_SCREENING_VISIT",
        "V2_EXPERIMENTAL_FOLLOWUP_VISIT",
        "V4_UNSCHEDULED_VISIT",
    ),
}


def upgrade() -> None:
    connection = op.get_bind()
    projects = connection.execute(sa.text("SELECT id FROM projects")).mappings().all()
    for project in projects:
        project_id = project["id"]
        parent_ids = _ensure_parent_stages(connection, project_id)
        stage_ids = _ensure_trial_child_stages(connection, project_id, parent_ids["TRIAL"])
        _disable_old_trial_stages(connection, project_id)
        _ensure_trial_material_templates(connection, project_id, stage_ids["TRIAL_MATERIALS"])
        _ensure_subject_item_templates(connection, project_id, stage_ids)
        _ensure_subject_visit_records(connection, project_id, stage_ids)


def downgrade() -> None:
    pass


def _ensure_parent_stages(connection, project_id: int) -> dict[str, int]:
    parent_ids = {}
    for code, name, sort_order, description in PARENT_STAGES:
        stage_id = connection.execute(
            sa.text("SELECT id FROM stages WHERE project_id = :project_id AND code = :code"),
            {"project_id": project_id, "code": code},
        ).scalar_one_or_none()
        if stage_id is None:
            stage_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO stages (
                        project_id, name, code, parent_id, phase_code, option_code, is_system,
                        enabled, sort_order, description, created_at, updated_at
                    )
                    VALUES (
                        :project_id, :name, :code, NULL, :code, NULL, TRUE, TRUE,
                        :sort_order, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """
                ),
                {
                    "project_id": project_id,
                    "name": name,
                    "code": code,
                    "sort_order": sort_order,
                    "description": description,
                },
            ).scalar_one()
        else:
            connection.execute(
                sa.text(
                    """
                    UPDATE stages
                    SET name = :name,
                        parent_id = NULL,
                        phase_code = :code,
                        option_code = NULL,
                        is_system = TRUE,
                        enabled = TRUE,
                        sort_order = :sort_order,
                        description = :description,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :stage_id
                    """
                ),
                {
                    "stage_id": stage_id,
                    "name": name,
                    "code": code,
                    "sort_order": sort_order,
                    "description": description,
                },
            )
        parent_ids[code] = stage_id
    return parent_ids


def _ensure_trial_child_stages(connection, project_id: int, parent_id: int) -> dict[str, int]:
    stage_ids = {}
    for code, name, sort_order, description in TRIAL_STAGE_OPTIONS:
        stage_id = connection.execute(
            sa.text("SELECT id FROM stages WHERE project_id = :project_id AND code = :code"),
            {"project_id": project_id, "code": code},
        ).scalar_one_or_none()
        if stage_id is None:
            stage_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO stages (
                        project_id, name, code, parent_id, phase_code, option_code, is_system,
                        enabled, sort_order, description, created_at, updated_at
                    )
                    VALUES (
                        :project_id, :name, :code, :parent_id, 'TRIAL', :code, FALSE, TRUE,
                        :sort_order, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """
                ),
                {
                    "project_id": project_id,
                    "name": name,
                    "code": code,
                    "parent_id": parent_id,
                    "sort_order": sort_order,
                    "description": description,
                },
            ).scalar_one()
        else:
            connection.execute(
                sa.text(
                    """
                    UPDATE stages
                    SET name = :name,
                        parent_id = :parent_id,
                        phase_code = 'TRIAL',
                        option_code = :code,
                        enabled = TRUE,
                        sort_order = :sort_order,
                        description = :description,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :stage_id
                    """
                ),
                {
                    "stage_id": stage_id,
                    "name": name,
                    "code": code,
                    "parent_id": parent_id,
                    "sort_order": sort_order,
                    "description": description,
                },
            )
        stage_ids[code] = stage_id
    return stage_ids


def _disable_old_trial_stages(connection, project_id: int) -> None:
    connection.execute(
        sa.text(
            """
            UPDATE stages
            SET enabled = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = :project_id AND code IN :codes
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"project_id": project_id, "codes": OLD_TRIAL_STAGE_CODES},
    )


def _ensure_trial_material_templates(connection, project_id: int, stage_id: int) -> None:
    for item_code, item_name, sort_order, required in TRIAL_MATERIAL_TEMPLATES:
        _upsert_template(
            connection,
            project_id,
            stage_id,
            "center_file",
            item_code,
            item_name,
            sort_order,
            required,
        )


def _ensure_subject_item_templates(
    connection,
    project_id: int,
    stage_ids: dict[str, int],
) -> None:
    for stage_code, item_code, item_name, sort_order, required in SUBJECT_ITEM_TEMPLATES:
        _upsert_template(
            connection,
            project_id,
            stage_ids[stage_code],
            "subject_item",
            item_code,
            item_name,
            sort_order,
            required,
        )


def _upsert_template(
    connection,
    project_id: int,
    stage_id: int,
    template_scope: str,
    item_code: str,
    item_name: str,
    sort_order: int,
    required: bool,
) -> int:
    template_id = connection.execute(
        sa.text(
            """
            SELECT id
            FROM stage_templates
            WHERE project_id = :project_id
              AND stage_id = :stage_id
              AND template_scope = :template_scope
              AND item_code = :item_code
            """
        ),
        {
            "project_id": project_id,
            "stage_id": stage_id,
            "template_scope": template_scope,
            "item_code": item_code,
        },
    ).scalar_one_or_none()
    if template_id is None:
        return connection.execute(
            sa.text(
                """
                INSERT INTO stage_templates (
                    project_id, stage_id, item_name, item_code, template_scope, required,
                    sort_order, recognition_keywords, description, created_at, updated_at
                )
                VALUES (
                    :project_id, :stage_id, :item_name, :item_code, :template_scope, :required,
                    :sort_order, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id
                """
            ),
            {
                "project_id": project_id,
                "stage_id": stage_id,
                "item_name": item_name,
                "item_code": item_code,
                "template_scope": template_scope,
                "required": required,
                "sort_order": sort_order,
            },
        ).scalar_one()
    connection.execute(
        sa.text(
            """
            UPDATE stage_templates
            SET item_name = :item_name,
                required = :required,
                sort_order = :sort_order,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :template_id
            """
        ),
        {
            "template_id": template_id,
            "item_name": item_name,
            "required": required,
            "sort_order": sort_order,
        },
    )
    return template_id


def _ensure_subject_visit_records(
    connection,
    project_id: int,
    stage_ids: dict[str, int],
) -> None:
    subjects = connection.execute(
        sa.text(
            """
            SELECT id, subject_arm
            FROM subjects
            WHERE project_id = :project_id
            """
        ),
        {"project_id": project_id},
    ).mappings()
    for subject in subjects:
        subject_id = subject["id"]
        arm = subject["subject_arm"] if subject["subject_arm"] == "control" else "experimental"
        for stage_code in VISITS_BY_ARM[arm]:
            section_id = _ensure_subject_section(
                connection,
                project_id,
                subject_id,
                stage_ids[stage_code],
                stage_code,
            )
            _ensure_subject_items(connection, subject_id, section_id, project_id, stage_ids[stage_code])


def _ensure_subject_section(
    connection,
    project_id: int,
    subject_id: int,
    stage_id: int,
    stage_code: str,
) -> int:
    stage = connection.execute(
        sa.text("SELECT name, sort_order, description FROM stages WHERE id = :stage_id"),
        {"stage_id": stage_id},
    ).mappings().one()
    section_id = connection.execute(
        sa.text(
            """
            SELECT id
            FROM subject_sections
            WHERE subject_id = :subject_id AND section_code = :stage_code
            """
        ),
        {"subject_id": subject_id, "stage_code": stage_code},
    ).scalar_one_or_none()
    if section_id is None:
        return connection.execute(
            sa.text(
                """
                INSERT INTO subject_sections (
                    project_id, stage_id, subject_id, section_code, name, visit_name,
                    time_window, sort_order, description
                )
                VALUES (
                    :project_id, :stage_id, :subject_id, :stage_code, :name, :name,
                    NULL, :sort_order, :description
                )
                RETURNING id
                """
            ),
            {
                "project_id": project_id,
                "stage_id": stage_id,
                "subject_id": subject_id,
                "stage_code": stage_code,
                "name": stage["name"],
                "sort_order": stage["sort_order"],
                "description": stage["description"],
            },
        ).scalar_one()
    connection.execute(
        sa.text(
            """
            UPDATE subject_sections
            SET stage_id = :stage_id,
                name = :name,
                visit_name = :name,
                sort_order = :sort_order,
                description = :description
            WHERE id = :section_id
            """
        ),
        {
            "section_id": section_id,
            "stage_id": stage_id,
            "name": stage["name"],
            "sort_order": stage["sort_order"],
            "description": stage["description"],
        },
    )
    return section_id


def _ensure_subject_items(
    connection,
    subject_id: int,
    section_id: int,
    project_id: int,
    stage_id: int,
) -> None:
    templates = connection.execute(
        sa.text(
            """
            SELECT id, item_name, item_code, sort_order, required
            FROM stage_templates
            WHERE project_id = :project_id
              AND stage_id = :stage_id
              AND template_scope = 'subject_item'
            ORDER BY sort_order, id
            """
        ),
        {"project_id": project_id, "stage_id": stage_id},
    ).mappings()
    for template in templates:
        existing_id = connection.execute(
            sa.text(
                """
                SELECT id
                FROM subject_items
                WHERE subject_id = :subject_id AND item_code = :item_code
                """
            ),
            {"subject_id": subject_id, "item_code": template["item_code"]},
        ).scalar_one_or_none()
        if existing_id is not None:
            continue
        connection.execute(
            sa.text(
                """
                INSERT INTO subject_items (
                    subject_id, section_id, stage_template_id, item_name, item_code, sort_order,
                    required, upload_status, review_status, remark, created_at, updated_at
                )
                VALUES (
                    :subject_id, :section_id, :stage_template_id, :item_name, :item_code,
                    :sort_order, :required, 'not_uploaded', 'unreviewed', NULL,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "subject_id": subject_id,
                "section_id": section_id,
                "stage_template_id": template["id"],
                "item_name": template["item_name"],
                "item_code": template["item_code"],
                "sort_order": template["sort_order"],
                "required": template["required"],
            },
        )
