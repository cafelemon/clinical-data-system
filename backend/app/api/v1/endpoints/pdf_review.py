from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.api.v1.endpoints.files import (
    mark_binding_file_changed,
    relative_directory,
    resolve_binding,
    write_upload,
)
from app.core.clinical_data import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    UPLOAD_REPLACED,
    UPLOAD_SUPPLEMENT_REQUIRED,
    UPLOAD_UPLOADED,
)
from app.core.database import get_db
from app.models import (
    CorrectionTask,
    CorrectionTaskAnnotation,
    FileAsset,
    FileVersion,
    PdfAnnotation,
    ReviewRecord,
    StageFile,
    Subject,
    SubjectItem,
)
from app.schemas import (
    CorrectionTaskCreate,
    CorrectionTaskRead,
    CorrectionTaskReturnRequest,
    CorrectionTaskReviewRequest,
    CorrectionTaskSubmitRead,
    PdfAnnotationCreate,
    PdfAnnotationRead,
    PdfAnnotationUpdate,
    PdfReviewFileRead,
)
from app.services.audit import record_operation
from app.services.clinical_status import recalculate_subject_status

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
PdfReviewReadAccess = Annotated[AccessContext, Depends(require_permission("pdf_review:read"))]
PdfReviewAnnotateAccess = Annotated[
    AccessContext,
    Depends(require_permission("pdf_review:annotate")),
]
CorrectionTaskReadAccess = Annotated[
    AccessContext,
    Depends(require_permission("correction_tasks:read")),
]
CorrectionTaskCreateAccess = Annotated[
    AccessContext,
    Depends(require_permission("correction_tasks:create")),
]
CorrectionTaskSubmitAccess = Annotated[
    AccessContext,
    Depends(require_permission("correction_tasks:submit")),
]
CorrectionTaskReviewAccess = Annotated[
    AccessContext,
    Depends(require_permission("correction_tasks:review")),
]


def now_utc() -> datetime:
    return datetime.now(UTC)


