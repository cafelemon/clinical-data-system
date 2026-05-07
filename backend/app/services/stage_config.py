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


PARENT_STAGE_SPECS: tuple[ParentStageSpec, ...] = (
    ParentStageSpec("STARTUP", "启动阶段", 1, "项目启动、中心准备和启动会相关资料。"),
    ParentStageSpec("TRIAL", "试验进行阶段", 2, "按受试者组织试验执行过程资料。"),
    ParentStageSpec("CLOSEOUT", "总结阶段", 3, "完成随访、数据清理、统计总结和归档资料。"),
)

STAGE_OPTION_SPECS: tuple[StageOptionSpec, ...] = (
    StageOptionSpec("STARTUP", "PROJECT_SURVEY_CONFIRMATION", "项目调研和确定", 1),
    StageOptionSpec("STARTUP", "TRIAL_FILE_PREPARATION", "试验文件准备", 2),
    StageOptionSpec("STARTUP", "SITE_SCREENING", "其他临床试验中心筛选", 3),
    StageOptionSpec("STARTUP", "INVESTIGATOR_MEETING", "研究者会议", 4),
    StageOptionSpec("STARTUP", "INSTITUTION_PROJECT_APPROVAL", "机构立项", 5),
    StageOptionSpec("STARTUP", "ETHICS_REVIEW", "伦理审查", 6),
    StageOptionSpec("STARTUP", "CONTRACT_SIGNING", "合同签署", 7),
    StageOptionSpec("STARTUP", "GENETIC_OFFICE", "遗传办", 8),
    StageOptionSpec("STARTUP", "FILING", "备案", 9),
    StageOptionSpec("STARTUP", "STARTUP_MEETING", "启动会", 10),
    StageOptionSpec(
        "TRIAL",
        "SCREENING",
        "筛选阶段",
        1,
        "完成知情同意、筛选评估和纳排标准确认。",
    ),
    StageOptionSpec(
        "TRIAL",
        "ENROLLMENT_PREP",
        "入组与检查准备阶段",
        2,
        "完成入组登记、基线信息和检查准备确认。",
    ),
    StageOptionSpec(
        "TRIAL",
        "EXAM_EXECUTION",
        "检查执行阶段",
        3,
        "记录检查执行、原始检查资料和检查结论摘要。",
    ),
    StageOptionSpec(
        "TRIAL",
        "EARLY_FOLLOWUP",
        "检查后早期随访阶段",
        4,
        "完成检查后早期随访和不良事件确认。",
    ),
    StageOptionSpec(
        "TRIAL",
        "DELAYED_FOLLOWUP",
        "异常或延迟随访阶段",
        5,
        "记录异常处理和延迟随访情况。",
    ),
    StageOptionSpec(
        "TRIAL",
        "COMPLETION",
        "试验完成阶段",
        6,
        "完成受试者完成/退出记录和资料完整性确认。",
    ),
    StageOptionSpec("CLOSEOUT", "FOLLOWUP_COMPLETION", "完成随访阶段", 1),
    StageOptionSpec("CLOSEOUT", "DATA_QUERY", "数据答疑阶段", 2),
    StageOptionSpec("CLOSEOUT", "BLINDED_REVIEW", "盲态审核阶段", 3),
    StageOptionSpec("CLOSEOUT", "STATISTICAL_SUMMARY_REPORT", "统计与总结报告阶段", 4),
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
        first_child = first_child_stage(stage)
        if first_child is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="phase has no secondary stage",
            )
        stage = first_child
    expected_scope = phase_template_scope(phase_code)
    if template_scope != expected_scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{phase_code} templates must use {expected_scope}",
        )
    return stage


def first_child_stage(parent: Stage) -> Stage | None:
    if parent.children:
        return sorted(parent.children, key=lambda item: (item.sort_order, item.id))[0]
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
    db.flush()
    _move_parent_templates_to_children(db, project_id, parents, children)
    if not project.stage_template_defaults_initialized:
        _ensure_default_subject_item_templates(db, project_id, children)
        project.stage_template_defaults_initialized = True
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
            if not stage.name:
                stage.name = option.name
            if stage.description is None:
                stage.description = option.description
        children[(option.phase_code, option.option_code)] = stage
    return children


def _move_parent_templates_to_children(
    db: Session,
    project_id: int,
    parents: dict[str, Stage],
    children: dict[tuple[str, str], Stage],
) -> None:
    for phase_code, parent in parents.items():
        first_option = OPTIONS_BY_PHASE[phase_code][0]
        target_stage = children[(phase_code, first_option.option_code)]
        target_scope = phase_template_scope(phase_code)
        parent_templates = list(
            db.scalars(
                select(StageTemplate).where(
                    StageTemplate.project_id == project_id,
                    StageTemplate.stage_id == parent.id,
                )
            )
        )
        for template in parent_templates:
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
                    required=True,
                    sort_order=item_spec.sort_order,
                    description=None,
                )
            )
