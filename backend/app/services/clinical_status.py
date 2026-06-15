from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.clinical_data import (
    CHECKING_REVIEW_STATUSES,
    DATA_CHECKING,
    DATA_COMPLETE,
    DATA_INCOMPLETE,
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    UPLOAD_SUPPLEMENT_REQUIRED,
    UPLOADED_STATUSES,
)
from app.models import Center, Stage, StageFile, StageTemplate, Subject, SubjectItem
from app.services.stage_config import CENTER_FILE_SCOPE


@dataclass(frozen=True)
class StageCompleteness:
    stage_id: int
    stage_name: str
    status: str
    required_count: int
    complete_count: int
    checking_count: int
    incomplete_count: int


@dataclass(frozen=True)
class CompletenessSummary:
    status: str
    stage_files: Counter[str]
    subjects: Counter[str]
    centers: list[dict]
    stages: list[StageCompleteness]


@dataclass(frozen=True)
class StageFileStatus:
    project_id: int
    center_id: int
    stage_id: int
    upload_status: str
    review_status: str
    required: bool
    not_applicable: bool = False


def required_item_status(
    upload_status: str,
    review_status: str,
    required: bool = True,
) -> str:
    if not required:
        return DATA_COMPLETE
    if upload_status == UPLOAD_SUPPLEMENT_REQUIRED or review_status == REVIEW_REJECTED:
        return DATA_INCOMPLETE
    if upload_status not in UPLOADED_STATUSES:
        return DATA_INCOMPLETE
    if review_status == REVIEW_APPROVED:
        return DATA_COMPLETE
    if review_status in CHECKING_REVIEW_STATUSES:
        return DATA_CHECKING
    return DATA_INCOMPLETE


def stage_file_item_status(
    upload_status: str,
    review_status: str,
    required: bool = True,
    not_applicable: bool = False,
) -> str:
    if not required and not_applicable:
        return DATA_COMPLETE
    if upload_status == UPLOAD_SUPPLEMENT_REQUIRED or review_status == REVIEW_REJECTED:
        return DATA_INCOMPLETE
    if upload_status not in UPLOADED_STATUSES:
        return DATA_INCOMPLETE
    if review_status == REVIEW_APPROVED:
        return DATA_COMPLETE
    if review_status in CHECKING_REVIEW_STATUSES:
        return DATA_CHECKING
    return DATA_INCOMPLETE


def aggregate_status(statuses: list[str]) -> str:
    if not statuses:
        return DATA_INCOMPLETE
    if all(status == DATA_COMPLETE for status in statuses):
        return DATA_COMPLETE
    if any(status == DATA_CHECKING for status in statuses):
        return DATA_CHECKING
    return DATA_INCOMPLETE


def aggregate_required_item_statuses(statuses: list[str]) -> str:
    if not statuses:
        return DATA_INCOMPLETE
    if any(status == DATA_INCOMPLETE for status in statuses):
        return DATA_INCOMPLETE
    if any(status == DATA_CHECKING for status in statuses):
        return DATA_CHECKING
    return DATA_COMPLETE


def recalculate_subject_status(db: Session, subject: Subject) -> str:
    items = list(
        db.scalars(
            select(SubjectItem)
            .where(SubjectItem.subject_id == subject.id, SubjectItem.required.is_(True))
            .order_by(SubjectItem.id)
        )
    )
    statuses = [
        required_item_status(item.upload_status, item.review_status, item.required)
        for item in items
    ]
    subject.data_status = aggregate_required_item_statuses(statuses)
    if subject.data_status == DATA_COMPLETE and subject.completed_at is None:
        subject.completed_at = datetime.now(UTC)
    if subject.data_status == DATA_COMPLETE:
        subject.review_status = REVIEW_APPROVED
    elif any(item.review_status == REVIEW_REJECTED for item in items):
        subject.review_status = REVIEW_REJECTED
    elif any(item.review_status in CHECKING_REVIEW_STATUSES for item in items):
        subject.review_status = DEFAULT_REVIEW_STATUS
    else:
        subject.review_status = DEFAULT_REVIEW_STATUS
    return subject.data_status


