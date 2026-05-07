from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.clinical_data import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    UPLOAD_SUPPLEMENT_REQUIRED,
    UPLOADED_STATUSES,
)
from app.core.database import get_db
from app.models import Center, FileAsset, Project, ReviewRecord, StageFile, Subject, SubjectItem
from app.schemas import (
    CenterCompletenessRead,
    CompletenessRecalculateRequest,
    CompletenessStatusCount,
    CompletenessSummaryRead,
    ReviewActionRequest,
    ReviewBatchApproveRead,
    ReviewBatchApproveRequest,
    ReviewBatchApproveResultItem,
    ReviewRecordRead,
    StageCompletenessRead,
)
from app.services.audit import record_operation
from app.services.clinical_status import (
    build_completeness_summary,
    recalculate_subject_status,
)

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
ReviewReadAccess = Annotated[AccessContext, Depends(require_permission("reviews:read"))]
ReviewSubmitAccess = Annotated[AccessContext, Depends(require_permission("reviews:submit"))]
ReviewApproveAccess = Annotated[AccessContext, Depends(require_permission("reviews:review"))]
CompletenessReadAccess = Annotated[
    AccessContext,
    Depends(require_permission("completeness:read")),
]
CompletenessRecalculateAccess = Annotated[
    AccessContext,
    Depends(require_permission("completeness:recalculate")),
]


def get_or_404(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return item


def ensure_project_access(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_center_access(access: AccessContext, center_id: int, project_id: int) -> None:
    if not access.can_access_center(center_id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")


def resolve_target(
    db: Session,
    access: AccessContext,
    target_type: str,
    target_id: int,
) -> tuple[StageFile | SubjectItem, Subject | None, int, int]:
    if target_type == "stage_file":
        stage_file = get_or_404(db, StageFile, target_id, "stage file")
        ensure_center_access(access, stage_file.center_id, stage_file.project_id)
        return stage_file, None, stage_file.project_id, stage_file.center_id
    if target_type == "subject_item":
        subject_item = get_or_404(db, SubjectItem, target_id, "subject item")
        subject = get_or_404(db, Subject, subject_item.subject_id, "subject")
        ensure_center_access(access, subject.center_id, subject.project_id)
        return subject_item, subject, subject.project_id, subject.center_id
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid target type")


def target_has_file(db: Session, target_type: str, target_id: int) -> bool:
    statement = select(FileAsset.id)
    if target_type == "stage_file":
        statement = statement.where(FileAsset.stage_file_id == target_id)
    else:
        statement = statement.where(FileAsset.subject_item_id == target_id)
    return db.scalar(statement.limit(1)) is not None


def create_review_record(
    db: Session,
    access: AccessContext,
    payload: ReviewActionRequest,
    action: str,
    review_status: str,
) -> ReviewRecord:
    record = ReviewRecord(
        target_type=payload.target_type,
        target_id=payload.target_id,
        action=action,
        review_status=review_status,
        reviewer_id=access.user.id,
        comment=payload.comment,
    )
    db.add(record)
    return record


def apply_target_recalculation(
    db: Session, target: StageFile | SubjectItem, subject: Subject | None
) -> None:
    if isinstance(target, SubjectItem) and subject is not None:
        recalculate_subject_status(db, subject)


def accessible_project_ids(access: AccessContext) -> set[int] | None:
    if access.is_admin:
        return None
    return access.project_ids


def accessible_center_ids(access: AccessContext) -> set[int] | None:
    if access.is_admin:
        return None
    return access.center_ids


def ensure_completeness_scope(
    db: Session,
    access: AccessContext,
    project_id: int | None,
    center_id: int | None,
    subject_id: int | None = None,
) -> None:
    if subject_id is not None:
        subject = get_or_404(db, Subject, subject_id, "subject")
        if project_id is not None and subject.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="subject does not belong to project",
            )
        if center_id is not None and subject.center_id != center_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="subject does not belong to center",
            )
        ensure_center_access(access, subject.center_id, subject.project_id)
        return
    if center_id is not None:
        center = get_or_404(db, Center, center_id, "center")
        if project_id is not None and center.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="center does not belong to project",
            )
        ensure_center_access(access, center.id, center.project_id)
        return
    if project_id is not None:
        get_or_404(db, Project, project_id, "project")
        ensure_project_access(access, project_id)


