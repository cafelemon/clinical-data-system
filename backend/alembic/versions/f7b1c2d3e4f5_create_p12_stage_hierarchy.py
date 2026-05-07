"""create p12 stage hierarchy

Revision ID: f7b1c2d3e4f5
Revises: e8a1d4c7f902
Create Date: 2026-05-06 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7b1c2d3e4f5"
down_revision: str | Sequence[str] | None = "e8a1d4c7f902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARENT_STAGES = (
    ("STARTUP", "启动阶段", 1, "项目启动、中心准备和启动会相关资料。"),
    ("TRIAL", "试验进行阶段", 2, "按受试者组织试验执行过程资料。"),
    ("CLOSEOUT", "总结阶段", 3, "完成随访、数据清理、统计总结和归档资料。"),
)

STAGE_OPTIONS = (
    ("STARTUP", "PROJECT_SURVEY_CONFIRMATION", "项目调研和确定", 1, ""),
    ("STARTUP", "TRIAL_FILE_PREPARATION", "试验文件准备", 2, ""),
    ("STARTUP", "SITE_SCREENING", "其他临床试验中心筛选", 3, ""),
    ("STARTUP", "INVESTIGATOR_MEETING", "研究者会议", 4, ""),
    ("STARTUP", "INSTITUTION_PROJECT_APPROVAL", "机构立项", 5, ""),
    ("STARTUP", "ETHICS_REVIEW", "伦理审查", 6, ""),
    ("STARTUP", "CONTRACT_SIGNING", "合同签署", 7, ""),
    ("STARTUP", "GENETIC_OFFICE", "遗传办", 8, ""),
    ("STARTUP", "FILING", "备案", 9, ""),
    ("STARTUP", "STARTUP_MEETING", "启动会", 10, ""),
    ("TRIAL", "SCREENING", "筛选阶段", 1, "完成知情同意、筛选评估和纳排标准确认。"),
    ("TRIAL", "ENROLLMENT_PREP", "入组与检查准备阶段", 2, "完成入组登记、基线信息和检查准备确认。"),
    ("TRIAL", "EXAM_EXECUTION", "检查执行阶段", 3, "记录检查执行、原始检查资料和检查结论摘要。"),
    ("TRIAL", "EARLY_FOLLOWUP", "检查后早期随访阶段", 4, "完成检查后早期随访和不良事件确认。"),
    ("TRIAL", "DELAYED_FOLLOWUP", "异常或延迟随访阶段", 5, "记录异常处理和延迟随访情况。"),
    ("TRIAL", "COMPLETION", "试验完成阶段", 6, "完成受试者完成/退出记录和资料完整性确认。"),
    ("CLOSEOUT", "FOLLOWUP_COMPLETION", "完成随访阶段", 1, ""),
    ("CLOSEOUT", "DATA_QUERY", "数据答疑阶段", 2, ""),
    ("CLOSEOUT", "BLINDED_REVIEW", "盲态审核阶段", 3, ""),
    ("CLOSEOUT", "STATISTICAL_SUMMARY_REPORT", "统计与总结报告阶段", 4, ""),
)

DEFAULT_SUBJECT_ITEMS = (
    ("SCREENING", "SCREENING_CONSENT", "知情同意", 1),
    ("SCREENING", "SCREENING_ASSESSMENT", "筛选评估", 2),
    ("SCREENING", "SCREENING_CRITERIA", "纳排标准确认", 3),
    ("ENROLLMENT_PREP", "ENROLLMENT_REGISTRATION", "入组登记", 1),
    ("ENROLLMENT_PREP", "BASELINE_INFORMATION", "基线信息", 2),
    ("ENROLLMENT_PREP", "EXAM_PREPARATION", "检查准备确认", 3),
    ("EXAM_EXECUTION", "EXAM_EXECUTION_RECORD", "检查执行记录", 1),
    ("EXAM_EXECUTION", "EXAM_RAW_DATA", "原始检查资料", 2),
    ("EXAM_EXECUTION", "EXAM_SUMMARY", "检查结论摘要", 3),
    ("EARLY_FOLLOWUP", "EARLY_FOLLOWUP_RECORD", "早期随访记录", 1),
    ("EARLY_FOLLOWUP", "ADVERSE_EVENT_CHECK", "不良事件确认", 2),
    ("DELAYED_FOLLOWUP", "EXCEPTION_HANDLING", "异常处理记录", 1),
    ("DELAYED_FOLLOWUP", "DELAYED_FOLLOWUP_RECORD", "延迟随访记录", 2),
    ("COMPLETION", "COMPLETION_OR_EXIT", "完成/退出记录", 1),
    ("COMPLETION", "DATA_COMPLETENESS_CONFIRM", "资料完整性确认", 2),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("stages", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column("stages", sa.Column("phase_code", sa.String(length=30), nullable=True))
    op.add_column("stages", sa.Column("option_code", sa.String(length=80), nullable=True))
    op.add_column(
        "stages",
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "stages",
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.alter_column("stages", "is_system", server_default=None)
    op.alter_column("stages", "enabled", server_default=None)
    op.create_index(op.f("ix_stages_parent_id"), "stages", ["parent_id"], unique=False)
    op.create_index(op.f("ix_stages_phase_code"), "stages", ["phase_code"], unique=False)
    op.create_index(op.f("ix_stages_option_code"), "stages", ["option_code"], unique=False)

    op.add_column(
        "stage_templates",
        sa.Column(
            "template_scope",
            sa.String(length=30),
            server_default="center_file",
            nullable=False,
        ),
    )
    op.alter_column("stage_templates", "template_scope", server_default=None)

    op.add_column("subject_sections", sa.Column("stage_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_subject_sections_stage_id"),
        "subject_sections",
        ["stage_id"],
        unique=False,
    )
    op.add_column("subject_items", sa.Column("stage_template_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_subject_items_stage_template_id"),
        "subject_items",
        ["stage_template_id"],
        unique=False,
    )

    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_stages_parent_id_stages",
            "stages",
            "stages",
            ["parent_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_subject_sections_stage_id_stages",
            "subject_sections",
            "stages",
            ["stage_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_subject_items_stage_template_id_stage_templates",
            "subject_items",
            "stage_templates",
            ["stage_template_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _migrate_stage_data()

    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_stage_templates_item", "stage_templates", type_="unique")
        op.create_unique_constraint(
            "uq_stage_templates_item_scope",
            "stage_templates",
            ["project_id", "stage_id", "template_scope", "item_code"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_stage_templates_item_scope", "stage_templates", type_="unique")
        op.create_unique_constraint(
            "uq_stage_templates_item",
            "stage_templates",
            ["project_id", "stage_id", "item_code"],
        )
        op.drop_constraint(
            "fk_subject_items_stage_template_id_stage_templates",
            "subject_items",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_subject_sections_stage_id_stages",
            "subject_sections",
            type_="foreignkey",
        )
        op.drop_constraint("fk_stages_parent_id_stages", "stages", type_="foreignkey")
    op.drop_index(op.f("ix_subject_items_stage_template_id"), table_name="subject_items")
    op.drop_column("subject_items", "stage_template_id")
    op.drop_index(op.f("ix_subject_sections_stage_id"), table_name="subject_sections")
    op.drop_column("subject_sections", "stage_id")
    op.drop_column("stage_templates", "template_scope")
    op.drop_index(op.f("ix_stages_option_code"), table_name="stages")
    op.drop_index(op.f("ix_stages_phase_code"), table_name="stages")
    op.drop_index(op.f("ix_stages_parent_id"), table_name="stages")
    op.drop_column("stages", "enabled")
    op.drop_column("stages", "is_system")
    op.drop_column("stages", "option_code")
    op.drop_column("stages", "phase_code")
    op.drop_column("stages", "parent_id")


def _migrate_stage_data() -> None:
    bind = op.get_bind()
    project_ids = [row[0] for row in bind.execute(sa.text("select id from projects"))]
    for project_id in project_ids:
        parent_ids: dict[str, int] = {}
        for code, name, sort_order, description in PARENT_STAGES:
            bind.execute(
                sa.text(
                    """
                    insert into stages (
                        project_id, name, code, parent_id, phase_code, option_code,
                        is_system, enabled, sort_order, description
                    )
                    values (
                        :project_id, :name, :code, null, :code, null,
                        true, true, :sort_order, :description
                    )
                    on conflict (project_id, code) do nothing
                    """
                ),
                {
                    "project_id": project_id,
                    "name": name,
                    "code": code,
                    "sort_order": sort_order,
                    "description": description,
                },
            )
            bind.execute(
                sa.text(
                    """
                    update stages
                    set name = :name,
                        parent_id = null,
                        phase_code = :code,
                        option_code = null,
                        is_system = true,
                        enabled = true,
                        sort_order = :sort_order
                    where project_id = :project_id and code = :code
                    """
                ),
                {
                    "project_id": project_id,
                    "name": name,
                    "code": code,
                    "sort_order": sort_order,
                },
            )
            parent_ids[code] = bind.execute(
                sa.text("select id from stages where project_id = :project_id and code = :code"),
                {"project_id": project_id, "code": code},
            ).scalar_one()

        child_ids: dict[tuple[str, str], int] = {}
        for phase_code, option_code, name, sort_order, description in STAGE_OPTIONS:
            bind.execute(
                sa.text(
                    """
                    insert into stages (
                        project_id, name, code, parent_id, phase_code, option_code,
                        is_system, enabled, sort_order, description
                    )
                    values (
                        :project_id, :name, :option_code, :parent_id, :phase_code,
                        :option_code, false, true, :sort_order, :description
                    )
                    on conflict (project_id, code) do nothing
                    """
                ),
                {
                    "project_id": project_id,
                    "name": name,
                    "option_code": option_code,
                    "parent_id": parent_ids[phase_code],
                    "phase_code": phase_code,
                    "sort_order": sort_order,
                    "description": description,
                },
            )
            bind.execute(
                sa.text(
                    """
                    update stages
                    set parent_id = :parent_id,
                        phase_code = :phase_code,
                        option_code = :option_code,
                        is_system = false
                    where project_id = :project_id and code = :option_code
                    """
                ),
                {
                    "project_id": project_id,
                    "option_code": option_code,
                    "parent_id": parent_ids[phase_code],
                    "phase_code": phase_code,
                },
            )
            child_ids[(phase_code, option_code)] = bind.execute(
                sa.text(
                    "select id from stages where project_id = :project_id and code = :option_code"
                ),
                {"project_id": project_id, "option_code": option_code},
            ).scalar_one()

        for phase_code, _, _, _ in PARENT_STAGES:
            first_option_code = next(
                option_code
                for candidate_phase, option_code, *_ in STAGE_OPTIONS
                if candidate_phase == phase_code
            )
            target_stage_id = child_ids[(phase_code, first_option_code)]
            target_scope = "subject_item" if phase_code == "TRIAL" else "center_file"
            parent_templates = bind.execute(
                sa.text(
                    """
                    select id, item_code
                    from stage_templates
                    where project_id = :project_id and stage_id = :parent_stage_id
                    """
                ),
                {"project_id": project_id, "parent_stage_id": parent_ids[phase_code]},
            ).mappings()
            for template in parent_templates:
                existing_id = bind.execute(
                    sa.text(
                        """
                        select id
                        from stage_templates
                        where project_id = :project_id
                          and stage_id = :target_stage_id
                          and item_code = :item_code
                          and id <> :template_id
                        """
                    ),
                    {
                        "project_id": project_id,
                        "target_stage_id": target_stage_id,
                        "target_scope": target_scope,
                        "item_code": template["item_code"],
                        "template_id": template["id"],
                    },
                ).scalar()
                if existing_id is not None:
                    bind.execute(
                        sa.text("delete from stage_templates where id = :template_id"),
                        {"template_id": template["id"]},
                    )
                    continue
                bind.execute(
                    sa.text(
                        """
                        update stage_templates
                        set stage_id = :target_stage_id, template_scope = :target_scope
                        where id = :template_id
                        """
                    ),
                    {
                        "target_stage_id": target_stage_id,
                        "target_scope": target_scope,
                        "template_id": template["id"],
                    },
                )

        for stage_code, item_code, item_name, sort_order in DEFAULT_SUBJECT_ITEMS:
            stage_id = child_ids[("TRIAL", stage_code)]
            existing_id = bind.execute(
                sa.text(
                    """
                    select id
                    from stage_templates
                    where project_id = :project_id
                      and stage_id = :stage_id
                      and item_code = :item_code
                    """
                ),
                {"project_id": project_id, "stage_id": stage_id, "item_code": item_code},
            ).scalar()
            if existing_id is not None:
                continue
            bind.execute(
                sa.text(
                    """
                    insert into stage_templates (
                        project_id, stage_id, item_name, item_code, template_scope,
                        required, sort_order, description
                    )
                    values (
                        :project_id, :stage_id, :item_name, :item_code, 'subject_item',
                        true, :sort_order, null
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
