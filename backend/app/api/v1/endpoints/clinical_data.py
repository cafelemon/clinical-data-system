from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.clinical_data import (
    DEFAULT_DATA_STATUS,
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
    SUBJECT_SECTION_SPECS,
)
from app.core.database import get_db
from app.models import Center, Project, Stage, StageFile, StageTemplate, Subject, SubjectItem
from app.models.clinical_data import SubjectSection
from app.schemas import (
    ClinicalDatasetRead,
    StageFileRead,
    SubjectCreate,
    SubjectItemRead,
    SubjectItemUpdate,
    SubjectRead,
    SubjectSectionRead,
    SubjectUpdate,
)

router = APIRouter()
ModelT = TypeVar("ModelT", Project, Center, Stage, StageFile, Subject, SubjectItem)
DBSession = Annotated[Session, Depends(get_db)]
ClinicalRead = Annotated[AccessContext, Depends(require_permission("clinical_data:read"))]
ClinicalWrite = Annotated[AccessContext, Depends(require_permission("clinical_data:write"))]


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


def ensure_project_access(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_center_belongs_to_project(db: Session, project_id: int, center_id: int) -> Center:
    center = get_or_404(db, Center, center_id, "center")
    if center.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="center does not belong to project",
        )
    return center


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


def ensure_dataset_scope(
    db: Session,
    access: AccessContext,
    project_id: int,
    center_id: int,
) -> Center:
    get_or_404(db, Project, project_id, "project")
    ensure_project_access(access, project_id)
    center = ensure_center_belongs_to_project(db, project_id, center_id)
    ensure_center_access(access, center)
    return center


def materialize_stage_files(
    db: Session,
    project_id: int,
    center_id: int,
    stage_id: int | None = None,
) -> list[StageFile]:
    template_statement = select(StageTemplate).where(StageTemplate.project_id == project_id)
    if stage_id is not None:
        template_statement = template_statement.where(StageTemplate.stage_id == stage_id)
    templates = list(
        db.scalars(
            template_statement.order_by(
                StageTemplate.stage_id,
                StageTemplate.sort_order,
                StageTemplate.id,
            )
        )
    )

    for template in templates:
        stage_file = db.scalar(
            select(StageFile).where(
                StageFile.project_id == project_id,
                StageFile.center_id == center_id,
                StageFile.stage_id == template.stage_id,
                StageFile.stage_template_id == template.id,
            )
        )
        if stage_file is None:
            db.add(
                StageFile(
                    project_id=project_id,
                    center_id=center_id,
                    stage_id=template.stage_id,
                    stage_template_id=template.id,
                    file_name=template.item_name,
                    file_type=template.item_code,
                    upload_status=DEFAULT_UPLOAD_STATUS,
                    review_status=DEFAULT_REVIEW_STATUS,
                )
            )
        else:
            stage_file.file_name = template.item_name
            stage_file.file_type = template.item_code
    if templates:
        db.commit()

    stage_file_statement = select(StageFile).where(
        StageFile.project_id == project_id,
        StageFile.center_id == center_id,
    )
    if stage_id is not None:
        stage_file_statement = stage_file_statement.where(StageFile.stage_id == stage_id)
    return list(
        db.scalars(
            stage_file_statement.order_by(
                StageFile.stage_id,
                StageFile.id,
            )
        )
    )


def create_default_subject_sections(db: Session, subject: Subject) -> None:
    for section_spec in SUBJECT_SECTION_SPECS:
        section = SubjectSection(
            project_id=subject.project_id,
            subject_id=subject.id,
            section_code=section_spec.code,
            name=section_spec.name,
            visit_name=section_spec.visit_name,
            time_window=section_spec.time_window,
            sort_order=section_spec.sort_order,
            description=section_spec.description,
        )
        db.add(section)
        db.flush()
        for item_spec in section_spec.items:
            db.add(
                SubjectItem(
                    subject_id=subject.id,
                    section_id=section.id,
                    item_name=item_spec.name,
                    item_code=item_spec.code,
                    sort_order=item_spec.sort_order,
                    upload_status=DEFAULT_UPLOAD_STATUS,
                    review_status=DEFAULT_REVIEW_STATUS,
                )
            )


def scoped_subject_statement(access: AccessContext):
    statement = select(Subject).order_by(Subject.project_id, Subject.center_id, Subject.id)
    if access.is_admin:
        return statement
    conditions = []
    if access.project_ids:
        conditions.append(Subject.project_id.in_(access.project_ids))
    if access.center_ids:
        conditions.append(Subject.center_id.in_(access.center_ids))
    if not conditions:
        return statement.where(Subject.id == -1)
    return statement.where(or_(*conditions))


