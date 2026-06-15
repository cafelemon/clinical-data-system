from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import SUBJECT_SECTION_SPECS
from app.models import Project, Stage, StageTemplate

CENTER_FILE_SCOPE = "center_file"
SUBJECT_ITEM_SCOPE = "subject_item"
TEMPLATE_SCOPES = {CENTER_FILE_SCOPE, SUBJECT_ITEM_SCOPE}


@dataclass(frozen=True)
class ParentStageSpec:
    code: str
    name: str
    sort_order: int
    description: str


@dataclass(frozen=True)
class StageOptionSpec:
    phase_code: str
    option_code: str
    name: str
    sort_order: int
    description: str = ""
    default_enabled: bool = True


@dataclass(frozen=True)
class DefaultCenterTemplateSpec:
    phase_code: str
    option_code: str
    item_code: str
    item_name: str
    sort_order: int
    required: bool = True
    description: str | None = None


PARENT_STAGE_SPECS: tuple[ParentStageSpec, ...] = (
    ParentStageSpec("STARTUP", "试验准备阶段", 1, "试验准备资料、SSU进展和启动会相关资料。"),
    ParentStageSpec("TRIAL", "试验进行阶段", 2, "试验进行资料准备和受试者试验实施访视资料。"),
    ParentStageSpec("CLOSEOUT", "试验结束阶段", 3, "试验完成、终止后资料准备和归档资料。"),
)

STAGE_OPTION_SPECS: tuple[StageOptionSpec, ...] = (
    StageOptionSpec("STARTUP", "STARTUP_MATERIALS", "资料准备", 1),
    StageOptionSpec("STARTUP", "SSU_PROJECT_APPROVAL", "立项", 2),
    StageOptionSpec("STARTUP", "SSU_ETHICS", "伦理", 3),
    StageOptionSpec("STARTUP", "SSU_AGREEMENT_SIGNING", "协议签署", 4),
    StageOptionSpec("STARTUP", "SSU_PROVINCIAL_FILING", "省局备案", 5),
    StageOptionSpec("STARTUP", "SSU_STARTUP_MEETING", "启动会", 6),
    StageOptionSpec("TRIAL", "TRIAL_MATERIALS", "资料准备", 1),
    StageOptionSpec(
        "TRIAL",
        "V1_SCREENING_VISIT",
        "V1筛选访视阶段",
        2,
        "完成知情同意、筛选评估和入组前资料收集。",
    ),
    StageOptionSpec(
        "TRIAL",
        "V2_EXPERIMENTAL_FOLLOWUP_VISIT",
        "V2随访访视",
        3,
        "完成随访访视资料收集。",
    ),
    StageOptionSpec(
        "TRIAL",
        "V3_CONTROL_FOLLOWUP_VISIT",
        "V3随访访视",
        4,
        "完成随访访视资料收集。",
    ),
    StageOptionSpec(
        "TRIAL",
        "V4_UNSCHEDULED_VISIT",
        "V4非预期访视（若有）",
        5,
        "按需记录非预期访视资料。",
    ),
    StageOptionSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "资料准备", 1),
)