def get_or_404(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return item


def ensure_center_scope(access: AccessContext, project_id: int, center_id: int) -> None:
    if not access.can_access_center(center_id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")


def ensure_file_scope(access: AccessContext, file_asset: FileAsset) -> None:
    ensure_center_scope(access, file_asset.project_id, file_asset.center_id)


def ensure_pdf_file(file_version: FileVersion) -> None:
    if file_version.mime_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="PDF only")


def resolve_file_version(
    db: Session,
    file_asset: FileAsset,
    *,
    version: int | None = None,
    file_version_id: int | None = None,
) -> FileVersion:
    statement = select(FileVersion).where(FileVersion.file_id == file_asset.id)
    if file_version_id is not None:
        statement = statement.where(FileVersion.id == file_version_id)
    else:
        statement = statement.where(FileVersion.version == (version or file_asset.version))
    file_version = db.scalar(statement)
    if file_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file version not found")
    ensure_pdf_file(file_version)
    return file_version


def list_annotations_for_version(db: Session, file_version_id: int) -> list[PdfAnnotation]:
    return list(
        db.scalars(
            select(PdfAnnotation)
            .where(
                PdfAnnotation.file_version_id == file_version_id,
                PdfAnnotation.deleted_at.is_(None),
            )
            .order_by(PdfAnnotation.page_no, PdfAnnotation.id)
        )
    )


def can_manage_review(access: AccessContext) -> bool:
    return access.has_permission("pdf_review:manage")


def ensure_annotation_owner_or_manager(access: AccessContext, annotation: PdfAnnotation) -> None:
    if can_manage_review(access) or annotation.created_by == access.user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Annotation owner denied")


def task_annotations(db: Session, task: CorrectionTask) -> list[PdfAnnotation]:
    annotation_ids = list(
        db.scalars(
            select(CorrectionTaskAnnotation.annotation_id)
            .where(CorrectionTaskAnnotation.task_id == task.id)
            .order_by(CorrectionTaskAnnotation.id)
        )
    )
    if not annotation_ids:
        return []
    return list(
        db.scalars(
            select(PdfAnnotation)
            .where(
                PdfAnnotation.id.in_(annotation_ids),
                PdfAnnotation.deleted_at.is_(None),
            )
            .order_by(PdfAnnotation.page_no, PdfAnnotation.id)
        )
    )


ISSUE_LABELS = {
    "missing_page": "缺页",
    "wrong_page": "错页",
    "unclear_scan": "扫描不清晰",
    "inconsistent_info": "信息不一致",
    "missing_signature": "签名缺失",
    "missing_stamp": "盖章缺失",
    "missing_date": "日期缺失",
    "wrong_subject": "受试者不匹配",
    "wrong_document": "资料类型不匹配",
    "other": "其他",
}
ACTIVE_TASK_FINAL_STATUSES = ("closed", "cancelled")
ACTIONABLE_ANNOTATION_STATUSES = ("open", "task_created", "submitted", "rejected")
TASK_STATUS_PRIORITY = {
    "pending": 1,
    "processing": 2,
    "returned": 3,
    "submitted": 4,
}


def is_actionable_annotation(annotation: PdfAnnotation | None) -> bool:
    return (
        annotation is not None
        and annotation.deleted_at is None
        and annotation.status in ACTIONABLE_ANNOTATION_STATUSES
    )


def get_active_tasks_for_file(db: Session, file_id: int) -> list[CorrectionTask]:
    return list(
        db.scalars(
            select(CorrectionTask)
            .where(
                CorrectionTask.file_id == file_id,
                ~CorrectionTask.status.in_(ACTIVE_TASK_FINAL_STATUSES),
            )
            .order_by(CorrectionTask.updated_at.desc(), CorrectionTask.id.desc())
        )
    )


def actionable_annotations_for_task(db: Session, task: CorrectionTask) -> list[PdfAnnotation]:
    return list(
        db.scalars(
            select(PdfAnnotation)
            .join(
                CorrectionTaskAnnotation,
                PdfAnnotation.id == CorrectionTaskAnnotation.annotation_id,
            )
            .where(
                CorrectionTaskAnnotation.task_id == task.id,
                PdfAnnotation.deleted_at.is_(None),
                PdfAnnotation.status.in_(ACTIONABLE_ANNOTATION_STATUSES),
            )
            .order_by(PdfAnnotation.page_no, PdfAnnotation.id)
        )
    )


def cancel_task(task: CorrectionTask, reason: str) -> None:
    task.status = "cancelled"
    task.review_result = "cancelled"
    task.review_comment = reason
    task.closed_at = now_utc()


def normalize_active_tasks_for_file(db: Session, file_asset: FileAsset) -> CorrectionTask | None:
    tasks = get_active_tasks_for_file(db, file_asset.id)
    if not tasks:
        return None

    actionable_by_task = {task.id: actionable_annotations_for_task(db, task) for task in tasks}
    candidates = [
        task
        for task in tasks
        if task.status != "pending" or len(actionable_by_task[task.id]) > 0
    ]
    if not candidates:
        for task in tasks:
            for link in list(task.task_annotations):
                db.delete(link)
            cancel_task(task, "空整改任务自动撤销")
        db.flush()
        return None

    def task_rank(task: CorrectionTask) -> tuple[int, int, datetime, int]:
        timestamp = task.updated_at or task.created_at
        return (
            TASK_STATUS_PRIORITY.get(task.status, 0),
            len(actionable_by_task[task.id]),
            timestamp,
            task.id,
        )

    primary = max(candidates, key=task_rank)
    primary_annotation_ids = {link.annotation_id for link in primary.task_annotations}
    for task in tasks:
        if task.id == primary.id:
            continue
        for link in list(task.task_annotations):
            annotation = link.annotation
            if is_actionable_annotation(annotation) and annotation.id not in primary_annotation_ids:
                link.task_id = primary.id
                annotation.status = annotation_status_for_task(primary)
                primary_annotation_ids.add(annotation.id)
                continue
            db.delete(link)
        if primary.latest_file_version_id is None and task.latest_file_version_id is not None:
            primary.latest_file_version_id = task.latest_file_version_id
        cancel_task(task, f"合并到整改任务 {primary.task_no}")
    db.flush()
    sync_task_description(db, primary)
    db.flush()
    return primary


def get_active_task_for_file(db: Session, file_asset: FileAsset) -> CorrectionTask | None:
    return normalize_active_tasks_for_file(db, file_asset)


def actionable_annotation_exists_for_task(task_id):
    return (
        select(CorrectionTaskAnnotation.id)
        .join(PdfAnnotation, PdfAnnotation.id == CorrectionTaskAnnotation.annotation_id)
        .where(
            CorrectionTaskAnnotation.task_id == task_id,
            PdfAnnotation.deleted_at.is_(None),
            PdfAnnotation.status.in_(ACTIONABLE_ANNOTATION_STATUSES),
        )
        .exists()
    )


def task_title_for_file(file_version: FileVersion) -> str:
    return f"{file_version.original_name} 整改任务"


def annotation_summary(annotation: PdfAnnotation) -> str:
    issue_label = ISSUE_LABELS.get(annotation.issue_type, annotation.issue_type)
    return f"第{annotation.page_no}页 {issue_label}：{annotation.comment.strip()}"


def sync_task_description(db: Session, task: CorrectionTask) -> None:
    annotations = task_annotations(db, task)
    if not annotations:
        task.description = None
        return
    task.description = "\n".join(
        annotation_summary(annotation) for annotation in annotations
    )[:4000]


def annotation_status_for_task(task: CorrectionTask) -> str:
    if task.status == "submitted":
        return "submitted"
    if task.status == "returned":
        return "rejected"
    if task.status == "closed":
        return "resolved"
    return "task_created"


def current_target_status(
    db: Session,
    file_asset: FileAsset,
) -> tuple[str | None, str | None]:
    _, target, _ = target_for_file(db, file_asset)
    if target is None:
        return None, None
    return target.upload_status, target.review_status


def create_active_task(
    db: Session,
    access: AccessContext,
    file_asset: FileAsset,
    file_version: FileVersion,
) -> CorrectionTask:
    if file_asset.stage_file_id is None and file_asset.subject_item_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file does not support correction tasks",
        )
    previous_upload_status, previous_review_status = current_target_status(db, file_asset)
    task = CorrectionTask(
        task_no=f"CORR-{uuid4().hex[:12].upper()}",
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        subject_id=file_asset.subject_id,
        subject_item_id=file_asset.subject_item_id,
        file_id=file_asset.id,
        source_file_version_id=file_version.id,
        latest_file_version_id=None,
        title=task_title_for_file(file_version),
        description=None,
        previous_upload_status=previous_upload_status,
        previous_review_status=previous_review_status,
        assigned_to=file_asset.uploaded_by,
        created_by=access.user.id,
        status="pending",
        due_date=None,
    )
    db.add(task)
    db.flush()
    return task