def reset_stage_file_status(stage_file: StageFile) -> None:
    stage_file.upload_status = DEFAULT_UPLOAD_STATUS
    stage_file.review_status = DEFAULT_REVIEW_STATUS


def recalculate_all_subjects(
    db: Session,
    project_id: int | None = None,
    center_id: int | None = None,
    subject_id: int | None = None,
) -> list[Subject]:
    statement = select(Subject).order_by(Subject.id)
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


def stage_file_required(stage_file: StageFile) -> bool:
    return True if stage_file.stage_template is None else bool(stage_file.stage_template.required)


def build_completeness_summary(
    db: Session,
    project_ids: set[int] | None = None,
    center_ids: set[int] | None = None,
    project_id: int | None = None,
    center_id: int | None = None,
) -> CompletenessSummary:
    subject_statement = select(Subject).order_by(Subject.project_id, Subject.center_id)
    if project_ids is not None or center_ids is not None:
        subject_scope = []
        if project_ids:
            subject_scope.append(Subject.project_id.in_(project_ids))
        if center_ids:
            subject_scope.append(Subject.center_id.in_(center_ids))
        if not subject_scope:
            return CompletenessSummary(DATA_INCOMPLETE, Counter(), Counter(), [], [])
        subject_statement = subject_statement.where(or_(*subject_scope))
    if project_id is not None:
        subject_statement = subject_statement.where(Subject.project_id == project_id)
    if center_id is not None:
        subject_statement = subject_statement.where(Subject.center_id == center_id)

    stage_file_statuses = build_stage_file_statuses(
        db,
        project_ids=project_ids,
        center_ids=center_ids,
        project_id=project_id,
        center_id=center_id,
    )
    subjects = list(db.scalars(subject_statement))
    stage_item_statuses = [
        stage_file_item_status(
            status.upload_status,
            status.review_status,
            status.required,
            status.not_applicable,
        )
        for status in stage_file_statuses
    ]
    subject_statuses = [subject.data_status for subject in subjects]
    center_rows = _build_center_rows(db, stage_file_statuses, subjects)
    stage_rows = _build_stage_rows(db, stage_file_statuses)
    return CompletenessSummary(
        status=aggregate_status(stage_item_statuses + subject_statuses),
        stage_files=Counter(stage_item_statuses),
        subjects=Counter(subject_statuses),
        centers=center_rows,
        stages=stage_rows,
    )


def build_stage_file_statuses(
    db: Session,
    project_ids: set[int] | None = None,
    center_ids: set[int] | None = None,
    project_id: int | None = None,
    center_id: int | None = None,
) -> list[StageFileStatus]:
    center_statement = select(Center).order_by(Center.project_id, Center.id)
    if project_ids is not None or center_ids is not None:
        center_scope = []
        if project_ids:
            center_scope.append(Center.project_id.in_(project_ids))
        if center_ids:
            center_scope.append(Center.id.in_(center_ids))
        if not center_scope:
            return []
        center_statement = center_statement.where(or_(*center_scope))
    if project_id is not None:
        center_statement = center_statement.where(Center.project_id == project_id)
    if center_id is not None:
        center_statement = center_statement.where(Center.id == center_id)
    centers = list(db.scalars(center_statement))
    if not centers:
        return []

    visible_project_ids = {center.project_id for center in centers}
    visible_center_ids = {center.id for center in centers}
    templates = list(
        db.scalars(
            select(StageTemplate)
            .where(
                StageTemplate.project_id.in_(visible_project_ids),
                StageTemplate.template_scope == CENTER_FILE_SCOPE,
            )
            .order_by(StageTemplate.project_id, StageTemplate.stage_id, StageTemplate.sort_order)
        )
    )
    templates_by_project: dict[int, list[StageTemplate]] = {}
    for template in templates:
        templates_by_project.setdefault(template.project_id, []).append(template)

    stage_files = list(
        db.scalars(
            select(StageFile)
            .where(
                StageFile.project_id.in_(visible_project_ids),
                StageFile.center_id.in_(visible_center_ids),
            )
            .order_by(StageFile.project_id, StageFile.center_id, StageFile.stage_id)
        )
    )
    stage_files_by_template = {
        (stage_file.center_id, stage_file.stage_template_id): stage_file
        for stage_file in stage_files
        if stage_file.stage_template_id is not None
    }
    statuses: list[StageFileStatus] = []
    expected_keys: set[tuple[int, int]] = set()
    for center in centers:
        for template in templates_by_project.get(center.project_id, []):
            key = (center.id, template.id)
            expected_keys.add(key)
            stage_file = stage_files_by_template.get(key)
            required = bool(template.required)
            statuses.append(
                StageFileStatus(
                    project_id=center.project_id,
                    center_id=center.id,
                    stage_id=template.stage_id,
                    upload_status=(
                        stage_file.upload_status if stage_file else DEFAULT_UPLOAD_STATUS
                    ),
                    review_status=(
                        stage_file.review_status if stage_file else DEFAULT_REVIEW_STATUS
                    ),
                    required=required,
                    not_applicable=bool(stage_file.not_applicable) if stage_file else False,
                )
            )

    for stage_file in stage_files:
        if stage_file.stage_template_id is not None:
            if (stage_file.center_id, stage_file.stage_template_id) in expected_keys:
                continue
            if not stage_file_required(stage_file):
                continue
        statuses.append(
            StageFileStatus(
                project_id=stage_file.project_id,
                center_id=stage_file.center_id,
                stage_id=stage_file.stage_id,
                upload_status=stage_file.upload_status,
                review_status=stage_file.review_status,
                required=stage_file_required(stage_file),
                not_applicable=bool(stage_file.not_applicable),
            )
        )
    return statuses


