from collections import Counter
from datetime import date, timedelta
from statistics import median
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.clinical_data import DATA_COMPLETE
from app.core.database import get_db
from app.models import Center, Project, Subject, SubjectItem
from app.schemas import (
    CenterCompletenessRead,
    CompletenessStatusCount,
    CompletenessSummaryRead,
    DashboardCenterRead,
    DashboardProjectSummaryRead,
    DashboardReviewStatusRead,
    DashboardTrendPointRead,
    StageCompletenessRead,
)
from app.services.clinical_status import (
    build_completeness_summary,
    build_stage_file_statuses,
)

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
DashboardReadAccess = Annotated[AccessContext, Depends(require_permission("dashboard:read"))]


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


def ensure_project_access(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def visible_centers(db: Session, access: AccessContext, project_id: int) -> list[Center]:
    statement = select(Center).where(Center.project_id == project_id).order_by(Center.id)
    if not access.is_admin and project_id not in access.project_ids:
        statement = statement.where(Center.id.in_(access.center_ids))
    return list(db.scalars(statement))


def visible_center_ids(db: Session, access: AccessContext, project_id: int) -> list[int]:
    return [center.id for center in visible_centers(db, access, project_id)]


def scoped_subjects(
    db: Session,
    project_id: int,
    center_ids: list[int],
) -> list[Subject]:
    if not center_ids:
        return []
    return list(
        db.scalars(
            select(Subject)
            .where(Subject.project_id == project_id, Subject.center_id.in_(center_ids))
            .order_by(Subject.center_id, Subject.id)
        )
    )


def scoped_subject_item_statuses(
    db: Session,
    project_id: int,
    center_ids: list[int],
) -> list[tuple[int, str]]:
    if not center_ids:
        return []
    return list(
        db.execute(
            select(Subject.center_id, SubjectItem.review_status)
            .join(SubjectItem, SubjectItem.subject_id == Subject.id)
            .where(
                Subject.project_id == project_id,
                Subject.center_id.in_(center_ids),
                SubjectItem.required.is_(True),
            )
        )
    )


def status_counter_to_read(counter: Counter[str]) -> CompletenessStatusCount:
    return CompletenessStatusCount(
        complete=counter["complete"],
        checking=counter["checking"],
        incomplete=counter["incomplete"],
    )


def subject_start_date(subject: Subject) -> date:
    return subject.enrolled_at or subject.created_at.date()


def subject_completion_date(subject: Subject) -> date | None:
    return subject.completed_at.date() if subject.completed_at else None


def subject_duration_days(subject: Subject) -> int | None:
    completion_date = subject_completion_date(subject)
    if completion_date is None:
        return None
    return max((completion_date - subject_start_date(subject)).days, 0)


def project_days(project: Project) -> int:
    return max((date.today() - project.created_at.date()).days + 1, 1)


def period_start(value: date, granularity: str) -> date:
    if granularity == "month":
        return value.replace(day=1)
    return value - timedelta(days=value.weekday())


def next_period(value: date, granularity: str) -> date:
    if granularity == "month":
        if value.month == 12:
            return value.replace(year=value.year + 1, month=1, day=1)
        return value.replace(month=value.month + 1, day=1)
    return value + timedelta(days=7)


def period_label(value: date, granularity: str) -> str:
    if granularity == "month":
        return value.strftime("%Y-%m")
    return value.isoformat()


def review_status_counts(
    db: Session,
    project_id: int,
    center_ids: list[int],
) -> tuple[Counter[str], Counter[tuple[int, str]]]:
    stage_counts: Counter[str] = Counter()
    center_pending_rejected: Counter[int] = Counter()
    for stage_status in build_stage_file_statuses(
        db,
        project_id=project_id,
        center_ids=set(center_ids),
    ):
        stage_counts[stage_status.review_status] += 1
        if stage_status.review_status == "pending":
            center_pending_rejected[(stage_status.center_id, "pending")] += 1
        if stage_status.review_status == "rejected":
            center_pending_rejected[(stage_status.center_id, "rejected")] += 1

    subject_counts: Counter[str] = Counter()
    for center_id, review_status in scoped_subject_item_statuses(db, project_id, center_ids):
        subject_counts[review_status] += 1
        if review_status == "pending":
            center_pending_rejected[(center_id, "pending")] += 1
        if review_status == "rejected":
            center_pending_rejected[(center_id, "rejected")] += 1

    return stage_counts + subject_counts, center_pending_rejected


def scoped_project_ids(access: AccessContext) -> set[int] | None:
    if access.is_admin:
        return None
    return access.project_ids


def scoped_center_ids(access: AccessContext) -> set[int] | None:
    if access.is_admin:
        return None
    return access.center_ids


@router.get("/dashboard/project/{project_id}", response_model=DashboardProjectSummaryRead)
def dashboard_project_summary(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
) -> DashboardProjectSummaryRead:
    project = get_project_or_404(db, project_id)
    ensure_project_access(access, project_id)
    center_ids = visible_center_ids(db, access, project_id)
    subjects = scoped_subjects(db, project_id, center_ids)
    completed_subjects = [
        subject for subject in subjects if subject.data_status == DATA_COMPLETE
    ]
    durations = [
        duration
        for subject in completed_subjects
        if (duration := subject_duration_days(subject)) is not None
    ]
    return DashboardProjectSummaryRead(
        project_id=project.id,
        project_name=project.name,
        completed_subject_count=len(completed_subjects),
        visible_center_count=len(center_ids),
        project_days=project_days(project),
        average_days_per_subject=round(sum(durations) / len(durations), 1)
        if durations
        else 0.0,
        median_days_per_subject=round(float(median(durations)), 1) if durations else 0.0,
        subject_count=len(subjects),
    )


@router.get("/dashboard/project/{project_id}/centers", response_model=list[DashboardCenterRead])
def dashboard_project_centers(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
) -> list[DashboardCenterRead]:
    get_project_or_404(db, project_id)
    ensure_project_access(access, project_id)
    centers = visible_centers(db, access, project_id)
    center_ids = [center.id for center in centers]
    subjects = scoped_subjects(db, project_id, center_ids)
    summary = build_completeness_summary(
        db,
        project_ids=scoped_project_ids(access),
        center_ids=scoped_center_ids(access),
        project_id=project_id,
    )
    center_status_by_id = {
        row["center_id"]: row["status"]
        for row in summary.centers
    }
    _, pending_rejected = review_status_counts(db, project_id, center_ids)
    rows = []
    for center in centers:
        center_subjects = [subject for subject in subjects if subject.center_id == center.id]
        completed_count = sum(
            1 for subject in center_subjects if subject.data_status == DATA_COMPLETE
        )
        rows.append(
            DashboardCenterRead(
                center_id=center.id,
                center_name=center.name,
                subject_count=len(center_subjects),
                completed_subject_count=completed_count,
                completion_rate=round(completed_count / len(center_subjects) * 100, 1)
                if center_subjects
                else 0.0,
                completeness_status=center_status_by_id.get(center.id, "incomplete"),
                pending_review_count=pending_rejected[(center.id, "pending")],
                rejected_review_count=pending_rejected[(center.id, "rejected")],
            )
        )
    return rows


@router.get("/dashboard/project/{project_id}/trend", response_model=list[DashboardTrendPointRead])
def dashboard_project_trend(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
    granularity: Annotated[str, Query(pattern="^(week|month)$")] = "week",
) -> list[DashboardTrendPointRead]:
    get_project_or_404(db, project_id)
    ensure_project_access(access, project_id)
    center_ids = visible_center_ids(db, access, project_id)
    completed_dates = []
    for subject in scoped_subjects(db, project_id, center_ids):
        if subject.data_status != DATA_COMPLETE:
            continue
        completion_date = subject_completion_date(subject)
        if completion_date is not None:
            completed_dates.append(completion_date)
    if not completed_dates:
        return []

    counts: Counter[date] = Counter(period_start(value, granularity) for value in completed_dates)
    cursor = period_start(min(completed_dates), granularity)
    end = period_start(date.today(), granularity)
    rows = []
    while cursor <= end:
        rows.append(
            DashboardTrendPointRead(
                period=period_label(cursor, granularity),
                completed_count=counts[cursor],
            )
        )
        cursor = next_period(cursor, granularity)
    return rows


@router.get(
    "/dashboard/project/{project_id}/review-status",
    response_model=DashboardReviewStatusRead,
)
def dashboard_project_review_status(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
) -> DashboardReviewStatusRead:
    get_project_or_404(db, project_id)
    ensure_project_access(access, project_id)
    center_ids = visible_center_ids(db, access, project_id)
    counts, _ = review_status_counts(db, project_id, center_ids)
    return DashboardReviewStatusRead(
        unreviewed=counts["unreviewed"],
        pending=counts["pending"],
        approved=counts["approved"],
        rejected=counts["rejected"],
    )


@router.get("/dashboard/project/{project_id}/completeness", response_model=CompletenessSummaryRead)
def dashboard_project_completeness(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
) -> CompletenessSummaryRead:
    get_project_or_404(db, project_id)
    ensure_project_access(access, project_id)
    summary = build_completeness_summary(
        db,
        project_ids=scoped_project_ids(access),
        center_ids=scoped_center_ids(access),
        project_id=project_id,
    )
    return CompletenessSummaryRead(
        project_id=project_id,
        center_id=None,
        status=summary.status,
        stage_files=status_counter_to_read(summary.stage_files),
        subjects=status_counter_to_read(summary.subjects),
        centers=[
            CenterCompletenessRead(
                center_id=row["center_id"],
                center_name=row["center_name"],
                status=row["status"],
                stage_files=status_counter_to_read(row["stage_files"]),
                subjects=status_counter_to_read(row["subjects"]),
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