def ensure_annotation_not_linked_to_other_task(
    db: Session,
    annotation: PdfAnnotation,
    task: CorrectionTask,
) -> None:
    conflict = db.scalar(
        select(CorrectionTask.id)
        .join(CorrectionTaskAnnotation, CorrectionTask.id == CorrectionTaskAnnotation.task_id)
        .where(
            CorrectionTaskAnnotation.annotation_id == annotation.id,
            CorrectionTask.id != task.id,
        )
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="annotation already linked to correction task",
        )


def active_task_for_annotation(db: Session, annotation_id: int) -> CorrectionTask | None:
    return db.scalar(
        select(CorrectionTask)
        .join(CorrectionTaskAnnotation, CorrectionTask.id == CorrectionTaskAnnotation.task_id)
        .where(
            CorrectionTaskAnnotation.annotation_id == annotation_id,
            ~CorrectionTask.status.in_(ACTIVE_TASK_FINAL_STATUSES),
        )
        .order_by(CorrectionTask.updated_at.desc(), CorrectionTask.id.desc())
    )


def attach_annotations_to_task(
    db: Session,
    task: CorrectionTask,
    annotations: list[PdfAnnotation],
    *,
    actor_id: int,
) -> None:
    existing_ids = {item.annotation_id for item in task.task_annotations}
    next_status = annotation_status_for_task(task)
    for annotation in annotations:
        ensure_annotation_not_linked_to_other_task(db, annotation, task)
        if annotation.id not in existing_ids:
            db.add(CorrectionTaskAnnotation(task_id=task.id, annotation_id=annotation.id))
            existing_ids.add(annotation.id)
        annotation.status = next_status
        annotation.updated_by = actor_id
    db.flush()
    sync_task_description(db, task)


def restore_target_status_after_cancel(
    db: Session,
    file_asset: FileAsset,
    task: CorrectionTask,
) -> None:
    fallback_upload_status = UPLOAD_REPLACED if file_asset.version > 1 else UPLOAD_UPLOADED
    fallback_review_status = REVIEW_PENDING
    set_target_status(
        db,
        file_asset,
        upload_status=task.previous_upload_status or fallback_upload_status,
        review_status=task.previous_review_status or fallback_review_status,
    )


