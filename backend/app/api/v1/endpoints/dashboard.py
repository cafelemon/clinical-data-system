from collections import Counter
from datetime import date, timedelta
from statistics import median
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
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
from app.schemas.dashboard import (
    DashboardClinicalEventCreate,
    DashboardClinicalEventRead,
    DashboardClinicalEventUpdate,
    DashboardDeviceHandoverCreate,
    DashboardDeviceHandoverRead,
    DashboardDeviceHandoverUpdate,
    DashboardDeviceIssueCreate,
    DashboardDeviceIssueRead,
    DashboardDeviceIssueUpdate,
    DashboardEnrollmentPlanCreate,
    DashboardEnrollmentPlanRead,
    DashboardEnrollmentPlanUpdate,
    DashboardImportantTaskCreate,
    DashboardImportantTaskRead,
    DashboardImportantTaskUpdate,
    DashboardMilestoneCreate,
    DashboardMilestoneRead,
    DashboardMilestoneUpdate,
    DashboardSubjectOverviewCreate,
    DashboardSubjectOverviewRead,
    DashboardSubjectOverviewUpdate,
    DashboardSubjectResultCreate,
    DashboardSubjectResultRead,
    DashboardSubjectResultUpdate,
    DashboardV31ImportResultRead,
    DashboardV31OverviewRead,
    DashboardV323CenterRead,
    DashboardV323EnrollmentRead,
    DashboardV323KpisRead,
    DashboardV323ManualSupplementsRead,
    DashboardV323OverviewRead,
    DashboardV323ScopeRead,
    DashboardV323TrendRead,
    DashboardV323WarningRead,
)
from app.services.clinical_status import (
    build_completeness_summary,
    build_stage_file_statuses,
)
from app.services.dashboard_v31 import (
    DASHBOARD_V31_CONFIGS,
    XLSX_MEDIA_TYPE,
    build_overview,
    build_template_workbook,
    build_warnings,
    create_record,
    delete_record,
    export_records_workbook,
    import_records_workbook,
    list_records,
    update_record,
)

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
DashboardReadAccess = Annotated[AccessContext, Depends(require_permission("dashboard:read"))]
DashboardWriteAccess = Annotated[AccessContext, Depends(require_permission("dashboard:write"))]
DashboardUploadFile = Annotated[UploadFile, File(...)]


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


def visible_projects(db: Session, access: AccessContext) -> list[Project]:
    statement = select(Project).order_by(Project.id)
    if access.is_admin:
        return list(db.scalars(statement))
    project_ids = access.project_ids | access.center_project_ids
    if not project_ids:
        return []
    return list(db.scalars(statement.where(Project.id.in_(project_ids))))