def ensure_subject_access(access: AccessContext, subject: Subject) -> None:
    if not access.can_access_center(subject.center_id, subject.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subject scope denied")


def recalculate_subject_status(db: Session, subject: Subject) -> None:
    items = list(db.scalars(select(SubjectItem).where(SubjectItem.subject_id == subject.id)))
    if not items or all(item.upload_status == DEFAULT_UPLOAD_STATUS for item in items):
        subject.data_status = DEFAULT_DATA_STATUS
    elif all(item.upload_status == "uploaded" for item in items) and all(
        item.review_status == "approved" for item in items
    ):
        subject.data_status = "complete"
    else:
        subject.data_status = "in_progress"

    if items and all(item.review_status == "approved" for item in items):
        subject.review_status = "approved"
    elif any(item.review_status == "rejected" for item in items):
        subject.review_status = "rejected"
    else:
        subject.review_status = DEFAULT_REVIEW_STATUS


@router.get("/clinical-datasets", response_model=ClinicalDatasetRead)
def get_clinical_dataset(
    db: DBSession,
    access: ClinicalRead,
    project_id: int | None = None,
    center_id: int | None = None,
) -> ClinicalDatasetRead:
    if project_id is None or center_id is None:
        return ClinicalDatasetRead(project_id=project_id, center_id=center_id)
    ensure_dataset_scope(db, access, project_id, center_id)
    stages = list(
        db.scalars(
            select(Stage)
            .where(Stage.project_id == project_id)
            .order_by(Stage.sort_order, Stage.id)
        )
    )
    stage_by_code = {stage.code: stage for stage in stages}
    startup_files = (
        materialize_stage_files(db, project_id, center_id, stage_by_code["STARTUP"].id)
        if "STARTUP" in stage_by_code
        else []
    )
    closeout_files = (
        materialize_stage_files(db, project_id, center_id, stage_by_code["CLOSEOUT"].id)
        if "CLOSEOUT" in stage_by_code
        else []
    )
    subjects = list(
        db.scalars(
            select(Subject)
            .where(Subject.project_id == project_id, Subject.center_id == center_id)
            .order_by(Subject.id)
        )
    )
    return ClinicalDatasetRead(
        project_id=project_id,
        center_id=center_id,
        stages=stages,
        startup_files=startup_files,
        subjects=subjects,
        closeout_files=closeout_files,
        stage_file_count=len(startup_files) + len(closeout_files),
        subject_count=len(subjects),
    )


@router.get("/stage-files", response_model=list[StageFileRead])
def list_stage_files(
    db: DBSession,
    access: ClinicalRead,
    project_id: Annotated[int, Query()],
    center_id: Annotated[int, Query()],
    stage_id: int | None = None,
) -> list[StageFile]:
    ensure_dataset_scope(db, access, project_id, center_id)
    if stage_id is not None:
        ensure_stage_belongs_to_project(db, project_id, stage_id)
    return materialize_stage_files(db, project_id, center_id, stage_id)


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(
    db: DBSession,
    access: ClinicalRead,
    project_id: int | None = None,
    center_id: int | None = None,
) -> list[Subject]:
    statement = scoped_subject_statement(access)
    if project_id is not None:
        get_or_404(db, Project, project_id, "project")
        ensure_project_access(access, project_id)
        statement = statement.where(Subject.project_id == project_id)
        if not access.is_admin and project_id not in access.project_ids and access.center_ids:
            statement = statement.where(Subject.center_id.in_(access.center_ids))
    if center_id is not None:
        center = get_or_404(db, Center, center_id, "center")
        if project_id is not None and center.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="center does not belong to project",
            )
        ensure_center_access(access, center)
        statement = statement.where(Subject.center_id == center_id)
    return list(db.scalars(statement))


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, db: DBSession, access: ClinicalWrite) -> Subject:
    center = ensure_dataset_scope(db, access, payload.project_id, payload.center_id)
    subject_data = payload.model_dump()
    subject_data["center_id"] = center.id
    subject = Subject(**subject_data, added_by=access.user.id)
    db.add(subject)
    try:
        db.flush()
        create_default_subject_sections(db, subject)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="screening number already exists in this project center",
        ) from exc
    db.refresh(subject)
    return subject


@router.get("/subjects/{subject_id}", response_model=SubjectRead)
def get_subject(subject_id: int, db: DBSession, access: ClinicalRead) -> Subject:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    return subject


@router.put("/subjects/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    db: DBSession,
    access: ClinicalWrite,
) -> Subject:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    update_data = payload.model_dump(exclude_unset=True)
    if "center_id" in update_data:
        target_center = ensure_center_belongs_to_project(
            db,
            subject.project_id,
            update_data["center_id"],
        )
        ensure_center_access(access, target_center)
    for field, value in update_data.items():
        setattr(subject, field, value)
    commit_or_conflict(db, "screening number already exists in this project center")
    db.refresh(subject)
    return subject


@router.get("/subjects/{subject_id}/sections", response_model=list[SubjectSectionRead])
def list_subject_sections(
    subject_id: int,
    db: DBSession,
    access: ClinicalRead,
) -> list[SubjectSection]:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    return list(
        db.scalars(
            select(SubjectSection)
            .where(SubjectSection.subject_id == subject_id)
            .order_by(SubjectSection.sort_order, SubjectSection.id)
        )
    )


@router.get("/subjects/{subject_id}/items", response_model=list[SubjectItemRead])
def list_subject_items(
    subject_id: int,
    db: DBSession,
    access: ClinicalRead,
) -> list[SubjectItem]:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    return list(
        db.scalars(
            select(SubjectItem)
            .join(SubjectSection, SubjectItem.section_id == SubjectSection.id)
            .where(SubjectItem.subject_id == subject_id)
            .order_by(SubjectSection.sort_order, SubjectItem.sort_order, SubjectItem.id)
        )
    )


@router.put("/subject-items/{item_id}", response_model=SubjectItemRead)
def update_subject_item(
    item_id: int,
    payload: SubjectItemUpdate,
    db: DBSession,
    access: ClinicalWrite,
) -> SubjectItem:
    item = get_or_404(db, SubjectItem, item_id, "subject item")
    subject = get_or_404(db, Subject, item.subject_id, "subject")
    ensure_subject_access(access, subject)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    recalculate_subject_status(db, subject)
    db.commit()
    db.refresh(item)
    return item