def task_to_read(db: Session, task: CorrectionTask) -> CorrectionTaskRead:
    sync_task_description(db, task)
    annotations = task_annotations(db, task)
    return CorrectionTaskRead(
        id=task.id,
        task_no=task.task_no,
        project_id=task.project_id,
        center_id=task.center_id,
        subject_id=task.subject_id,
        subject_item_id=task.subject_item_id,
        file_id=task.file_id,
        source_file_version_id=task.source_file_version_id,
        latest_file_version_id=task.latest_file_version_id,
        title=task.title,
        description=task.description,
        assigned_to=task.assigned_to,
        created_by=task.created_by,
        status=task.status,
        due_date=task.due_date,
        submitted_at=task.submitted_at,
        reviewed_at=task.reviewed_at,
        closed_at=task.closed_at,
        submission_remark=task.submission_remark,
        review_comment=task.review_comment,
        review_result=task.review_result,
        created_at=task.created_at,
        updated_at=task.updated_at,
        annotations=[PdfAnnotationRead.model_validate(annotation) for annotation in annotations],
    )


def task_query(access: AccessContext):
    statement = select(CorrectionTask).order_by(
        CorrectionTask.updated_at.desc(),
        CorrectionTask.id.desc(),
    )
    if access.is_admin:
        return statement
    conditions = []
    if access.project_ids:
        conditions.append(CorrectionTask.project_id.in_(access.project_ids))
    if access.center_ids:
        conditions.append(CorrectionTask.center_id.in_(access.center_ids))
    conditions.append(CorrectionTask.assigned_to == access.user.id)
    conditions.append(CorrectionTask.created_by == access.user.id)
    return statement.where(or_(*conditions))


def ensure_task_scope(access: AccessContext, task: CorrectionTask) -> None:
    if access.is_admin:
        return
    if task.assigned_to == access.user.id or task.created_by == access.user.id:
        return
    ensure_center_scope(access, task.project_id, task.center_id)


def ensure_task_submit_scope(access: AccessContext, task: CorrectionTask) -> None:
    if (
        access.is_admin
        or task.assigned_to == access.user.id
        or access.has_permission("correction_tasks:review")
        or access.has_permission("correction_tasks:create")
    ):
        ensure_task_scope(access, task)
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Task submit denied")


def target_for_file(
    db: Session,
    file_asset: FileAsset,
) -> tuple[str | None, StageFile | SubjectItem | None, Subject | None]:
    if file_asset.stage_file_id is not None:
        return "stage_file", db.get(StageFile, file_asset.stage_file_id), None
    if file_asset.subject_item_id is not None:
        subject_item = db.get(SubjectItem, file_asset.subject_item_id)
        subject = db.get(Subject, subject_item.subject_id) if subject_item is not None else None
        return "subject_item", subject_item, subject
    return None, None, None


def set_target_status(
    db: Session,
    file_asset: FileAsset,
    *,
    upload_status: str | None = None,
    review_status: str | None = None,
) -> None:
    _, target, subject = target_for_file(db, file_asset)
    if target is None:
        return
    if upload_status is not None:
        target.upload_status = upload_status
    if review_status is not None:
        target.review_status = review_status
    if isinstance(target, SubjectItem) and subject is not None:
        recalculate_subject_status(db, subject)


def add_review_record(
    db: Session,
    access: AccessContext,
    file_asset: FileAsset,
    *,
    action: str,
    review_status: str,
    comment: str | None,
) -> None:
    target_type, target, _ = target_for_file(db, file_asset)
    if target_type is None or target is None:
        return
    db.add(
        ReviewRecord(
            target_type=target_type,
            target_id=target.id,
            action=action,
            review_status=review_status,
            reviewer_id=access.user.id,
            comment=comment,
        )
    )