STARTUP_MATERIAL_TEMPLATES: tuple[DefaultCenterTemplateSpec, ...] = (
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_001_APPLICATION", "临床试验申请表", 1),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_002_PROTOCOL", "试验方案以及其修正案（已签章）", 2),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_003_INVESTIGATOR_BROCHURE", "研究者手册", 3),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_004_ICF_TEXT", "知情同意书文本以及其他任何提供给受试者的书面材料", 4),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_005_RECRUITMENT_DOCUMENTS", "招募受试者和向其宣传的程序性文件（若有）", 5, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_006_CRF_TEXT", "病例报告表文本", 6),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_007_PRODUCT_TEST_REPORT", "基于产品技术要求的产品检验报告", 7),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_008_PRECLINICAL_MATERIALS", "临床前研究相关资料", 8),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_009_INVESTIGATOR_QUALIFICATION", "研究者简历以及资格证明文件", 9),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_010_QMS_DECLARATION", "质量管理体系相关要求声明", 10),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_011_SUBJECT_INSURANCE", "受试者保险相关文件（若有）", 11, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_012_ETHICS_OPINION", "伦理委员会审查意见", 12),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_013_ETHICS_MEMBER_LIST", "伦理委员会成员表（若有）", 13, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_014_CONTRACT", "临床试验合同（已签章）", 14),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_015_TRIAL_APPROVAL", "医疗器械临床试验批件（若有）", 15, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_016_REGULATORY_FILING", "药品监督管理部门临床试验备案文件", 16),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_017_STARTUP_TRAINING", "启动会相关培训记录", 17),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_018_SIGNATURE_AUTHORIZATION", "研究者签名样张以及研究者授权表", 18),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_019_LAB_NORMAL_RANGE", "实验室检测正常值范围（若有）", 19, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_020_LAB_QC_CERTIFICATE", "医学或者实验室室间质控证明（若有）", 20, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_021_DEVICE_LABEL_TEXT", "试验医疗器械标签文本", 21),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_022_DEVICE_HANDOVER", "试验医疗器械与试验相关物资的交接单", 22),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_023_UNBLINDING_PROCEDURE", "设盲试验的破盲程序（若有）", 23, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_024_RANDOMIZATION_LIST", "总随机表（若有）", 24, False),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_025_MONITORING_PLAN", "监查计划", 25),
    DefaultCenterTemplateSpec("STARTUP", "STARTUP_MATERIALS", "STARTUP_026_STARTUP_MONITORING_REPORT", "试验启动监查报告", 26),
)

CLOSEOUT_MATERIAL_TEMPLATES: tuple[DefaultCenterTemplateSpec, ...] = (
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_046_DEVICE_ACCOUNTABILITY", "试验医疗器械储存/使用/维护/保养/销毁/回收等记录（若有）", 46, False),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_047_BIO_SAMPLE_RECORDS", "生物样本采集/处理/使用/保存/运输/销毁记录（若有）", 47, False),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_048_TEST_RESULT_SOURCE", "所有检测试验结果原始记录（若有）", 48, False),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_049_FINAL_MONITORING_REPORT", "最终监查报告", 49),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_050_AUDIT_CERTIFICATE", "稽查证明（若有）", 50, False),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_051_TREATMENT_ALLOCATION", "治疗分配记录（若有）", 51, False),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_052_UNBLINDING_CERTIFICATE", "破盲证明（若有）", 52, False),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_053_ETHICS_COMPLETION_SUBMISSION", "研究者向伦理委员会提交的试验完成文件", 53),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_054_SITE_SUMMARY", "分中心临床试验小结", 54),
    DefaultCenterTemplateSpec("CLOSEOUT", "CLOSEOUT_MATERIALS", "CLOSEOUT_055_CLINICAL_TRIAL_REPORT", "临床试验报告", 55),
)