def review_record_scope_filter(access: AccessContext):
    if access.is_admin:
        return None

    stage_scope = []
    subject_scope = []
    if access.project_ids:
        stage_scope.append(StageFile.project_id.in_(access.project_ids))
        subject_scope.append(Subject.project_id.in_(access.project_ids))
    if access.center_ids:
        stage_scope.append(StageFile.center_id.in_(access.center_ids))
        subject_scope.append(Subject.center_id.in_(access.center_ids))
    if not stage_scope:
        return ReviewRecord.id == -1

    allowed_stage_file_ids = select(StageFile.id).where(or_(*stage_scope))
    allowed_subject_item_ids = (
        select(SubjectItem.id)
        .join(Subject, SubjectItem.subject_id == Subject.id)
        .where(or_(*subject_scope))
    )
    return or_(
        and_(
            ReviewRecord.target_type == "stage_file",
            ReviewRecord.target_id.in_(allowed_stage_file_ids),
        ),
        and_(
            ReviewRecord.target_type == "subject_item",
            ReviewRecord.target_id.in_(allowed_subject_item_ids),
        ),
    )


def recalculate_subjects_for_access(
    db: Session,
    access: AccessContext,
    project_id: int | None,
    center_id: int | None,
    subject_id: int | None,
) -> list[Subject]:
    statement = select(Subject).order_by(Subject.id)
    if not access.is_admin:
        scope_conditions = []
        if access.project_ids:
            scope_conditions.append(Subject.project_id.in_(access.project_ids))
        if access.center_ids:
            scope_conditions.append(Subject.center_id.in_(access.center_ids))
        if not scope_conditions:
            return []
        statement = statement.where(or_(*scope_conditions))
    if project_id is not None:
        statement = statement.where(Subject.project_id == project_id)
    if center_id is not None:
        statement = statement.where(Subject.center_id == center_id)
    if subject_id is not None:
        statement = statement.where(Subject.id == subject_id)
    subjects = list(db.scalars(statement))
    for subject in subjects:
        recalculate_subject_status(db, subject)
    return subjects


@router.post(
    "/reviews/submit", response_model=ReviewRecordRead, status_code=status.HTTP_201_CREATED
)
def submit_review(
    payload: ReviewActionRequest,
    db: DBSession,
    access: ReviewSubmitAccess,
    request: Request,
) -> ReviewRecord:
    target, subject, project_id, center_id = resolve_target(
        db, access, payload.target_type, payload.target_id
    )
    if target.review_status == REVIEW_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="target already approved"
        )
    if target.upload_status not in UPLOADED_STATUSES or not target_has_file(
        db,
        payload.target_type,
        payload.target_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target has no uploaded file to submit",
        )
    target.review_status = REVIEW_PENDING
    record = create_review_record(db, access, payload, "submit", REVIEW_PENDING)
    apply_target_recalculation(db, target, subject)
    record_operation(
        db,
        action="review.submit",
        request=request,
        access=access,
        target_type=payload.target_type,
        target_id=payload.target_id,
        project_id=project_id,
        center_id=center_id,
        detail={"comment": payload.comment},
    )
    db.commit()
    db.refresh(record)
    return record