@router.get("/pdf-review/files/{file_id}", response_model=PdfReviewFileRead)
def get_pdf_review_file(
    file_id: int,
    db: DBSession,
    access: PdfReviewReadAccess,
    version: int | None = None,
    file_version_id: int | None = None,
) -> PdfReviewFileRead:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = resolve_file_version(
        db,
        file_asset,
        version=version,
        file_version_id=file_version_id,
    )
    versions = list(
        db.scalars(
            select(FileVersion)
            .where(FileVersion.file_id == file_asset.id)
            .order_by(FileVersion.version)
        )
    )
    active_task = get_active_task_for_file(db, file_asset)
    active_annotations = task_annotations(db, active_task) if active_task is not None else []
    return PdfReviewFileRead(
        file_id=file_asset.id,
        file_version_id=file_version.id,
        file_name=file_version.original_name,
        preview_url=f"/api/files/{file_asset.id}/preview?version={file_version.version}",
        version=file_version.version,
        mime_type=file_version.mime_type,
        status=file_asset.status,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        subject_id=file_asset.subject_id,
        subject_item_id=file_asset.subject_item_id,
        ssu_progress_id=file_asset.ssu_progress_id,
        read_only=file_asset.ssu_progress_id is not None,
        active_task_id=active_task.id if active_task is not None else None,
        active_task_status=active_task.status if active_task is not None else None,
        active_task_annotation_count=len(active_annotations),
        versions=versions,
        annotations=list_annotations_for_version(db, file_version.id),
    )


@router.get(
    "/pdf-review/files/{file_id}/annotations",
    response_model=list[PdfAnnotationRead],
)
def list_pdf_annotations(
    file_id: int,
    db: DBSession,
    access: PdfReviewReadAccess,
    version: int | None = None,
    file_version_id: int | None = None,
) -> list[PdfAnnotation]:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = resolve_file_version(
        db,
        file_asset,
        version=version,
        file_version_id=file_version_id,
    )
    return list_annotations_for_version(db, file_version.id)


@router.post(
    "/pdf-review/annotations",
    response_model=PdfAnnotationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_pdf_annotation(
    payload: PdfAnnotationCreate,
    db: DBSession,
    access: PdfReviewAnnotateAccess,
    request: Request,
) -> PdfAnnotation:
    file_asset = get_or_404(db, FileAsset, payload.file_id, "file")
    ensure_file_scope(access, file_asset)
    if file_asset.ssu_progress_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSU files are read-only in PDF review",
        )
    file_version = resolve_file_version(
        db,
        file_asset,
        file_version_id=payload.file_version_id,
    )
    active_task = get_active_task_for_file(db, file_asset)
    created_task = False
    annotation = PdfAnnotation(
        file_id=file_asset.id,
        file_version_id=file_version.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        subject_id=file_asset.subject_id,
        subject_item_id=file_asset.subject_item_id,
        page_no=payload.page_no,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        comment=payload.comment,
        issue_type=payload.issue_type,
        severity=payload.severity,
        status="open",
        created_by=access.user.id,
        updated_by=access.user.id,
    )
    db.add(annotation)
    db.flush()
    if active_task is None:
        active_task = create_active_task(db, access, file_asset, file_version)
        created_task = True
    attach_annotations_to_task(db, active_task, [annotation], actor_id=access.user.id)
    if created_task:
        set_target_status(
            db,
            file_asset,
            upload_status=UPLOAD_SUPPLEMENT_REQUIRED,
            review_status=REVIEW_REJECTED,
        )
        add_review_record(
            db,
            access,
            file_asset,
            action="reject",
            review_status=REVIEW_REJECTED,
            comment=active_task.description,
        )
        record_operation(
            db,
            action="correction_task.create",
            request=request,
            access=access,
            target_type="correction_task",
            target_id=active_task.id,
            project_id=active_task.project_id,
            center_id=active_task.center_id,
            detail={
                "file_id": active_task.file_id,
                "file_version_id": active_task.source_file_version_id,
                "annotation_ids": [annotation.id],
                "assigned_to": active_task.assigned_to,
                "auto_created": True,
            },
        )
    record_operation(
        db,
        action="pdf_review.annotation_create",
        request=request,
        access=access,
        target_type="pdf_annotation",
        target_id=annotation.id,
        project_id=annotation.project_id,
        center_id=annotation.center_id,
        detail={
            "file_id": annotation.file_id,
            "file_version_id": annotation.file_version_id,
            "page_no": annotation.page_no,
            "issue_type": annotation.issue_type,
            "severity": annotation.severity,
            "task_id": active_task.id,
            "task_created": created_task,
        },
    )
    db.commit()
    db.refresh(annotation)
    return annotation


