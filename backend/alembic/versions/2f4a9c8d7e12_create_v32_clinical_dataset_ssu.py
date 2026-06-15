"""create v32 clinical dataset ssu

Revision ID: 2f4a9c8d7e12
Revises: 8b6d2f4c9a31
Create Date: 2026-05-24 13:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f4a9c8d7e12"
down_revision: str | Sequence[str] | None = "8b6d2f4c9a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STARTUP_OPTIONS = (
    ("STARTUP_MATERIALS", "资料准备", 1),
    ("SSU_PROJECT_APPROVAL", "立项", 2),
    ("SSU_ETHICS", "伦理", 3),
    ("SSU_AGREEMENT_SIGNING", "协议签署", 4),
    ("SSU_PROVINCIAL_FILING", "省局备案", 5),
    ("SSU_STARTUP_MEETING", "启动会", 6),
)
CLOSEOUT_OPTIONS = (("CLOSEOUT_MATERIALS", "资料准备", 1),)
RETIRED_CODES = (
    "PROJECT_SURVEY_CONFIRMATION",
    "TRIAL_FILE_PREPARATION",
    "SITE_SCREENING",
    "INVESTIGATOR_MEETING",
    "INSTITUTION_PROJECT_APPROVAL",
    "ETHICS_REVIEW",
    "CONTRACT_SIGNING",
    "GENETIC_OFFICE",
    "FILING",
    "FOLLOWUP_COMPLETION",
    "DATA_QUERY",
    "BLINDED_REVIEW",
    "STATISTICAL_SUMMARY_REPORT",
)
STARTUP_TEMPLATES = (
    ("STARTUP_001_APPLICATION", "临床试验申请表", 1, True),
    ("STARTUP_002_PROTOCOL", "试验方案以及其修正案（已签章）", 2, True),
    ("STARTUP_003_INVESTIGATOR_BROCHURE", "研究者手册", 3, True),
    ("STARTUP_004_ICF_TEXT", "知情同意书文本以及其他任何提供给受试者的书面材料", 4, True),
    ("STARTUP_005_RECRUITMENT_DOCUMENTS", "招募受试者和向其宣传的程序性文件（若有）", 5, False),
    ("STARTUP_006_CRF_TEXT", "病例报告表文本", 6, True),
    ("STARTUP_007_PRODUCT_TEST_REPORT", "基于产品技术要求的产品检验报告", 7, True),
    ("STARTUP_008_PRECLINICAL_MATERIALS", "临床前研究相关资料", 8, True),
    ("STARTUP_009_INVESTIGATOR_QUALIFICATION", "研究者简历以及资格证明文件", 9, True),
    ("STARTUP_010_QMS_DECLARATION", "质量管理体系相关要求声明", 10, True),
    ("STARTUP_011_SUBJECT_INSURANCE", "受试者保险相关文件（若有）", 11, False),
    ("STARTUP_012_ETHICS_OPINION", "伦理委员会审查意见", 12, True),
    ("STARTUP_013_ETHICS_MEMBER_LIST", "伦理委员会成员表（若有）", 13, False),
    ("STARTUP_014_CONTRACT", "临床试验合同（已签章）", 14, True),
    ("STARTUP_015_TRIAL_APPROVAL", "医疗器械临床试验批件（若有）", 15, False),
    ("STARTUP_016_REGULATORY_FILING", "药品监督管理部门临床试验备案文件", 16, True),
    ("STARTUP_017_STARTUP_TRAINING", "启动会相关培训记录", 17, True),
    ("STARTUP_018_SIGNATURE_AUTHORIZATION", "研究者签名样张以及研究者授权表", 18, True),
    ("STARTUP_019_LAB_NORMAL_RANGE", "实验室检测正常值范围（若有）", 19, False),
    ("STARTUP_020_LAB_QC_CERTIFICATE", "医学或者实验室室间质控证明（若有）", 20, False),
    ("STARTUP_021_DEVICE_LABEL_TEXT", "试验医疗器械标签文本", 21, True),
    ("STARTUP_022_DEVICE_HANDOVER", "试验医疗器械与试验相关物资的交接单", 22, True),
    ("STARTUP_023_UNBLINDING_PROCEDURE", "设盲试验的破盲程序（若有）", 23, False),
    ("STARTUP_024_RANDOMIZATION_LIST", "总随机表（若有）", 24, False),
    ("STARTUP_025_MONITORING_PLAN", "监查计划", 25, True),
    ("STARTUP_026_STARTUP_MONITORING_REPORT", "试验启动监查报告", 26, True),
)
CLOSEOUT_TEMPLATES = (
    ("CLOSEOUT_046_DEVICE_ACCOUNTABILITY", "试验医疗器械储存/使用/维护/保养/销毁/回收等记录（若有）", 46, False),
    ("CLOSEOUT_047_BIO_SAMPLE_RECORDS", "生物样本采集/处理/使用/保存/运输/销毁记录（若有）", 47, False),
    ("CLOSEOUT_048_TEST_RESULT_SOURCE", "所有检测试验结果原始记录（若有）", 48, False),
    ("CLOSEOUT_049_FINAL_MONITORING_REPORT", "最终监查报告", 49, True),
    ("CLOSEOUT_050_AUDIT_CERTIFICATE", "稽查证明（若有）", 50, False),
    ("CLOSEOUT_051_TREATMENT_ALLOCATION", "治疗分配记录（若有）", 51, False),
    ("CLOSEOUT_052_UNBLINDING_CERTIFICATE", "破盲证明（若有）", 52, False),
    ("CLOSEOUT_053_ETHICS_COMPLETION_SUBMISSION", "研究者向伦理委员会提交的试验完成文件", 53, True),
    ("CLOSEOUT_054_SITE_SUMMARY", "分中心临床试验小结", 54, True),
    ("CLOSEOUT_055_CLINICAL_TRIAL_REPORT", "临床试验报告", 55, True),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "clinical_ssu_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=False),
        sa.Column("stage_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("submitted_at", sa.Date(), nullable=True),
        sa.Column("approved_at", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.Date(), nullable=True),
        sa.Column("version_info", sa.String(length=120), nullable=True),
        sa.Column("file_checklist", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("fee_detail", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["center_id"], ["centers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "center_id",
            "stage_code",
            name="uq_clinical_ssu_progress_scope_stage",
        ),
    )
    op.create_index(op.f("ix_clinical_ssu_progress_id"), "clinical_ssu_progress", ["id"])
    op.create_index(
        op.f("ix_clinical_ssu_progress_project_id"),
        "clinical_ssu_progress",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_clinical_ssu_progress_center_id"),
        "clinical_ssu_progress",
        ["center_id"],
    )
    op.create_index(
        op.f("ix_clinical_ssu_progress_stage_code"),
        "clinical_ssu_progress",
        ["stage_code"],
    )
    _migrate_stage_configuration()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_clinical_ssu_progress_stage_code"), table_name="clinical_ssu_progress")
    op.drop_index(op.f("ix_clinical_ssu_progress_center_id"), table_name="clinical_ssu_progress")
    op.drop_index(op.f("ix_clinical_ssu_progress_project_id"), table_name="clinical_ssu_progress")
    op.drop_index(op.f("ix_clinical_ssu_progress_id"), table_name="clinical_ssu_progress")
    op.drop_table("clinical_ssu_progress")


def _migrate_stage_configuration() -> None:
    bind = op.get_bind()
    project_ids = [row[0] for row in bind.execute(sa.text("select id from projects"))]
    for project_id in project_ids:
        _update_parent(bind, project_id, "STARTUP", "试验准备阶段")
        _update_parent(bind, project_id, "CLOSEOUT", "试验结束阶段")
        _ensure_options(bind, project_id, "STARTUP", STARTUP_OPTIONS)
        _ensure_options(bind, project_id, "CLOSEOUT", CLOSEOUT_OPTIONS)
        _disable_retired(bind, project_id)
        _ensure_templates(bind, project_id, "STARTUP_MATERIALS", STARTUP_TEMPLATES)
        _ensure_templates(bind, project_id, "CLOSEOUT_MATERIALS", CLOSEOUT_TEMPLATES)


def _update_parent(bind, project_id: int, code: str, name: str) -> None:
    bind.execute(
        sa.text(
            """
            update stages
            set name = :name, phase_code = :code, parent_id = null, is_system = true, enabled = true
            where project_id = :project_id and code = :code
            """
        ),
        {"project_id": project_id, "code": code, "name": name},
    )


def _ensure_options(bind, project_id: int, phase_code: str, options: tuple[tuple[str, str, int], ...]) -> None:
    parent_id = bind.execute(
        sa.text("select id from stages where project_id = :project_id and code = :phase_code"),
        {"project_id": project_id, "phase_code": phase_code},
    ).scalar_one()
    for option_code, name, sort_order in options:
        bind.execute(
            sa.text(
                """
                insert into stages (
                    project_id, name, code, parent_id, phase_code, option_code,
                    is_system, enabled, sort_order, description
                )
                select
                    :project_id,
                    cast(:name as varchar(100)),
                    cast(:stage_code as varchar(50)),
                    :parent_id,
                    cast(:phase_code as varchar(30)),
                    cast(:option_code as varchar(80)),
                    false, true, :sort_order, ''
                where not exists (
                    select 1
                    from stages
                    where project_id = :project_id and code = cast(:stage_code as varchar(50))
                )
                """
            ),
            {
                "project_id": project_id,
                "name": name,
                "stage_code": option_code,
                "option_code": option_code,
                "parent_id": parent_id,
                "phase_code": phase_code,
                "sort_order": sort_order,
            },
        )
        bind.execute(
            sa.text(
                """
                update stages
                set name = :name,
                    parent_id = :parent_id,
                    phase_code = :phase_code,
                    option_code = :option_code,
                    is_system = false,
                    enabled = true,
                    sort_order = :sort_order
                where project_id = :project_id and code = :option_code
                """
            ),
            {
                "project_id": project_id,
                "name": name,
                "option_code": option_code,
                "parent_id": parent_id,
                "phase_code": phase_code,
                "sort_order": sort_order,
            },
        )


def _disable_retired(bind, project_id: int) -> None:
    for code in RETIRED_CODES:
        bind.execute(
            sa.text(
                """
                update stages
                set enabled = false
                where project_id = :project_id and code = :code
                """
            ),
            {"project_id": project_id, "code": code},
        )


def _ensure_templates(
    bind,
    project_id: int,
    stage_code: str,
    templates: tuple[tuple[str, str, int, bool], ...],
) -> None:
    stage_id = bind.execute(
        sa.text("select id from stages where project_id = :project_id and code = :stage_code"),
        {"project_id": project_id, "stage_code": stage_code},
    ).scalar_one()
    for item_code, item_name, sort_order, required in templates:
        bind.execute(
            sa.text(
                """
                insert into stage_templates (
                    project_id, stage_id, item_name, item_code, template_scope,
                    required, sort_order, description
                )
                select
                    :project_id,
                    :stage_id,
                    cast(:item_name as varchar(150)),
                    cast(:item_code as varchar(80)),
                    cast('center_file' as varchar(30)),
                    :required, :sort_order, null
                where not exists (
                    select 1
                    from stage_templates
                    where project_id = :project_id
                      and stage_id = :stage_id
                      and template_scope = cast('center_file' as varchar(30))
                      and item_code = cast(:item_code as varchar(80))
                )
                """
            ),
            {
                "project_id": project_id,
                "stage_id": stage_id,
                "item_name": item_name,
                "item_code": item_code,
                "required": required,
                "sort_order": sort_order,
            },
        )