def resolve_v323_scope(
    db: Session,
    access: AccessContext,
    project_id: int | None,
    center_id: int | None,
) -> tuple[list[Project], list[Center], DashboardV323ScopeRead]:
    if center_id is not None:
        center = db.get(Center, center_id)
        if center is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="center not found")
        if project_id is not None and center.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="center does not belong to project"
            )
        ensure_project_access(access, center.project_id)
        if not access.can_access_center(center.id, center.project_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")
        project = get_project_or_404(db, center.project_id)
        return [
            project
        ], [
            center
        ], DashboardV323ScopeRead(
            level="center",
            project_id=project.id,
            project_name=project.name,
            center_id=center.id,
            center_name=center.name,
        )
    if project_id is not None:
        project = get_project_or_404(db, project_id)
        ensure_project_access(access, project_id)
        centers = visible_centers(db, access, project_id)
        return [
            project
        ], centers, DashboardV323ScopeRead(
            level="project",
            project_id=project.id,
            project_name=project.name,
        )
    projects = visible_projects(db, access)
    centers = [
        center for project in projects for center in visible_centers(db, access, project.id)
    ]
    return projects, centers, DashboardV323ScopeRead(level="all")


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


def completion_rate(completed_count: int, total_count: int) -> float:
    return round(completed_count / total_count * 100, 1) if total_count else 0.0


def combined_completeness_count(
    stage_files: CompletenessStatusCount, subjects: CompletenessStatusCount
) -> CompletenessStatusCount:
    return CompletenessStatusCount(
        complete=stage_files.complete + subjects.complete,
        checking=stage_files.checking + subjects.checking,
        incomplete=stage_files.incomplete + subjects.incomplete,
    )


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
    completed_subjects = [subject for subject in subjects if subject.data_status == DATA_COMPLETE]
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
        average_days_per_subject=round(sum(durations) / len(durations), 1) if durations else 0.0,
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
    center_status_by_id = {row["center_id"]: row["status"] for row in summary.centers}
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
                completion_rate=(
                    round(completed_count / len(center_subjects) * 100, 1)
                    if center_subjects
                    else 0.0
                ),
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


@router.get("/dashboard/v323/overview", response_model=DashboardV323OverviewRead)
def dashboard_v323_overview(
    db: DBSession,
    access: DashboardReadAccess,
    project_id: int | None = None,
    center_id: int | None = None,
) -> DashboardV323OverviewRead:
    projects, centers, scope = resolve_v323_scope(db, access, project_id, center_id)
    project_by_id = {project.id: project for project in projects}
    center_by_id = {center.id: center for center in centers}
    selected_project_ids = set(project_by_id)
    selected_center_ids = set(center_by_id)

    summary_project_ids = None if access.is_admin else selected_project_ids & access.project_ids
    summary_center_ids = (
        selected_center_ids
        if center_id is not None or not access.is_admin or project_id is None
        else None
    )
    summary = build_completeness_summary(
        db,
        project_ids=summary_project_ids,
        center_ids=summary_center_ids,
        project_id=project_id,
        center_id=center_id,
    )
    stage_file_counts = status_counter_to_read(summary.stage_files)
    subject_counts = status_counter_to_read(summary.subjects)
    completeness = combined_completeness_count(stage_file_counts, subject_counts)

    all_subjects: list[Subject] = []
    review_counts: Counter[str] = Counter()
    pending_rejected: Counter[tuple[int, str]] = Counter()
    for project in projects:
        project_center_ids = [
            center.id for center in centers if center.project_id == project.id
        ]
        all_subjects.extend(scoped_subjects(db, project.id, project_center_ids))
        counts, center_counts = review_status_counts(db, project.id, project_center_ids)
        review_counts.update(counts)
        pending_rejected.update(center_counts)

    completed_subjects = [
        subject for subject in all_subjects if subject.data_status == DATA_COMPLETE
    ]
    center_status_by_id = {row["center_id"]: row["status"] for row in summary.centers}
    center_rows = []
    for center in centers:
        center_subjects = [subject for subject in all_subjects if subject.center_id == center.id]
        center_completed = [
            subject for subject in center_subjects if subject.data_status == DATA_COMPLETE
        ]
        project = project_by_id[center.project_id]
        center_rows.append(
            DashboardV323CenterRead(
                project_id=project.id,
                project_name=project.name,
                center_id=center.id,
                center_name=center.name,
                subject_count=len(center_subjects),
                completed_subject_count=len(center_completed),
                completion_rate=completion_rate(len(center_completed), len(center_subjects)),
                completeness_status=center_status_by_id.get(center.id, "incomplete"),
                pending_review_count=pending_rejected[(center.id, "pending")],
                rejected_review_count=pending_rejected[(center.id, "rejected")],
            )
        )

    manual_counts: Counter[str] = Counter()
    task_status: Counter[str] = Counter()
    contract_count = 0
    planned_next_week = 0
    maintained_current_enrolled = 0
    warnings: list[DashboardV323WarningRead] = []
    for project in projects:
        scoped_center_id = (
            center_id if center_id is not None and project.id == scope.project_id else None
        )
        for kind in DASHBOARD_V31_CONFIGS:
            records = list_records(db, access, kind, project.id, scoped_center_id)
            manual_counts[kind] += len(records)
            if kind == "enrollment-plans":
                contract_count += sum(row.contract_count or 0 for row in records)
                planned_next_week += sum(row.next_week_plan_count or 0 for row in records)
                maintained_current_enrolled += sum(
                    row.current_enrolled_count or 0 for row in records
                )
            if kind == "important-tasks":
                task_status.update(row.status for row in records)
        for warning in build_warnings(db, access, project.id):
            if center_id is not None and warning["center_id"] != center_id:
                continue
            warning_center = center_by_id.get(warning["center_id"] or 0)
            warnings.append(
                DashboardV323WarningRead(
                    source=warning["source"],
                    project_id=project.id,
                    project_name=project.name,
                    id=warning["id"],
                    title=warning["title"],
                    center_id=warning["center_id"],
                    center_name=warning_center.name if warning_center else None,
                    planned_date=warning["planned_date"],
                    status=warning["status"],
                    warning_level=warning["warning_level"],
                )
            )

    trend_counts: Counter[date] = Counter()
    for subject in completed_subjects:
        if subject.completed_at is not None:
            trend_counts[period_start(subject.completed_at.date(), "week")] += 1
    trends = [
        DashboardV323TrendRead(period=period_label(period, "week"), completed_count=count)
        for period, count in sorted(trend_counts.items())
    ]

    return DashboardV323OverviewRead(
        scope=scope,
        kpis=DashboardV323KpisRead(
            project_count=len(projects),
            center_count=len(centers),
            subject_count=len(all_subjects),
            completed_subject_count=len(completed_subjects),
            completion_rate=completion_rate(len(completed_subjects), len(all_subjects)),
            active_warning_count=len(warnings),
            pending_review_count=review_counts["pending"],
            rejected_review_count=review_counts["rejected"],
        ),
        completeness=completeness,
        stage_files=stage_file_counts,
        subjects=subject_counts,
        reviews=DashboardReviewStatusRead(
            unreviewed=review_counts["unreviewed"],
            pending=review_counts["pending"],
            approved=review_counts["approved"],
            rejected=review_counts["rejected"],
        ),
        enrollment=DashboardV323EnrollmentRead(
            subject_count=len(all_subjects),
            completed_subject_count=len(completed_subjects),
            contract_count=contract_count,
            planned_next_week=planned_next_week,
            maintained_current_enrolled=maintained_current_enrolled,
        ),
        centers=sorted(
            center_rows,
            key=lambda row: (row.completeness_status != "incomplete", row.completion_rate),
        ),
        trends=trends,
        warnings=sorted(warnings, key=lambda row: (row.planned_date, row.source, row.id)),
        manual_supplements=DashboardV323ManualSupplementsRead(
            counts=dict(manual_counts),
            important_task_status=dict(task_status),
            clinical_event_count=manual_counts["clinical-events"],
            device_issue_count=manual_counts["device-issues"],
        ),
    )


@router.get("/dashboard/v31/project/{project_id}/overview", response_model=DashboardV31OverviewRead)
def dashboard_v31_overview(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
) -> dict:
    return build_overview(db, access, project_id)


@router.get("/dashboard/v31/milestones", response_model=list[DashboardMilestoneRead])
def list_dashboard_milestones(
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
    center_id: int | None = None,
) -> list:
    return list_records(db, access, "milestones", project_id, center_id)


@router.post(
    "/dashboard/v31/milestones",
    response_model=DashboardMilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_milestone(
    payload: DashboardMilestoneCreate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return create_record(db, access, "milestones", payload.model_dump())


@router.patch("/dashboard/v31/milestones/{record_id}", response_model=DashboardMilestoneRead)
def update_dashboard_milestone(
    record_id: int,
    payload: DashboardMilestoneUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "milestones", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/dashboard/v31/milestones/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard_milestone(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "milestones", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/enrollment-plans", response_model=list[DashboardEnrollmentPlanRead])
def list_dashboard_enrollment_plans(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "enrollment-plans", project_id, center_id)


@router.post(
    "/dashboard/v31/enrollment-plans",
    response_model=DashboardEnrollmentPlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_enrollment_plan(
    payload: DashboardEnrollmentPlanCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "enrollment-plans", payload.model_dump())


@router.patch(
    "/dashboard/v31/enrollment-plans/{record_id}", response_model=DashboardEnrollmentPlanRead
)
def update_dashboard_enrollment_plan(
    record_id: int,
    payload: DashboardEnrollmentPlanUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "enrollment-plans", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete(
    "/dashboard/v31/enrollment-plans/{record_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_dashboard_enrollment_plan(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "enrollment-plans", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/subject-overviews", response_model=list[DashboardSubjectOverviewRead])
def list_dashboard_subject_overviews(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "subject-overviews", project_id, center_id)


@router.post(
    "/dashboard/v31/subject-overviews",
    response_model=DashboardSubjectOverviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_subject_overview(
    payload: DashboardSubjectOverviewCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "subject-overviews", payload.model_dump())


@router.patch(
    "/dashboard/v31/subject-overviews/{record_id}", response_model=DashboardSubjectOverviewRead
)
def update_dashboard_subject_overview(
    record_id: int,
    payload: DashboardSubjectOverviewUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "subject-overviews", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete(
    "/dashboard/v31/subject-overviews/{record_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_dashboard_subject_overview(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "subject-overviews", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/device-handovers", response_model=list[DashboardDeviceHandoverRead])
def list_dashboard_device_handovers(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "device-handovers", project_id, center_id)


@router.post(
    "/dashboard/v31/device-handovers",
    response_model=DashboardDeviceHandoverRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_device_handover(
    payload: DashboardDeviceHandoverCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "device-handovers", payload.model_dump())


@router.patch(
    "/dashboard/v31/device-handovers/{record_id}", response_model=DashboardDeviceHandoverRead
)
def update_dashboard_device_handover(
    record_id: int,
    payload: DashboardDeviceHandoverUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "device-handovers", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete(
    "/dashboard/v31/device-handovers/{record_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_dashboard_device_handover(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "device-handovers", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/subject-results", response_model=list[DashboardSubjectResultRead])
def list_dashboard_subject_results(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "subject-results", project_id, center_id)


@router.post(
    "/dashboard/v31/subject-results",
    response_model=DashboardSubjectResultRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_subject_result(
    payload: DashboardSubjectResultCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "subject-results", payload.model_dump())


@router.patch(
    "/dashboard/v31/subject-results/{record_id}", response_model=DashboardSubjectResultRead
)
def update_dashboard_subject_result(
    record_id: int,
    payload: DashboardSubjectResultUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "subject-results", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/dashboard/v31/subject-results/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard_subject_result(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "subject-results", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/clinical-events", response_model=list[DashboardClinicalEventRead])
def list_dashboard_clinical_events(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "clinical-events", project_id, center_id)


@router.post(
    "/dashboard/v31/clinical-events",
    response_model=DashboardClinicalEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_clinical_event(
    payload: DashboardClinicalEventCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "clinical-events", payload.model_dump())


@router.patch(
    "/dashboard/v31/clinical-events/{record_id}", response_model=DashboardClinicalEventRead
)
def update_dashboard_clinical_event(
    record_id: int,
    payload: DashboardClinicalEventUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "clinical-events", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/dashboard/v31/clinical-events/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard_clinical_event(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "clinical-events", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/device-issues", response_model=list[DashboardDeviceIssueRead])
def list_dashboard_device_issues(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "device-issues", project_id, center_id)


@router.post(
    "/dashboard/v31/device-issues",
    response_model=DashboardDeviceIssueRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_device_issue(
    payload: DashboardDeviceIssueCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "device-issues", payload.model_dump())


@router.patch("/dashboard/v31/device-issues/{record_id}", response_model=DashboardDeviceIssueRead)
def update_dashboard_device_issue(
    record_id: int, payload: DashboardDeviceIssueUpdate, db: DBSession, access: DashboardWriteAccess
):
    return update_record(
        db, access, "device-issues", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/dashboard/v31/device-issues/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard_device_issue(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "device-issues", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/important-tasks", response_model=list[DashboardImportantTaskRead])
def list_dashboard_important_tasks(
    project_id: int, db: DBSession, access: DashboardReadAccess, center_id: int | None = None
) -> list:
    return list_records(db, access, "important-tasks", project_id, center_id)


@router.post(
    "/dashboard/v31/important-tasks",
    response_model=DashboardImportantTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_dashboard_important_task(
    payload: DashboardImportantTaskCreate, db: DBSession, access: DashboardWriteAccess
):
    return create_record(db, access, "important-tasks", payload.model_dump())


@router.patch(
    "/dashboard/v31/important-tasks/{record_id}", response_model=DashboardImportantTaskRead
)
def update_dashboard_important_task(
    record_id: int,
    payload: DashboardImportantTaskUpdate,
    db: DBSession,
    access: DashboardWriteAccess,
):
    return update_record(
        db, access, "important-tasks", record_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/dashboard/v31/important-tasks/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard_important_task(
    record_id: int, db: DBSession, access: DashboardWriteAccess
) -> Response:
    delete_record(db, access, "important-tasks", record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/v31/import-template/{kind}")
def dashboard_v31_import_template(kind: str, access: DashboardReadAccess) -> Response:
    content = build_template_workbook(kind)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="dashboard-v31-{kind}-template.xlsx"'
        },
    )


@router.post("/dashboard/v31/import/{kind}", response_model=DashboardV31ImportResultRead)
async def dashboard_v31_import(
    kind: str,
    project_id: int,
    db: DBSession,
    access: DashboardWriteAccess,
    file: DashboardUploadFile,
) -> DashboardV31ImportResultRead:
    return import_records_workbook(db, access, kind, project_id, await file.read())


@router.get("/dashboard/v31/export/{kind}")
def dashboard_v31_export(
    kind: str,
    project_id: int,
    db: DBSession,
    access: DashboardReadAccess,
    center_id: int | None = None,
) -> Response:
    content = export_records_workbook(db, access, kind, project_id, center_id)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="dashboard-v31-{kind}.xlsx"'},
    )