TRIAL_MATERIAL_TEMPLATES: tuple[DefaultCenterTemplateSpec, ...] = (
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_027_INVESTIGATOR_BROCHURE_UPDATE", "研究者手册更新件（若有）", 27, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_028_PROTOCOL_UPDATE", "临床试验方案更新件（若有）", 28, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_029_OTHER_DOCUMENT_UPDATES", "其他文件（病例报告表、知情同意书、书面情况通知）的更新（若有）", 29, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_030_PRODUCT_TEST_REPORT_UPDATE", "试验医疗器械产品检验报告的更新（若有）", 30, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_031_ETHICS_UPDATE_OPINION", "伦理委员会对更新文件的书面审查意见（若有）", 31, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_032_INVESTIGATOR_QUALIFICATION_UPDATE", "研究者简历以及资格证明文件的更新（若有）", 32, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_033_LAB_NORMAL_RANGE_UPDATE", "临床试验有关的实验室检测正常值范围更新（若有）", 33, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_034_LAB_QC_CERTIFICATE_UPDATE", "医学或者实验室室间质控证明更新（若有）", 34, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_035_DEVICE_HANDOVER", "试验医疗器械与试验相关物资的交接单（若有）", 35, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_036_SIGNED_INFORMED_CONSENT", "已签名的知情同意书（若有）", 36, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_037_SOURCE_MEDICAL_DOCUMENTS", "原始医疗文件（若有）", 37, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_038_SIGNED_CRF", "已填并签字的病例报告表", 38),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_039_INVESTIGATOR_SAE_REPORT", "研究者对严重不良事件的报告（若有）", 39, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_040_SPONSOR_DEVICE_RELATED_SAE_REPORT", "申办者对试验医疗器械相关严重不良事件的报告（若有）", 40, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_041_OTHER_SAFETY_RISK_REPORT", "其他严重安全性风险信息的报告（若有）", 41, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_042_SUBJECT_IDENTIFICATION_CODE_LIST", "受试者鉴认代码表", 42),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_043_SUBJECT_SCREENING_AND_ENROLLMENT_TABLE", "受试者筛选表与入选表", 43),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_044_SIGNATURE_AUTHORIZATION_UPDATE", "研究者签名样张以及研究者授权表更新文件（若有）", 44, False),
    DefaultCenterTemplateSpec("TRIAL", "TRIAL_MATERIALS", "TRIAL_045_MONITORING_REPORT", "监查员监查报告", 45),
)

DEFAULT_CENTER_FILE_TEMPLATES = (
    STARTUP_MATERIAL_TEMPLATES + TRIAL_MATERIAL_TEMPLATES + CLOSEOUT_MATERIAL_TEMPLATES
)
CENTER_FILE_OPTION_CODES = frozenset({"STARTUP_MATERIALS", "TRIAL_MATERIALS", "CLOSEOUT_MATERIALS"})
RETIRED_CENTER_FILE_STAGE_CODES = frozenset(
    {
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
        "SCREENING",
        "ENROLLMENT_PREP",
        "EXAM_EXECUTION",
        "EARLY_FOLLOWUP",
        "DELAYED_FOLLOWUP",
        "COMPLETION",
    }
)

PARENT_STAGE_CODES = frozenset(spec.code for spec in PARENT_STAGE_SPECS)
PARENT_STAGE_BY_CODE = {spec.code: spec for spec in PARENT_STAGE_SPECS}
OPTIONS_BY_PHASE: dict[str, tuple[StageOptionSpec, ...]] = {
    phase_code: tuple(option for option in STAGE_OPTION_SPECS if option.phase_code == phase_code)
    for phase_code in PARENT_STAGE_CODES
}
OPTION_BY_PHASE_AND_CODE = {
    (option.phase_code, option.option_code): option for option in STAGE_OPTION_SPECS
}


def normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().upper() or None


def template_scope_for_option(option_code: str | None) -> str:
    if option_code in CENTER_FILE_OPTION_CODES or (option_code or "").startswith("SSU_"):
        return CENTER_FILE_SCOPE
    return SUBJECT_ITEM_SCOPE


def phase_template_scope(phase_code: str) -> str:
    return SUBJECT_ITEM_SCOPE if phase_code == "TRIAL" else CENTER_FILE_SCOPE


def ensure_template_scope(scope: str) -> str:
    if scope not in TEMPLATE_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid template scope",
        )
    return scope


def option_for(phase_code: str, option_code: str) -> StageOptionSpec:
    option = OPTION_BY_PHASE_AND_CODE.get((phase_code, option_code))
    if option is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage option not found in built-in library",
        )
    return option