@router.post(
    "/reviews/approve", response_model=ReviewRecordRead, status_code=status.HTTP_201_CREATED
)
def approve_review(
    payload: ReviewActionRequest,
    db: DBSession,
    access: ReviewApproveAccess,
    request: Request,
) -> ReviewRecord:
    target, subject, project_id, center_id = resolve_target(
        db, access, payload.target_type, payload.target_id
    )
    if target.review_status != REVIEW_PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target is not pending")
    target.review_status = REVIEW_APPROVED
    record = create_review_record(db, access, payload, "approve", REVIEW_APPROVED)
    apply_target_recalculation(db, target, subject)
    record_operation(
        db,
        action="review.approve",
        request=request,
        access=access,
        target_type=payload.target_type,
        target_id=payload.target_id,
        project_id=project_id,
        center_id=center_id,
        detail={"comment": payload.comment},
    )
    db.commit()
    db.refresh(record)
    return record


@router.post("/reviews/approve-batch", response_model=ReviewBatchApproveRead)
def approve_reviews_batch(
    payload: ReviewBatchApproveRequest,
    db: DBSession,
    access: ReviewApproveAccess,
    request: Request,
) -> ReviewBatchApproveRead:
    results: list[ReviewBatchApproveResultItem] = []
    approved_count = 0
    skipped_count = 0
    project_ids: set[int] = set()
    center_ids: set[int] = set()

    for target_payload in payload.targets:
        target, subject, project_id, center_id = resolve_target(
            db,
            access,
            target_payload.target_type,
            target_payload.target_id,
        )
        project_ids.add(project_id)
        center_ids.add(center_id)
        result = ReviewBatchApproveResultItem(
            target_type=target_payload.target_type,
            target_id=target_payload.target_id,
            status="skipped",
            message="",
        )
        action_payload = ReviewActionRequest(
            target_type=target_payload.target_type,
            target_id=target_payload.target_id,
        )

        if target.review_status == REVIEW_APPROVED:
            result.message = "已通过，跳过"
        elif target.upload_status not in UPLOADED_STATUSES:
            result.message = "未处于已上传或已替换状态，跳过"
        elif not target_has_file(db, target_payload.target_type, target_payload.target_id):
            result.message = "没有已上传文件，跳过"
        elif target.review_status == REVIEW_PENDING:
            target.review_status = REVIEW_APPROVED
            create_review_record(db, access, action_payload, "approve", REVIEW_APPROVED)
            apply_target_recalculation(db, target, subject)
            result.status = "approved"
            result.message = "已通过"
            result.approved = True
        else:
            target.review_status = REVIEW_PENDING
            create_review_record(db, access, action_payload, "submit", REVIEW_PENDING)
            target.review_status = REVIEW_APPROVED
            create_review_record(db, access, action_payload, "approve", REVIEW_APPROVED)
            apply_target_recalculation(db, target, subject)
            result.status = "approved"
            result.message = "已自动提交并通过"
            result.submitted = True
            result.approved = True

        if result.approved:
            approved_count += 1
        else:
            skipped_count += 1
        results.append(result)

    record_operation(
        db,
        action="review.approve_batch",
        request=request,
        access=access,
        target_type="review_batch",
        project_id=next(iter(project_ids)) if len(project_ids) == 1 else None,
        center_id=next(iter(center_ids)) if len(center_ids) == 1 else None,
        detail={
            "approved_count": approved_count,
            "skipped_count": skipped_count,
            "targets": [item.model_dump() for item in results],
        },
    )
    db.commit()
    return ReviewBatchApproveRead(
        approved_count=approved_count,
        skipped_count=skipped_count,
        results=results,
    )


@router.post(
    "/reviews/reject", response_model=ReviewRecordRead, status_code=status.HTTP_201_CREATED
)
def reject_review(
    payload: ReviewActionRequest,
    db: DBSession,
    access: ReviewApproveAccess,
    request: Request,
) -> ReviewRecord:
    if not payload.comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="reject reason required"
        )
    target, subject, project_id, center_id = resolve_target(
        db, access, payload.target_type, payload.target_id
    )
    if target.review_status != REVIEW_PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target is not pending")
    target.review_status = REVIEW_REJECTED
    target.upload_status = UPLOAD_SUPPLEMENT_REQUIRED
    record = create_review_record(db, access, payload, "reject", REVIEW_REJECTED)
    apply_target_recalculation(db, target, subject)
    record_operation(
        db,
        action="review.reject",
        request=request,
        access=access,
        target_type=payload.target_type,
        target_id=payload.target_id,
        project_id=project_id,
        center_id=center_id,
        detail={"comment": payload.comment},
    )
    db.commit()
    db.refresh(record)
    return record