@router.patch("/pdf-review/annotations/{annotation_id}", response_model=PdfAnnotationRead)
def update_pdf_annotation(
    annotation_id: int,
    payload: PdfAnnotationUpdate,
    db: DBSession,
    access: PdfReviewAnnotateAccess,
    request: Request,
) -> PdfAnnotation:
    annotation = get_or_404(db, PdfAnnotation, annotation_id, "pdf annotation")
    file_asset = get_or_404(db, FileAsset, annotation.file_id, "file")
    linked_task = active_task_for_annotation(db, annotation.id)
    ensure_file_scope(access, file_asset)
    ensure_annotation_owner_or_manager(access, annotation)
    if annotation.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="annotation deleted")
    update_data = payload.model_dump(exclude_unset=True)
    x = update_data.get("x", annotation.x)
    y = update_data.get("y", annotation.y)
    width = update_data.get("width", annotation.width)
    height = update_data.get("height", annotation.height)
    if x + width > 1 or y + height > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="annotation rectangle exceeds page",
        )
    for field, value in update_data.items():
        setattr(annotation, field, value)
    annotation.updated_by = access.user.id
    if annotation.status in {"resolved", "closed"} and annotation.resolved_at is None:
        annotation.resolved_by = access.user.id
        annotation.resolved_at = now_utc()
    if linked_task is not None:
        sync_task_description(db, linked_task)
    record_operation(
        db,
        action="pdf_review.annotation_update",
        request=request,
        access=access,
        target_type="pdf_annotation",
        target_id=annotation.id,
        project_id=annotation.project_id,
        center_id=annotation.center_id,
        detail={"changed_fields": sorted(update_data)},
    )
    db.commit()
    db.refresh(annotation)
    return annotation


@router.delete("/pdf-review/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdf_annotation(
    annotation_id: int,
    db: DBSession,
    access: PdfReviewAnnotateAccess,
    request: Request,
) -> None:
    annotation = get_or_404(db, PdfAnnotation, annotation_id, "pdf annotation")
    file_asset = get_or_404(db, FileAsset, annotation.file_id, "file")
    linked_task = active_task_for_annotation(db, annotation.id)
    ensure_file_scope(access, file_asset)
    ensure_annotation_owner_or_manager(access, annotation)
    if linked_task is not None and linked_task.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="annotation cannot be removed after correction flow has started",
        )
    if annotation.deleted_at is None:
        annotation.status = "closed"
        annotation.deleted_by = access.user.id
        annotation.deleted_at = now_utc()
        annotation.updated_by = access.user.id
    task_cancelled = False
    if linked_task is not None:
        links_to_remove = [
            item for item in linked_task.task_annotations if item.annotation_id == annotation.id
        ]
        for link in links_to_remove:
            db.delete(link)
        db.flush()
        sync_task_description(db, linked_task)
        if len(task_annotations(db, linked_task)) == 0:
            linked_task.status = "cancelled"
            linked_task.review_result = "cancelled"
            linked_task.review_comment = "批注删除后自动撤销"
            linked_task.closed_at = now_utc()
            linked_task.submitted_at = None
            linked_task.reviewed_at = None
            linked_task.latest_file_version_id = None
            restore_target_status_after_cancel(db, file_asset, linked_task)
            task_cancelled = True
            record_operation(
                db,
                action="correction_task.cancel",
                request=request,
                access=access,
                target_type="correction_task",
                target_id=linked_task.id,
                project_id=linked_task.project_id,
                center_id=linked_task.center_id,
                detail={
                    "file_id": linked_task.file_id,
                    "reason": "annotation_deleted",
                },
            )
    record_operation(
        db,
        action="pdf_review.annotation_delete",
        request=request,
        access=access,
        target_type="pdf_annotation",
        target_id=annotation.id,
        project_id=annotation.project_id,
        center_id=annotation.center_id,
        detail={
            "file_id": annotation.file_id,
            "file_version_id": annotation.file_version_id,
            "task_id": linked_task.id if linked_task is not None else None,
            "task_cancelled": task_cancelled,
        },
    )
    db.commit()


@router.get("/correction-tasks", response_model=list[CorrectionTaskRead])
def list_correction_tasks(
    db: DBSession,
    access: CorrectionTaskReadAccess,
    assigned_to_me: bool = False,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    file_id: int | None = None,
    subject_id: int | None = None,
) -> list[CorrectionTaskRead]:
    if file_id is not None:
        file_asset = get_or_404(db, FileAsset, file_id, "file")
        ensure_file_scope(access, file_asset)
        get_active_task_for_file(db, file_asset)

    statement = task_query(access)
    if status_filter is not None:
        statement = statement.where(CorrectionTask.status == status_filter)
    else:
        statement = statement.where(
            CorrectionTask.status != "cancelled",
            or_(
                CorrectionTask.status != "pending",
                actionable_annotation_exists_for_task(CorrectionTask.id),
            ),
        )
    if assigned_to_me:
        statement = statement.where(CorrectionTask.assigned_to == access.user.id)
    if file_id is not None:
        statement = statement.where(CorrectionTask.file_id == file_id)
    if subject_id is not None:
        statement = statement.where(CorrectionTask.subject_id == subject_id)
    tasks = list(db.scalars(statement))
    for task in tasks:
        ensure_task_scope(access, task)
    return [task_to_read(db, task) for task in tasks]