def parent_phase_for_stage(stage: Stage) -> str | None:
    if stage.phase_code:
        return stage.phase_code
    if stage.code in PARENT_STAGE_CODES and stage.parent_id is None:
        return stage.code
    if stage.parent is not None and stage.parent.code in PARENT_STAGE_CODES:
        return stage.parent.code
    return None


def validate_template_stage(stage: Stage, template_scope: str) -> Stage:
    phase_code = parent_phase_for_stage(stage)
    if phase_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage is not part of the fixed phase system",
        )
    if stage.parent_id is None:
        first_child = first_child_stage(stage, template_scope)
        if first_child is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phase has no secondary stage",
            )
        stage = first_child
    expected_scope = template_scope_for_option(stage.option_code or stage.code)
    if template_scope != expected_scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{stage.code} templates must use {expected_scope}",
        )
    return stage


def first_child_stage(parent: Stage, template_scope: str | None = None) -> Stage | None:
    children = sorted(parent.children, key=lambda item: (item.sort_order, item.id))
    if template_scope is not None:
        children = [
            child
            for child in children
            if template_scope_for_option(child.option_code or child.code) == template_scope
        ]
    if children:
        return children[0]
    return None


def ensure_project_stage_config(db: Session, project_or_id: Project | int) -> None:
    project = (
        project_or_id
        if isinstance(project_or_id, Project)
        else db.get(Project, project_or_id)
    )
    if project is None:
        return
    project_id = project.id
    parents = _ensure_parent_stages(db, project_id)
    children = _ensure_child_stages(db, project_id, parents)
    _disable_retired_center_file_stages(db, project_id)
    db.flush()
    _move_parent_templates_to_children(db, project_id, parents, children)
    _ensure_default_center_file_templates(db, project_id, children)
    if not project.stage_template_defaults_initialized:
        _ensure_default_subject_item_templates(db, project_id, children)
        project.stage_template_defaults_initialized = True
    _disable_retired_center_file_stages(db, project_id)
    db.flush()


def ensure_all_project_stage_configs(db: Session) -> None:
    for project_id in db.scalars(select(Project.id).order_by(Project.id)):
        ensure_project_stage_config(db, project_id)


def _ensure_parent_stages(db: Session, project_id: int) -> dict[str, Stage]:
    parents: dict[str, Stage] = {}
    for spec in PARENT_STAGE_SPECS:
        stage = db.scalar(
            select(Stage).where(Stage.project_id == project_id, Stage.code == spec.code)
        )
        if stage is None:
            stage = Stage(
                project_id=project_id,
                name=spec.name,
                code=spec.code,
                parent_id=None,
                phase_code=spec.code,
                option_code=None,
                is_system=True,
                enabled=True,
                sort_order=spec.sort_order,
                description=spec.description,
            )
            db.add(stage)
            db.flush()
        else:
            stage.name = spec.name
            stage.parent_id = None
            stage.phase_code = spec.code
            stage.option_code = None
            stage.is_system = True
            stage.enabled = True
            stage.sort_order = spec.sort_order
            if stage.description is None:
                stage.description = spec.description
        parents[spec.code] = stage
    return parents


def _ensure_child_stages(
    db: Session,
    project_id: int,
    parents: dict[str, Stage],
) -> dict[tuple[str, str], Stage]:
    children: dict[tuple[str, str], Stage] = {}
    for option in STAGE_OPTION_SPECS:
        parent = parents[option.phase_code]
        stage = db.scalar(
            select(Stage).where(Stage.project_id == project_id, Stage.code == option.option_code)
        )
        if stage is None:
            stage = Stage(
                project_id=project_id,
                name=option.name,
                code=option.option_code,
                parent_id=parent.id,
                phase_code=option.phase_code,
                option_code=option.option_code,
                is_system=False,
                enabled=option.default_enabled,
                sort_order=option.sort_order,
                description=option.description,
            )
            db.add(stage)
            db.flush()
        else:
            stage.parent_id = parent.id
            stage.phase_code = option.phase_code
            stage.option_code = option.option_code
            stage.is_system = False
            stage.name = option.name
            if stage.description is None:
                stage.description = option.description
        children[(option.phase_code, option.option_code)] = stage
    return children