def _build_center_rows(
    db: Session, stage_file_statuses: list[StageFileStatus], subjects: list[Subject]
) -> list[dict]:
    centers = {
        center.id: center
        for center in db.scalars(select(Center).order_by(Center.project_id, Center.id))
    }
    center_ids = {stage_file.center_id for stage_file in stage_file_statuses} | {
        subject.center_id for subject in subjects
    }
    rows = []
    for center_id in sorted(center_ids):
        center_stage_statuses = [
            stage_file_item_status(
                stage_file.upload_status,
                stage_file.review_status,
                stage_file.required,
                stage_file.not_applicable,
            )
            for stage_file in stage_file_statuses
            if stage_file.center_id == center_id
        ]
        center_subject_statuses = [
            subject.data_status for subject in subjects if subject.center_id == center_id
        ]
        center = centers.get(center_id)
        rows.append(
            {
                "center_id": center_id,
                "center_name": center.name if center else f"中心 {center_id}",
                "status": aggregate_status(center_stage_statuses + center_subject_statuses),
                "stage_files": Counter(center_stage_statuses),
                "subjects": Counter(center_subject_statuses),
            }
        )
    return rows


def _build_stage_rows(
    db: Session, stage_file_statuses: list[StageFileStatus]
) -> list[StageCompleteness]:
    stages = {
        stage.id: stage for stage in db.scalars(select(Stage).order_by(Stage.sort_order, Stage.id))
    }
    rows = []
    for stage_id in sorted({stage_file.stage_id for stage_file in stage_file_statuses}):
        statuses = [
            stage_file_item_status(
                stage_file.upload_status,
                stage_file.review_status,
                stage_file.required,
                stage_file.not_applicable,
            )
            for stage_file in stage_file_statuses
            if stage_file.stage_id == stage_id
        ]
        counts = Counter(statuses)
        stage = stages.get(stage_id)
        rows.append(
            StageCompleteness(
                stage_id=stage_id,
                stage_name=stage_completeness_name(stage) if stage else f"阶段 {stage_id}",
                status=aggregate_required_item_statuses(statuses),
                required_count=len(statuses),
                complete_count=counts[DATA_COMPLETE],
                checking_count=counts[DATA_CHECKING],
                incomplete_count=counts[DATA_INCOMPLETE],
            )
        )
    return rows


def stage_completeness_name(stage: Stage) -> str:
    if stage.code == "STARTUP_MATERIALS":
        return "试验准备阶段资料准备"
    if stage.code == "TRIAL_MATERIALS":
        return "试验进行阶段资料准备"
    if stage.code == "CLOSEOUT_MATERIALS":
        return "试验结束阶段资料准备"
    return stage.name
