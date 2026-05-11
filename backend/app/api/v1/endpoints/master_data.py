from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.database import get_db
from app.models import Center, Dictionary, Project, Stage, StageTemplate, Subject
from app.schemas import (
    CenterCreate,
    CenterRead,
    CenterUpdate,
    DictionaryCreate,
    DictionaryRead,
    DictionaryUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    StageCreate,
    StageOptionGroupRead,
    StageOptionRead,
    StageRead,
    StageTemplateCreate,
    StageTemplateKeywordGenerateRead,
    StageTemplateKeywordGenerateRequest,
    StageTemplateRead,
    StageTemplateUpdate,
    StageUpdate,
)
from app.services.audit import record_operation
from app.services.stage_config import (
    OPTIONS_BY_PHASE,
    PARENT_STAGE_CODES,
    PARENT_STAGE_SPECS,
    ensure_project_stage_config,
    ensure_template_scope,
    normalize_code,
    option_for,
    validate_template_stage,
)
from app.services.template_keywords import generate_keywords_from_subject

router = APIRouter()
ModelT = TypeVar("ModelT", Project, Center, Stage, StageTemplate, Dictionary, Subject)
DBSession = Annotated[Session, Depends(get_db)]
MasterRead = Annotated[AccessContext, Depends(require_permission("master_data:read"))]
MasterWrite = Annotated[AccessContext, Depends(require_permission("master_data:write"))]
DictionaryReadAccess = Annotated[AccessContext, Depends(require_permission("dictionaries:read"))]
DictionaryWriteAccess = Annotated[AccessContext, Depends(require_permission("dictionaries:write"))]
StatusQuery = Annotated[str | None, Query(alias="status")]


def get_or_404(db: Session, model: type[ModelT], item_id: int, label: str) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return item


def commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc


def commit_with_audit_or_conflict(
    db: Session,
    message: str,
    audit_callback: Callable[[], None],
) -> None:
    try:
        db.flush()
        audit_callback()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc


def ensure_project_exists(db: Session, project_id: int) -> Project:
    return get_or_404(db, Project, project_id, "project")


def accessible_project_ids(access: AccessContext) -> set[int]:
    return access.project_ids | access.center_project_ids


def ensure_project_access(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_admin(access: AccessContext) -> None:
    if not access.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can maintain master data",
        )


def ensure_project_write_access(access: AccessContext, project_id: int) -> None:
    ensure_admin(access)


def ensure_center_access(access: AccessContext, center: Center) -> None:
    if not access.can_access_center(center.id, center.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")


def ensure_stage_belongs_to_project(db: Session, project_id: int, stage_id: int) -> Stage:
    stage = get_or_404(db, Stage, stage_id, "stage")
    if stage.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage does not belong to project",
        )
    return stage


def ensure_child_stage(stage: Stage) -> None:
    if stage.parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="system parent stages cannot be maintained here",
        )


def stage_phase_code(db: Session, stage: Stage) -> str | None:
    if stage.phase_code:
        return stage.phase_code
    if stage.parent_id is None:
        return stage.code if stage.code in PARENT_STAGE_CODES else None
    parent = db.get(Stage, stage.parent_id)
    return parent.code if parent is not None else None


def first_enabled_child_stage(db: Session, parent: Stage) -> Stage | None:
    return db.scalar(
        select(Stage)
        .where(
            Stage.project_id == parent.project_id,
            Stage.parent_id == parent.id,
            Stage.enabled.is_(True),
        )
        .order_by(Stage.sort_order, Stage.id)
    )


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    db: DBSession,
    access: MasterRead,
    status_filter: StatusQuery = None,
) -> list[Project]:
    statement = select(Project).order_by(Project.id)
    if status_filter:
        statement = statement.where(Project.status == status_filter)
    if not access.is_admin:
        project_ids = accessible_project_ids(access)
        if not project_ids:
            return []
        statement = statement.where(Project.id.in_(project_ids))
    return list(db.scalars(statement))


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> Project:
    ensure_admin(access)
    project = Project(**payload.model_dump())
    db.add(project)
    try:
        db.flush()
        ensure_project_stage_config(db, project)
        record_operation(
            db,
            action="project.create",
            request=request,
            access=access,
            target_type="project",
            target_id=project.id,
            project_id=project.id,
            detail={"code": project.code, "name": project.name},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="project code already exists",
        ) from exc
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: DBSession, access: MasterRead) -> Project:
    project = get_or_404(db, Project, project_id, "project")
    ensure_project_access(access, project.id)
    return project


