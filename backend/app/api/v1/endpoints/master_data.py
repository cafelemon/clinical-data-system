from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.database import get_db
from app.models import Center, Dictionary, Project, Stage, StageTemplate
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
    StageRead,
    StageTemplateCreate,
    StageTemplateRead,
    StageTemplateUpdate,
    StageUpdate,
)

router = APIRouter()
ModelT = TypeVar("ModelT", Project, Center, Stage, StageTemplate, Dictionary)
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


def ensure_project_exists(db: Session, project_id: int) -> Project:
    return get_or_404(db, Project, project_id, "project")


def accessible_project_ids(access: AccessContext) -> set[int]:
    return access.project_ids | access.center_project_ids


def ensure_project_access(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_project_write_access(access: AccessContext, project_id: int) -> None:
    if not access.is_admin and project_id not in access.project_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project write scope denied",
        )


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
def create_project(payload: ProjectCreate, db: DBSession, access: MasterWrite) -> Project:
    if not access.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create projects",
        )
    project = Project(**payload.model_dump())
    db.add(project)
    commit_or_conflict(db, "project code already exists")
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
) -> Project:
    project = get_or_404(db, Project, project_id, "project")
    ensure_project_write_access(access, project.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    commit_or_conflict(db, "project code already exists")
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DBSession, access: MasterWrite) -> None:
    project = get_or_404(db, Project, project_id, "project")
    ensure_project_write_access(access, project.id)
    db.delete(project)
    db.commit()


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
def create_center(payload: CenterCreate, db: DBSession, access: MasterWrite) -> Center:
    ensure_project_exists(db, payload.project_id)
    ensure_project_write_access(access, payload.project_id)
    center = Center(**payload.model_dump())
    db.add(center)
    commit_or_conflict(db, "center code already exists in this project")
    db.refresh(center)
    return center


@router.put("/centers/{center_id}", response_model=CenterRead)
def update_center(
    center_id: int,
    payload: CenterUpdate,
    db: DBSession,
    access: MasterWrite,
) -> Center:
    center = get_or_404(db, Center, center_id, "center")
    ensure_center_access(access, center)
    update_data = payload.model_dump(exclude_unset=True)
    if "project_id" in update_data:
        ensure_project_exists(db, update_data["project_id"])
        ensure_project_write_access(access, update_data["project_id"])
    for field, value in update_data.items():
        setattr(center, field, value)
    commit_or_conflict(db, "center code already exists in this project")
    db.refresh(center)
    return center