@router.get("/correction-tasks/{task_id}", response_model=CorrectionTaskRead)
def get_correction_task(
    task_id: int,
    db: DBSession,
    access: CorrectionTaskReadAccess,
) -> CorrectionTaskRead:
    task = get_or_404(db, CorrectionTask, task_id, "correction task")
    ensure_task_scope(access, task)
    return task_to_read(db, task)


@router.post(
    "/correction-tasks",
    response_model=CorrectionTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_correction_task(
    payload: CorrectionTaskCreate,
    db: DBSession,
    access: CorrectionTaskCreateAccess,
    request: Request,
) -> CorrectionTaskRead:
    file_asset = get_or_404(db, FileAsset, payload.file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = resolve_file_version(
        db,
        file_asset,
        file_version_id=payload.file_version_id,
    )
    annotations = list(
        db.scalars(
            select(PdfAnnotation).where(
                PdfAnnotation.id.in_(payload.annotation_ids),
                PdfAnnotation.file_id == file_asset.id,
                PdfAnnotation.file_version_id == file_version.id,
                PdfAnnotation.deleted_at.is_(None),
            )
        )
    )
    if len(annotations) != len(set(payload.annotation_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="annotation set does not match file version",
        )
    task = get_active_task_for_file(db, file_asset)
    created_task = False
    if task is None:
        task = create_active_task(db, access, file_asset, file_version)
        created_task = True
        set_target_status(
            db,
            file_asset,
            upload_status=UPLOAD_SUPPLEMENT_REQUIRED,
            review_status=REVIEW_REJECTED,
        )
    attach_annotations_to_task(db, task, annotations, actor_id=access.user.id)
    if created_task:
        add_review_record(
            db,
            access,
            file_asset,
            action="reject",
            review_status=REVIEW_REJECTED,
            comment=task.description,
        )
    record_operation(
        db,
        action="correction_task.create",
        request=request,
        access=access,
        target_type="correction_task",
        target_id=task.id,
        project_id=task.project_id,
        center_id=task.center_id,
        detail={
            "file_id": task.file_id,
            "file_version_id": task.source_file_version_id,
            "annotation_ids": payload.annotation_ids,
            "assigned_to": task.assigned_to,
            "auto_created": created_task,
        },
    )
    db.commit()
    db.refresh(task)
    return task_to_read(db, task)


@router.post("/correction-tasks/{task_id}/submit", response_model=CorrectionTaskSubmitRead)
def submit_correction_task(
    task_id: int,
    db: DBSession,
    access: CorrectionTaskSubmitAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
    remark: Annotated[str | None, Form()] = None,
) -> CorrectionTaskSubmitRead:
    task = get_or_404(db, CorrectionTask, task_id, "correction task")
    ensure_task_submit_scope(access, task)
    if task.status in {"closed", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is closed")
    original_name = Path(file.filename or "correction.pdf").name
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF is supported")
    file_asset = get_or_404(db, FileAsset, task.file_id, "file")
    ensure_file_scope(access, file_asset)
    binding = resolve_binding(
        db,
        access,
        file_asset.stage_file_id,
        file_asset.subject_item_id,
        file_asset.ssu_progress_id,
    )
    next_version = file_asset.version + 1
    stored = write_upload(file, relative_directory(binding, file_asset.file_category, next_version))
    file_asset.original_name = stored.original_name
    file_asset.stored_name = stored.stored_name
    file_asset.file_ext = stored.file_ext
    file_asset.mime_type = stored.mime_type
    file_asset.file_size = stored.file_size
    file_asset.file_hash = stored.file_hash
    file_asset.storage_path = stored.storage_path
    file_asset.version = next_version
    file_asset.uploaded_by = access.user.id
    file_asset.status = "active"
    file_version = FileVersion(
        file_id=file_asset.id,
        version=next_version,
        storage_path=stored.storage_path,
        file_hash=stored.file_hash,
        file_size=stored.file_size,
        mime_type=stored.mime_type,
        original_name=stored.original_name,
        stored_name=stored.stored_name,
        uploaded_by=access.user.id,
        change_note=remark or f"整改任务 {task.task_no} 重新上传",
    )
    db.add(file_version)
    db.flush()
    mark_binding_file_changed(db, binding, UPLOAD_REPLACED)
    set_target_status(db, file_asset, review_status=REVIEW_PENDING)
    task.latest_file_version_id = file_version.id
    task.status = "submitted"
    task.submission_remark = remark
    task.submitted_at = now_utc()
    task.review_comment = None
    task.review_result = None
    task.closed_at = None
    for annotation in task_annotations(db, task):
        annotation.status = "submitted"
        annotation.updated_by = access.user.id
    add_review_record(
        db,
        access,
        file_asset,
        action="submit",
        review_status=REVIEW_PENDING,
        comment=remark,
    )
    record_operation(
        db,
        action="correction_task.submit",
        request=request,
        access=access,
        target_type="correction_task",
        target_id=task.id,
        project_id=task.project_id,
        center_id=task.center_id,
        detail={
            "file_id": file_asset.id,
            "new_version": file_version.version,
            "file_version_id": file_version.id,
            "remark": remark,
        },
    )
    db.commit()
    db.refresh(task)
    return CorrectionTaskSubmitRead(task=task_to_read(db, task))


@router.post("/correction-tasks/{task_id}/approve", response_model=CorrectionTaskRead)
def approve_correction_task(
    task_id: int,
    payload: CorrectionTaskReviewRequest,
    db: DBSession,
    access: CorrectionTaskReviewAccess,
    request: Request,
) -> CorrectionTaskRead:
    task = get_or_404(db, CorrectionTask, task_id, "correction task")
    ensure_task_scope(access, task)
    if task.status != "submitted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is not submitted")
    file_asset = get_or_404(db, FileAsset, task.file_id, "file")
    ensure_file_scope(access, file_asset)
    task.status = "closed"
    task.review_result = "approved"
    task.review_comment = payload.comment
    task.reviewed_at = now_utc()
    task.closed_at = task.reviewed_at
    for annotation in task_annotations(db, task):
        annotation.status = "resolved"
        annotation.resolved_by = access.user.id
        annotation.resolved_at = task.reviewed_at
        annotation.updated_by = access.user.id
    set_target_status(db, file_asset, review_status=REVIEW_APPROVED)
    add_review_record(
        db,
        access,
        file_asset,
        action="approve",
        review_status=REVIEW_APPROVED,
        comment=payload.comment,
    )
    record_operation(
        db,
        action="correction_task.approve",
        request=request,
        access=access,
        target_type="correction_task",
        target_id=task.id,
        project_id=task.project_id,
        center_id=task.center_id,
        detail={"file_id": task.file_id, "comment": payload.comment},
    )
    db.commit()
    db.refresh(task)
    return task_to_read(db, task)


@router.post("/correction-tasks/{task_id}/return", response_model=CorrectionTaskRead)
def return_correction_task(
    task_id: int,
    payload: CorrectionTaskReturnRequest,
    db: DBSession,
    access: CorrectionTaskReviewAccess,
    request: Request,
) -> CorrectionTaskRead:
    task = get_or_404(db, CorrectionTask, task_id, "correction task")
    ensure_task_scope(access, task)
    if task.status != "submitted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is not submitted")
    file_asset = get_or_404(db, FileAsset, task.file_id, "file")
    ensure_file_scope(access, file_asset)
    task.status = "returned"
    task.review_result = "returned"
    task.review_comment = payload.comment
    task.reviewed_at = now_utc()
    task.closed_at = None
    for annotation in task_annotations(db, task):
        annotation.status = "rejected"
        annotation.updated_by = access.user.id
    set_target_status(
        db,
        file_asset,
        upload_status=UPLOAD_SUPPLEMENT_REQUIRED,
        review_status=REVIEW_REJECTED,
    )
    add_review_record(
        db,
        access,
        file_asset,
        action="reject",
        review_status=REVIEW_REJECTED,
        comment=payload.comment,
    )
    record_operation(
        db,
        action="correction_task.return",
        request=request,
        access=access,
        target_type="correction_task",
        target_id=task.id,
        project_id=task.project_id,
        center_id=task.center_id,
        detail={"file_id": task.file_id, "comment": payload.comment},
    )
    db.commit()
    db.refresh(task)
    return task_to_read(db, task)