@router.get("/reviews", response_model=list[ReviewRecordRead])
def list_reviews(
    db: DBSession,
    access: ReviewReadAccess,
    target_type: Annotated[str | None, Query()] = None,
    target_id: int | None = None,
) -> list[ReviewRecord]:
    if target_type is not None and target_type not in {"stage_file", "subject_item"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid target type")
    if target_type is not None and target_id is not None:
        resolve_target(db, access, target_type, target_id)
        statement = select(ReviewRecord).where(
            ReviewRecord.target_type == target_type,
            ReviewRecord.target_id == target_id,
        )
        return list(
            db.scalars(statement.order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc()))
        )

    statement = select(ReviewRecord)
    if target_type is not None:
        statement = statement.where(ReviewRecord.target_type == target_type)
    scope_filter = review_record_scope_filter(access)
    if scope_filter is not None:
        statement = statement.where(scope_filter)
    return list(
        db.scalars(statement.order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc()))
    )


@router.post("/completeness/recalculate", response_model=CompletenessSummaryRead)
def recalculate_completeness(
    payload: CompletenessRecalculateRequest,
    db: DBSession,
    access: CompletenessRecalculateAccess,
    request: Request,
) -> CompletenessSummaryRead:
    ensure_completeness_scope(db, access, payload.project_id, payload.center_id, payload.subject_id)
    recalculate_subjects_for_access(
        db,
        access,
        project_id=payload.project_id,
        center_id=payload.center_id,
        subject_id=payload.subject_id,
    )
    audit_project_id = payload.project_id
    audit_center_id = payload.center_id
    if payload.subject_id is not None:
        subject = db.get(Subject, payload.subject_id)
        if subject is not None:
            audit_project_id = subject.project_id
            audit_center_id = subject.center_id
    record_operation(
        db,
        action="completeness.recalculate",
        request=request,
        access=access,
        target_type="completeness",
        target_id=payload.subject_id,
        project_id=audit_project_id,
        center_id=audit_center_id,
        detail=payload.model_dump(exclude_none=True),
    )
    db.commit()
    return completeness_summary(db, access, payload.project_id, payload.center_id)


@router.get("/completeness/summary", response_model=CompletenessSummaryRead)
def completeness_summary(
    db: DBSession,
    access: CompletenessReadAccess,
    project_id: int | None = None,
    center_id: int | None = None,
) -> CompletenessSummaryRead:
    ensure_completeness_scope(db, access, project_id, center_id)
    summary = build_completeness_summary(
        db,
        project_ids=accessible_project_ids(access),
        center_ids=accessible_center_ids(access),
        project_id=project_id,
        center_id=center_id,
    )
    return CompletenessSummaryRead(
        project_id=project_id,
        center_id=center_id,
        status=summary.status,
        stage_files=counter_to_read(summary.stage_files),
        subjects=counter_to_read(summary.subjects),
        centers=[
            CenterCompletenessRead(
                center_id=row["center_id"],
                center_name=row["center_name"],
                status=row["status"],
                stage_files=counter_to_read(row["stage_files"]),
                subjects=counter_to_read(row["subjects"]),
            )
            for row in summary.centers
        ],
        stages=[
            StageCompletenessRead(
                stage_id=row.stage_id,
                stage_name=row.stage_name,
                status=row.status,
                required_count=row.required_count,
                complete_count=row.complete_count,
                checking_count=row.checking_count,
                incomplete_count=row.incomplete_count,
            )
            for row in summary.stages
        ],
    )


def counter_to_read(counter) -> CompletenessStatusCount:
    return CompletenessStatusCount(
        complete=counter["complete"],
        checking=counter["checking"],
        incomplete=counter["incomplete"],
    )