@router.put("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> Project:
    project = get_or_404(db, Project, project_id, "project")
    ensure_project_write_access(access, project.id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    commit_with_audit_or_conflict(
        db,
        "project code already exists",
        lambda: record_operation(
            db,
            action="project.update",
            request=request,
            access=access,
            target_type="project",
            target_id=project.id,
            project_id=project.id,
            detail={"changed_fields": sorted(update_data)},
        ),
    )
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> None:
    project = get_or_404(db, Project, project_id, "project")
    ensure_project_write_access(access, project.id)
    project_code = project.code
    record_operation(
        db,
        action="project.delete",
        request=request,
        access=access,
        target_type="project",
        target_id=project_id,
        project_id=project_id,
        detail={"code": project_code},
    )
    db.delete(project)
    commit_or_conflict(db, "project delete failed")


@router.get("/centers", response_model=list[CenterRead])
def list_centers(
    db: DBSession,
    access: MasterRead,
    project_id: int | None = None,
) -> list[Center]:
    statement = select(Center).order_by(Center.project_id, Center.id)
    if project_id is not None:
        ensure_project_exists(db, project_id)
        ensure_project_access(access, project_id)
        statement = statement.where(Center.project_id == project_id)
        if not access.is_admin and project_id not in access.project_ids:
            statement = statement.where(Center.id.in_(access.center_ids))
    elif not access.is_admin:
        if not access.project_ids and not access.center_ids:
            return []
        statement = statement.where(
            or_(
                Center.project_id.in_(access.project_ids),
                Center.id.in_(access.center_ids),
            )
        )
    return list(db.scalars(statement))


@router.get("/projects/{project_id}/centers", response_model=list[CenterRead])
def list_project_centers(project_id: int, db: DBSession, access: MasterRead) -> list[Center]:
    ensure_project_exists(db, project_id)
    ensure_project_access(access, project_id)
    statement = select(Center).where(Center.project_id == project_id).order_by(Center.id)
    if not access.is_admin and project_id not in access.project_ids:
        statement = statement.where(Center.id.in_(access.center_ids))
    return list(db.scalars(statement))


@router.post("/centers", response_model=CenterRead, status_code=status.HTTP_201_CREATED)
def create_center(
    payload: CenterCreate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> Center:
    ensure_project_exists(db, payload.project_id)
    ensure_project_write_access(access, payload.project_id)
    center = Center(**payload.model_dump())
    db.add(center)
    commit_with_audit_or_conflict(
        db,
        "center code already exists in this project",
        lambda: record_operation(
            db,
            action="center.create",
            request=request,
            access=access,
            target_type="center",
            target_id=center.id,
            project_id=center.project_id,
            center_id=center.id,
            detail={"code": center.code, "name": center.name},
        ),
    )
    db.refresh(center)
    return center


@router.put("/centers/{center_id}", response_model=CenterRead)
def update_center(
    center_id: int,
    payload: CenterUpdate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> Center:
    center = get_or_404(db, Center, center_id, "center")
    ensure_project_write_access(access, center.project_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "project_id" in update_data:
        ensure_project_exists(db, update_data["project_id"])
        ensure_project_write_access(access, update_data["project_id"])
    for field, value in update_data.items():
        setattr(center, field, value)
    commit_with_audit_or_conflict(
        db,
        "center code already exists in this project",
        lambda: record_operation(
            db,
            action="center.update",
            request=request,
            access=access,
            target_type="center",
            target_id=center.id,
            project_id=center.project_id,
            center_id=center.id,
            detail={"changed_fields": sorted(update_data)},
        ),
    )
    db.refresh(center)
    return center


@router.delete("/centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_center(
    center_id: int,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> None:
    center = get_or_404(db, Center, center_id, "center")
    ensure_project_write_access(access, center.project_id)
    project_id = center.project_id
    center_code = center.code
    record_operation(
        db,
        action="center.delete",
        request=request,
        access=access,
        target_type="center",
        target_id=center_id,
        project_id=project_id,
        center_id=center_id,
        detail={"code": center_code},
    )
    db.delete(center)
    commit_or_conflict(db, "center delete failed")


@router.get("/stage-options", response_model=list[StageOptionGroupRead])
def list_stage_options(_: MasterRead) -> list[StageOptionGroupRead]:
    return [
        StageOptionGroupRead(
            phase_code=phase.code,
            phase_name=phase.name,
            sort_order=phase.sort_order,
            options=[
                StageOptionRead(
                    phase_code=option.phase_code,
                    option_code=option.option_code,
                    name=option.name,
                    sort_order=option.sort_order,
                    default_enabled=option.default_enabled,
                    description=option.description or None,
                )
                for option in OPTIONS_BY_PHASE[phase.code]
            ],
        )
        for phase in PARENT_STAGE_SPECS
    ]


@router.get("/stages", response_model=list[StageRead])
def list_stages(
    db: DBSession,
    access: MasterRead,
    project_id: int | None = None,
    phase_code: str | None = None,
    include_system: bool = False,
    enabled: bool | None = None,
) -> list[Stage]:
    statement = select(Stage).order_by(Stage.project_id, Stage.sort_order, Stage.id)
    if project_id is not None:
        ensure_project_exists(db, project_id)
        ensure_project_access(access, project_id)
        ensure_project_stage_config(db, project_id)
        db.commit()
        statement = statement.where(Stage.project_id == project_id)
    elif not access.is_admin:
        project_ids = accessible_project_ids(access)
        if not project_ids:
            return []
        statement = statement.where(Stage.project_id.in_(project_ids))
    if not include_system:
        statement = statement.where(Stage.parent_id.is_not(None))
    if phase_code is not None:
        statement = statement.where(Stage.phase_code == normalize_code(phase_code))
    if enabled is not None:
        statement = statement.where(Stage.enabled.is_(enabled))
    return list(db.scalars(statement))


@router.get("/projects/{project_id}/stages", response_model=list[StageRead])
def list_project_stages(
    project_id: int,
    db: DBSession,
    access: MasterRead,
    include_system: bool = True,
) -> list[Stage]:
    ensure_project_exists(db, project_id)
    ensure_project_access(access, project_id)
    ensure_project_stage_config(db, project_id)
    db.commit()
    statement = (
        select(Stage)
        .where(Stage.project_id == project_id)
        .order_by(Stage.sort_order, Stage.id)
    )
    if include_system:
        statement = statement.where(Stage.parent_id.is_(None))
    else:
        statement = statement.where(Stage.parent_id.is_not(None))
    return list(db.scalars(statement))


@router.post("/stages", response_model=StageRead, status_code=status.HTTP_201_CREATED)
def create_stage(
    payload: StageCreate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> Stage:
    ensure_project_exists(db, payload.project_id)
    ensure_project_write_access(access, payload.project_id)
    ensure_project_stage_config(db, payload.project_id)
    phase_code = normalize_code(payload.phase_code)
    option_code = normalize_code(payload.option_code or payload.code)
    if payload.parent_id is not None:
        parent = ensure_stage_belongs_to_project(db, payload.project_id, payload.parent_id)
        if parent.code not in PARENT_STAGE_CODES or parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent stage must be one of the fixed phases",
            )
        phase_code = parent.code
    if option_code in PARENT_STAGE_CODES and payload.option_code is None:
        stage = db.scalar(
            select(Stage).where(Stage.project_id == payload.project_id, Stage.code == option_code)
        )
        if stage is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="system parent stage was not created",
            )
        db.commit()
        return stage
    if payload.option_code is None:
        legacy_phase = next(
            (
                spec.code
                for spec in PARENT_STAGE_SPECS
                if payload.name == spec.name
                or (option_code is not None and option_code.startswith(f"{spec.code}_"))
            ),
            None,
        )
        if legacy_phase is not None:
            stage = db.scalar(
                select(Stage).where(
                    Stage.project_id == payload.project_id,
                    Stage.code == legacy_phase,
                )
            )
            if stage is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="system parent stage was not created",
                )
            db.commit()
            return stage
    if phase_code is None and option_code is not None:
        for candidate_phase, options in OPTIONS_BY_PHASE.items():
            if any(option.option_code == option_code for option in options):
                phase_code = candidate_phase
                break
    if phase_code not in PARENT_STAGE_CODES or option_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage can only be selected from built-in options",
        )
    option = option_for(phase_code, option_code)
    stage = db.scalar(
        select(Stage).where(
            Stage.project_id == payload.project_id,
            Stage.code == option.option_code,
        )
    )
    if stage is None:
        parent = db.scalar(
            select(Stage).where(Stage.project_id == payload.project_id, Stage.code == phase_code)
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="system parent stage was not created",
            )
        stage = Stage(
            project_id=payload.project_id,
            parent_id=parent.id,
            phase_code=phase_code,
            option_code=option.option_code,
            name=option.name,
            code=option.option_code,
            sort_order=payload.sort_order if payload.sort_order is not None else option.sort_order,
            enabled=payload.enabled,
            description=(
                payload.description if payload.description is not None else option.description
            ),
        )
        db.add(stage)
    else:
        stage.enabled = payload.enabled
        if payload.sort_order is not None:
            stage.sort_order = payload.sort_order
        if payload.description is not None:
            stage.description = payload.description
    try:
        db.flush()
        record_operation(
            db,
            action="stage.create",
            request=request,
            access=access,
            target_type="stage",
            target_id=stage.id,
            project_id=stage.project_id,
            detail={"code": stage.code, "name": stage.name},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="stage code already exists in this project",
        ) from exc
    db.refresh(stage)
    return stage


@router.put("/stages/{stage_id}", response_model=StageRead)
def update_stage(
    stage_id: int,
    payload: StageUpdate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> Stage:
    stage = get_or_404(db, Stage, stage_id, "stage")
    ensure_project_write_access(access, stage.project_id)
    if stage.parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="system parent stages cannot be edited",
        )
    update_data = payload.model_dump(exclude_unset=True)
    target_project_id = update_data.get("project_id", stage.project_id)
    if target_project_id != stage.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage project cannot be changed",
        )
    phase_code = normalize_code(update_data.get("phase_code", stage.phase_code))
    option_code = normalize_code(update_data.get("option_code", stage.option_code or stage.code))
    if option_code is not None:
        if phase_code is None:
            phase_code = stage_phase_code(db, stage)
        option = option_for(phase_code or "", option_code)
        parent = db.scalar(
            select(Stage).where(Stage.project_id == stage.project_id, Stage.code == phase_code)
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parent phase not found",
            )
        stage.parent_id = parent.id
        stage.phase_code = phase_code
        stage.option_code = option.option_code
        stage.code = option.option_code
        stage.name = option.name
    if "sort_order" in update_data:
        stage.sort_order = update_data["sort_order"] or 0
    if "enabled" in update_data:
        stage.enabled = bool(update_data["enabled"])
    if "description" in update_data:
        stage.description = update_data["description"]
    commit_with_audit_or_conflict(
        db,
        "stage code already exists in this project",
        lambda: record_operation(
            db,
            action="stage.update",
            request=request,
            access=access,
            target_type="stage",
            target_id=stage.id,
            project_id=stage.project_id,
            detail={"changed_fields": sorted(update_data)},
        ),
    )
    db.refresh(stage)
    return stage


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage(stage_id: int, db: DBSession, access: MasterWrite, request: Request) -> None:
    stage = get_or_404(db, Stage, stage_id, "stage")
    ensure_project_write_access(access, stage.project_id)
    if stage.parent_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="system parent stages cannot be deleted",
        )
    project_id = stage.project_id
    stage_code = stage.code
    stage.enabled = False
    record_operation(
        db,
        action="stage.delete",
        request=request,
        access=access,
        target_type="stage",
        target_id=stage_id,
        project_id=project_id,
        detail={"code": stage_code},
    )
    commit_or_conflict(db, "stage disable failed")


@router.get("/stage-templates", response_model=list[StageTemplateRead])
def list_stage_templates(
    db: DBSession,
    access: MasterRead,
    project_id: int | None = None,
    stage_id: int | None = None,
    template_scope: str | None = None,
) -> list[StageTemplate]:
    statement = select(StageTemplate).order_by(
        StageTemplate.project_id,
        StageTemplate.stage_id,
        StageTemplate.template_scope,
        StageTemplate.sort_order,
        StageTemplate.id,
    )
    if project_id is not None:
        ensure_project_exists(db, project_id)
        ensure_project_access(access, project_id)
        ensure_project_stage_config(db, project_id)
        db.commit()
        statement = statement.where(StageTemplate.project_id == project_id)
    elif not access.is_admin:
        project_ids = accessible_project_ids(access)
        if not project_ids:
            return []
        statement = statement.where(StageTemplate.project_id.in_(project_ids))
    if stage_id is not None:
        stage = get_or_404(db, Stage, stage_id, "stage")
        ensure_project_access(access, stage.project_id)
        if stage.parent_id is None and stage.code in PARENT_STAGE_CODES:
            child_ids = list(
                db.scalars(
                    select(Stage.id)
                    .where(Stage.project_id == stage.project_id, Stage.parent_id == stage.id)
                    .order_by(Stage.sort_order, Stage.id)
                )
            )
            statement = statement.where(StageTemplate.stage_id.in_(child_ids or [-1]))
        else:
            statement = statement.where(StageTemplate.stage_id == stage_id)
    if template_scope is not None:
        statement = statement.where(
            StageTemplate.template_scope == ensure_template_scope(template_scope)
        )
    return list(db.scalars(statement))


@router.post(
    "/stage-templates",
    response_model=StageTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_stage_template(
    payload: StageTemplateCreate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> StageTemplate:
    ensure_project_exists(db, payload.project_id)
    ensure_project_write_access(access, payload.project_id)
    ensure_project_stage_config(db, payload.project_id)
    stage = ensure_stage_belongs_to_project(db, payload.project_id, payload.stage_id)
    template_scope = ensure_template_scope(payload.template_scope)
    stage = validate_template_stage(stage, template_scope)
    payload_data = payload.model_dump()
    payload_data["stage_id"] = stage.id
    payload_data["template_scope"] = template_scope
    template = StageTemplate(**payload_data)
    db.add(template)
    commit_with_audit_or_conflict(
        db,
        "stage template item code already exists in this stage",
        lambda: record_operation(
            db,
            action="stage_template.create",
            request=request,
            access=access,
            target_type="stage_template",
            target_id=template.id,
            project_id=template.project_id,
            detail={"item_code": template.item_code, "item_name": template.item_name},
        ),
    )
    db.refresh(template)
    return template


@router.put("/stage-templates/{template_id}", response_model=StageTemplateRead)
def update_stage_template(
    template_id: int,
    payload: StageTemplateUpdate,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> StageTemplate:
    template = get_or_404(db, StageTemplate, template_id, "stage template")
    ensure_project_write_access(access, template.project_id)
    update_data = payload.model_dump(exclude_unset=True)
    project_id = update_data.get("project_id", template.project_id)
    stage_id = update_data.get("stage_id", template.stage_id)
    template_scope = update_data.get("template_scope", template.template_scope)
    ensure_project_exists(db, project_id)
    ensure_project_write_access(access, project_id)
    ensure_project_stage_config(db, project_id)
    stage = ensure_stage_belongs_to_project(db, project_id, stage_id)
    stage = validate_template_stage(stage, ensure_template_scope(template_scope))
    update_data["stage_id"] = stage.id
    update_data["template_scope"] = template_scope
    for field, value in update_data.items():
        setattr(template, field, value)
    commit_with_audit_or_conflict(
        db,
        "stage template item code already exists in this stage",
        lambda: record_operation(
            db,
            action="stage_template.update",
            request=request,
            access=access,
            target_type="stage_template",
            target_id=template.id,
            project_id=template.project_id,
            detail={"changed_fields": sorted(update_data)},
        ),
    )
    db.refresh(template)
    return template


@router.post(
    "/stage-templates/recognition-keywords/from-subject",
    response_model=StageTemplateKeywordGenerateRead,
)
def generate_stage_template_keywords(
    payload: StageTemplateKeywordGenerateRequest,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> StageTemplateKeywordGenerateRead:
    subject = get_or_404(db, Subject, payload.subject_id, "subject")
    ensure_project_write_access(access, subject.project_id)
    ensure_project_stage_config(db, subject.project_id)
    result = generate_keywords_from_subject(
        db,
        subject,
        mode=payload.mode,
        max_keywords_per_item=payload.max_keywords_per_item,
    )
    record_operation(
        db,
        action="stage_template.generate_keywords",
        request=request,
        access=access,
        target_type="subject",
        target_id=subject.id,
        project_id=subject.project_id,
        center_id=subject.center_id,
        detail={
            "mode": payload.mode,
            "updated_count": result.updated_count,
            "skipped_count": result.skipped_count,
        },
    )
    db.commit()
    return StageTemplateKeywordGenerateRead(
        subject_id=result.subject_id,
        updated_count=result.updated_count,
        skipped_count=result.skipped_count,
        items=[item.__dict__ for item in result.items],
    )


@router.delete("/stage-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage_template(
    template_id: int,
    db: DBSession,
    access: MasterWrite,
    request: Request,
) -> None:
    template = get_or_404(db, StageTemplate, template_id, "stage template")
    ensure_project_write_access(access, template.project_id)
    project_id = template.project_id
    item_code = template.item_code
    record_operation(
        db,
        action="stage_template.delete",
        request=request,
        access=access,
        target_type="stage_template",
        target_id=template_id,
        project_id=project_id,
        detail={"item_code": item_code},
    )
    db.delete(template)
    commit_or_conflict(db, "stage template delete failed")


@router.get("/dictionaries", response_model=list[DictionaryRead])
def list_dictionaries(
    db: DBSession,
    _: DictionaryReadAccess,
    dict_type: str | None = None,
    enabled: bool | None = None,
) -> list[Dictionary]:
    statement = select(Dictionary).order_by(
        Dictionary.dict_type,
        Dictionary.sort_order,
        Dictionary.id,
    )
    if dict_type is not None:
        statement = statement.where(Dictionary.dict_type == dict_type)
    if enabled is not None:
        statement = statement.where(Dictionary.enabled == enabled)
    return list(db.scalars(statement))


@router.post("/dictionaries", response_model=DictionaryRead, status_code=status.HTTP_201_CREATED)
def create_dictionary(
    payload: DictionaryCreate,
    db: DBSession,
    access: DictionaryWriteAccess,
    request: Request,
) -> Dictionary:
    ensure_admin(access)
    dictionary = Dictionary(**payload.model_dump())
    db.add(dictionary)
    commit_with_audit_or_conflict(
        db,
        "dictionary value already exists in this type",
        lambda: record_operation(
            db,
            action="dictionary.create",
            request=request,
            access=access,
            target_type="dictionary",
            target_id=dictionary.id,
            detail={"dict_type": dictionary.dict_type, "value": dictionary.value},
        ),
    )
    db.refresh(dictionary)
    return dictionary


@router.put("/dictionaries/{dictionary_id}", response_model=DictionaryRead)
def update_dictionary(
    dictionary_id: int,
    payload: DictionaryUpdate,
    db: DBSession,
    access: DictionaryWriteAccess,
    request: Request,
) -> Dictionary:
    ensure_admin(access)
    dictionary = get_or_404(db, Dictionary, dictionary_id, "dictionary")
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dictionary, field, value)
    commit_with_audit_or_conflict(
        db,
        "dictionary value already exists in this type",
        lambda: record_operation(
            db,
            action="dictionary.update",
            request=request,
            access=access,
            target_type="dictionary",
            target_id=dictionary.id,
            detail={"changed_fields": sorted(update_data)},
        ),
    )
    db.refresh(dictionary)
    return dictionary


@router.delete("/dictionaries/{dictionary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dictionary(
    dictionary_id: int,
    db: DBSession,
    access: DictionaryWriteAccess,
    request: Request,
) -> None:
    ensure_admin(access)
    dictionary = get_or_404(db, Dictionary, dictionary_id, "dictionary")
    dict_type = dictionary.dict_type
    value = dictionary.value
    record_operation(
        db,
        action="dictionary.delete",
        request=request,
        access=access,
        target_type="dictionary",
        target_id=dictionary_id,
        detail={"dict_type": dict_type, "value": value},
    )
    db.delete(dictionary)
    commit_or_conflict(db, "dictionary delete failed")