def _disable_retired_center_file_stages(db: Session, project_id: int) -> None:
    for stage in db.scalars(
        select(Stage).where(
            Stage.project_id == project_id,
            Stage.code.in_(RETIRED_CENTER_FILE_STAGE_CODES),
        )
    ):
        stage.enabled = False


def _move_parent_templates_to_children(
    db: Session,
    project_id: int,
    parents: dict[str, Stage],
    children: dict[tuple[str, str], Stage],
) -> None:
    for phase_code, parent in parents.items():
        parent_templates = list(
            db.scalars(
                select(StageTemplate).where(
                    StageTemplate.project_id == project_id,
                    StageTemplate.stage_id == parent.id,
                )
            )
        )
        for template in parent_templates:
            target_stage = _default_child_for_scope(phase_code, template.template_scope, children)
            if target_stage is None:
                continue
            target_scope = template_scope_for_option(target_stage.option_code or target_stage.code)
            duplicate = db.scalar(
                select(StageTemplate).where(
                    StageTemplate.project_id == project_id,
                    StageTemplate.stage_id == target_stage.id,
                    StageTemplate.template_scope == target_scope,
                    StageTemplate.item_code == template.item_code,
                    StageTemplate.id != template.id,
                )
            )
            if duplicate is not None:
                db.delete(template)
                continue
            template.stage_id = target_stage.id
            template.template_scope = target_scope


def _default_child_for_scope(
    phase_code: str,
    template_scope: str,
    children: dict[tuple[str, str], Stage],
) -> Stage | None:
    for option in OPTIONS_BY_PHASE[phase_code]:
        if template_scope_for_option(option.option_code) == template_scope:
            return children.get((phase_code, option.option_code))
    return None


def _ensure_default_center_file_templates(
    db: Session,
    project_id: int,
    children: dict[tuple[str, str], Stage],
) -> None:
    for template_spec in DEFAULT_CENTER_FILE_TEMPLATES:
        stage = children.get((template_spec.phase_code, template_spec.option_code))
        if stage is None:
            continue
        existing = db.scalar(
            select(StageTemplate).where(
                StageTemplate.project_id == project_id,
                StageTemplate.stage_id == stage.id,
                StageTemplate.template_scope == CENTER_FILE_SCOPE,
                StageTemplate.item_code == template_spec.item_code,
            )
        )
        if existing is not None:
            continue
        db.add(
            StageTemplate(
                project_id=project_id,
                stage_id=stage.id,
                template_scope=CENTER_FILE_SCOPE,
                item_name=template_spec.item_name,
                item_code=template_spec.item_code,
                required=template_spec.required,
                sort_order=template_spec.sort_order,
                description=template_spec.description,
            )
        )


def _ensure_default_subject_item_templates(
    db: Session,
    project_id: int,
    children: dict[tuple[str, str], Stage],
) -> None:
    for section_spec in SUBJECT_SECTION_SPECS:
        stage = children.get(("TRIAL", section_spec.code))
        if stage is None:
            continue
        for item_spec in section_spec.items:
            existing = db.scalar(
                select(StageTemplate).where(
                    StageTemplate.project_id == project_id,
                    StageTemplate.stage_id == stage.id,
                    StageTemplate.template_scope == SUBJECT_ITEM_SCOPE,
                    StageTemplate.item_code == item_spec.code,
                )
            )
            if existing is not None:
                continue
            db.add(
                StageTemplate(
                    project_id=project_id,
                    stage_id=stage.id,
                    template_scope=SUBJECT_ITEM_SCOPE,
                    item_name=item_spec.name,
                    item_code=item_spec.code,
                    required=item_spec.required,
                    sort_order=item_spec.sort_order,
                    description=None,
                )
            )