@router.delete("/centers/{center_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_center(center_id: int, db: DBSession, access: MasterWrite) -> None:
    center = get_or_404(db, Center, center_id, "center")
    ensure_center_access(access, center)
    db.delete(center)
    db.commit()


@router.get("/stages", response_model=list[StageRead])
def list_stages(
    db: DBSession,
    access: MasterRead,
    project_id: int | None = None,
) -> list[Stage]:
    statement = select(Stage).order_by(Stage.project_id, Stage.sort_order, Stage.id)
    if project_id is not None:
        ensure_project_exists(db, project_id)
        ensure_project_access(access, project_id)
        statement = statement.where(Stage.project_id == project_id)
    elif not access.is_admin:
        project_ids = accessible_project_ids(access)
        if not project_ids:
            return []
        statement = statement.where(Stage.project_id.in_(project_ids))
    return list(db.scalars(statement))


@router.get("/projects/{project_id}/stages", response_model=list[StageRead])
def list_project_stages(project_id: int, db: DBSession, access: MasterRead) -> list[Stage]:
    ensure_project_exists(db, project_id)
    ensure_project_access(access, project_id)
    statement = (
        select(Stage)
        .where(Stage.project_id == project_id)
        .order_by(Stage.sort_order, Stage.id)
    )
    return list(db.scalars(statement))


@router.post("/stages", response_model=StageRead, status_code=status.HTTP_201_CREATED)
def create_stage(payload: StageCreate, db: DBSession, access: MasterWrite) -> Stage:
    ensure_project_exists(db, payload.project_id)
    ensure_project_write_access(access, payload.project_id)
    stage = Stage(**payload.model_dump())
    db.add(stage)
    commit_or_conflict(db, "stage code already exists in this project")
    db.refresh(stage)
    return stage


@router.put("/stages/{stage_id}", response_model=StageRead)
def update_stage(
    stage_id: int,
    payload: StageUpdate,
    db: DBSession,
    access: MasterWrite,
) -> Stage:
    stage = get_or_404(db, Stage, stage_id, "stage")
    ensure_project_write_access(access, stage.project_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "project_id" in update_data:
        ensure_project_exists(db, update_data["project_id"])
        ensure_project_write_access(access, update_data["project_id"])
    for field, value in update_data.items():
        setattr(stage, field, value)
    commit_or_conflict(db, "stage code already exists in this project")
    db.refresh(stage)
    return stage


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage(stage_id: int, db: DBSession, access: MasterWrite) -> None:
    stage = get_or_404(db, Stage, stage_id, "stage")
    ensure_project_write_access(access, stage.project_id)
    db.delete(stage)
    db.commit()


@router.get("/stage-templates", response_model=list[StageTemplateRead])
def list_stage_templates(
    db: DBSession,
    access: MasterRead,
    project_id: int | None = None,
    stage_id: int | None = None,
) -> list[StageTemplate]:
    statement = select(StageTemplate).order_by(
        StageTemplate.project_id,
        StageTemplate.stage_id,
        StageTemplate.sort_order,
        StageTemplate.id,
    )
    if project_id is not None:
        ensure_project_exists(db, project_id)
        ensure_project_access(access, project_id)
        statement = statement.where(StageTemplate.project_id == project_id)
    elif not access.is_admin:
        project_ids = accessible_project_ids(access)
        if not project_ids:
            return []
        statement = statement.where(StageTemplate.project_id.in_(project_ids))
    if stage_id is not None:
        stage = get_or_404(db, Stage, stage_id, "stage")
        ensure_project_access(access, stage.project_id)
        statement = statement.where(StageTemplate.stage_id == stage_id)
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
) -> StageTemplate:
    ensure_project_exists(db, payload.project_id)
    ensure_project_write_access(access, payload.project_id)
    ensure_stage_belongs_to_project(db, payload.project_id, payload.stage_id)
    template = StageTemplate(**payload.model_dump())
    db.add(template)
    commit_or_conflict(db, "stage template item code already exists in this stage")
    db.refresh(template)
    return template


@router.put("/stage-templates/{template_id}", response_model=StageTemplateRead)
def update_stage_template(
    template_id: int,
    payload: StageTemplateUpdate,
    db: DBSession,
    access: MasterWrite,
) -> StageTemplate:
    template = get_or_404(db, StageTemplate, template_id, "stage template")
    ensure_project_write_access(access, template.project_id)
    update_data = payload.model_dump(exclude_unset=True)
    project_id = update_data.get("project_id", template.project_id)
    stage_id = update_data.get("stage_id", template.stage_id)
    ensure_project_exists(db, project_id)
    ensure_project_write_access(access, project_id)
    ensure_stage_belongs_to_project(db, project_id, stage_id)
    for field, value in update_data.items():
        setattr(template, field, value)
    commit_or_conflict(db, "stage template item code already exists in this stage")
    db.refresh(template)
    return template


@router.delete("/stage-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage_template(template_id: int, db: DBSession, access: MasterWrite) -> None:
    template = get_or_404(db, StageTemplate, template_id, "stage template")
    ensure_project_write_access(access, template.project_id)
    db.delete(template)
    db.commit()


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
    _: DictionaryWriteAccess,
) -> Dictionary:
    dictionary = Dictionary(**payload.model_dump())
    db.add(dictionary)
    commit_or_conflict(db, "dictionary value already exists in this type")
    db.refresh(dictionary)
    return dictionary


@router.put("/dictionaries/{dictionary_id}", response_model=DictionaryRead)
def update_dictionary(
    dictionary_id: int,
    payload: DictionaryUpdate,
    db: DBSession,
    _: DictionaryWriteAccess,
) -> Dictionary:
    dictionary = get_or_404(db, Dictionary, dictionary_id, "dictionary")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dictionary, field, value)
    commit_or_conflict(db, "dictionary value already exists in this type")
    db.refresh(dictionary)
    return dictionary


@router.delete("/dictionaries/{dictionary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dictionary(dictionary_id: int, db: DBSession, _: DictionaryWriteAccess) -> None:
    dictionary = get_or_404(db, Dictionary, dictionary_id, "dictionary")
    db.delete(dictionary)
    db.commit()
