import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.api.deps import AccessContext, require_permission
from app.core.clinical_data import (
    DATA_CHECKING,
    DATA_COMPLETE,
    DATA_INCOMPLETE,
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
    UPLOADED_STATUSES,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.files import ensure_relative_path
from app.models import (
    Center,
    ClinicalSsuProgress,
    CorrectionTask,
    FileAsset,
    FileVersion,
    OperationLog,
    PdfAnnotation,
    PdfPacket,
    Project,
    ReviewRecord,
    Stage,
    StageFile,
    StageTemplate,
    Subject,
    SubjectItem,
    SubjectSnapshot,
    User,
)
from app.models.clinical_data import SubjectSection
from app.schemas import (
    ClinicalDatasetRead,
    ClinicalDatasetSummaryRead,
    ClinicalOptionalFileSummaryRead,
    ClinicalPhaseRead,
    ClinicalReviewSummaryRead,
    ClinicalSsuProgressCreate,
    ClinicalSsuProgressRead,
    ClinicalSsuProgressUpdate,
    ClinicalSsuSummaryRead,
    ClinicalStageGroupSummaryRead,
    ClinicalStatusCountRead,
    SnapshotGenerateResponse,
    SnapshotPrecheckResponse,
    StageFileApplicabilityUpdate,
    StageFileGroupRead,
    StageFileRead,
    SubjectCreate,
    SubjectItemRead,
    SubjectItemRemarkRead,
    SubjectItemRemarkUpdate,
    SubjectItemTimelineEntryRead,
    SubjectItemUpdate,
    SubjectRead,
    SubjectSectionRead,
    SubjectSnapshotHistoryItem,
    SubjectUpdate,
)
from app.services.audit import record_operation
from app.services.clinical_status import (
    recalculate_subject_status,
    required_item_status,
    stage_file_item_status,
)
from app.services.document_fields import (
    analyze_file_version_fields,
    latest_file_version,
    sync_ssu_progress_from_fields,
)
from app.services.image_data import ensure_subject_image_records
from app.services.pdf_packets import remove_packet_physical_file
from app.services.snapshot_export import (
    SnapshotJsonIntegrityError,
    SnapshotJsonNotFoundError,
    SnapshotJsonUnavailableError,
    resolve_snapshot_json_export,
)
from app.services.snapshot_generation import (
    SnapshotFileWriteError,
    SnapshotPrecheckFailed,
    generate_subject_snapshot,
)
from app.services.snapshot_precheck import run_snapshot_precheck
from app.services.stage_config import (
    CENTER_FILE_OPTION_CODES,
    CENTER_FILE_SCOPE,
    PARENT_STAGE_CODES,
    ensure_project_stage_config,
)
from app.services.subject_setup import create_default_subject_sections

router = APIRouter()
ModelT = TypeVar("ModelT", Project, Center, Stage, StageFile, Subject, SubjectItem)
DBSession = Annotated[Session, Depends(get_db)]
ClinicalRead = Annotated[AccessContext, Depends(require_permission("clinical_data:read"))]
ClinicalWrite = Annotated[AccessContext, Depends(require_permission("clinical_data:write"))]
ClinicalDelete = Annotated[AccessContext, Depends(require_permission("clinical_data:delete"))]
ExportRead = Annotated[AccessContext, Depends(require_permission("exports:read"))]
SSU_STAGE_CODES = frozenset(
    {
        "SSU_PROJECT_APPROVAL",
        "SSU_ETHICS",
        "SSU_AGREEMENT_SIGNING",
        "SSU_PROVINCIAL_FILING",
        "SSU_STARTUP_MEETING",
    }
)
SSU_STAGE_OPTIONS: tuple[tuple[str, int], ...] = (
    ("SSU_PROJECT_APPROVAL", 1),
    ("SSU_ETHICS", 2),
    ("SSU_AGREEMENT_SIGNING", 3),
    ("SSU_PROVINCIAL_FILING", 4),
    ("SSU_STARTUP_MEETING", 5),
)


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


def ensure_ssu_stage_code(stage_code: str) -> str:
    if stage_code not in SSU_STAGE_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid SSU stage code",
        )
    return stage_code


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


def child_stage_ids_for_phase(db: Session, project_id: int, phase_code: str) -> list[int]:
    return list(
        db.scalars(
            select(Stage.id)
            .where(
                Stage.project_id == project_id,
                Stage.phase_code == phase_code,
                Stage.parent_id.is_not(None),
                Stage.enabled.is_(True),
            )
            .order_by(Stage.sort_order, Stage.id)
        )
    )


def stage_ids_for_center_files(
    db: Session,
    project_id: int,
    stage_id: int | None = None,
) -> list[int]:
    if stage_id is None:
        return list(
            db.scalars(
                select(Stage.id)
                .where(
                    Stage.project_id == project_id,
                    Stage.parent_id.is_not(None),
                    Stage.option_code.in_(CENTER_FILE_OPTION_CODES),
                    Stage.enabled.is_(True),
                )
                .order_by(Stage.phase_code, Stage.sort_order, Stage.id)
            )
        )
    stage = ensure_stage_belongs_to_project(db, project_id, stage_id)
    if stage.parent_id is None:
        if stage.code in PARENT_STAGE_CODES:
            return list(
                db.scalars(
                    select(Stage.id)
                    .where(
                        Stage.project_id == project_id,
                        Stage.parent_id == stage.id,
                        Stage.option_code.in_(CENTER_FILE_OPTION_CODES),
                        Stage.enabled.is_(True),
                    )
                    .order_by(Stage.sort_order, Stage.id)
                )
            )
    if (stage.option_code or stage.code) not in CENTER_FILE_OPTION_CODES:
        return []
    return [stage.id]


def user_display_names(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(user_ids)))
    return {user.id: user.full_name or user.username for user in users}


def enrich_stage_files(db: Session, stage_files: list[StageFile]) -> None:
    ids = [stage_file.id for stage_file in stage_files]
    if not ids:
        return
    latest_uploads: dict[int, FileAsset] = {}
    uploads = db.scalars(
        select(FileAsset)
        .where(FileAsset.stage_file_id.in_(ids), FileAsset.status == "active")
        .order_by(FileAsset.uploaded_at.desc(), FileAsset.id.desc())
    )
    for upload in uploads:
        if upload.stage_file_id is not None and upload.stage_file_id not in latest_uploads:
            latest_uploads[upload.stage_file_id] = upload

    latest_reviews: dict[int, ReviewRecord] = {}
    reviews = db.scalars(
        select(ReviewRecord)
        .where(
            ReviewRecord.target_type == "stage_file",
            ReviewRecord.target_id.in_(ids),
            ReviewRecord.action.in_(["approve", "reject"]),
        )
        .order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
    )
    for review in reviews:
        latest_reviews.setdefault(review.target_id, review)

    user_ids = {
        user_id
        for item in [*latest_uploads.values(), *latest_reviews.values()]
        if (user_id := getattr(item, "uploaded_by", None) or getattr(item, "reviewer_id", None))
        is not None
    }
    user_ids.update(
        stage_file.not_applicable_by
        for stage_file in stage_files
        if stage_file.not_applicable_by is not None
    )
    names = user_display_names(db, user_ids)
    for stage_file in stage_files:
        upload = latest_uploads.get(stage_file.id)
        review = latest_reviews.get(stage_file.id)
        required = True if stage_file.stage_template is None else stage_file.stage_template.required
        stage_file.required = required
        stage_file.uploaded_by = upload.uploaded_by if upload else None
        stage_file.uploaded_by_name = names.get(upload.uploaded_by) if upload else None
        stage_file.uploaded_at = upload.uploaded_at if upload else None
        stage_file.reviewer_id = review.reviewer_id if review else None
        stage_file.reviewer_name = names.get(review.reviewer_id) if review else None
        stage_file.reviewed_at = review.created_at if review else None
        stage_file.not_applicable_by_name = names.get(stage_file.not_applicable_by)
        stage_file.completeness_status = stage_file_item_status(
            stage_file.upload_status,
            stage_file.review_status,
            required,
            stage_file.not_applicable,
        )


def enrich_subject_items(db: Session, subject_items: list[SubjectItem]) -> None:
    ids = [item.id for item in subject_items]
    if not ids:
        return
    latest_uploads: dict[int, FileAsset] = {}
    uploads = db.scalars(
        select(FileAsset)
        .where(FileAsset.subject_item_id.in_(ids), FileAsset.status == "active")
        .order_by(FileAsset.uploaded_at.desc(), FileAsset.id.desc())
    )
    for upload in uploads:
        if upload.subject_item_id is not None and upload.subject_item_id not in latest_uploads:
            latest_uploads[upload.subject_item_id] = upload

    latest_reviews: dict[int, ReviewRecord] = {}
    reviews = db.scalars(
        select(ReviewRecord)
        .where(
            ReviewRecord.target_type == "subject_item",
            ReviewRecord.target_id.in_(ids),
            ReviewRecord.action.in_(["approve", "reject"]),
        )
        .order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
    )
    for review in reviews:
        latest_reviews.setdefault(review.target_id, review)

    user_ids = {
        user_id
        for item in [*latest_uploads.values(), *latest_reviews.values()]
        if (user_id := getattr(item, "uploaded_by", None) or getattr(item, "reviewer_id", None))
        is not None
    }
    names = user_display_names(db, user_ids)
    for subject_item in subject_items:
        upload = latest_uploads.get(subject_item.id)
        review = latest_reviews.get(subject_item.id)
        subject_item.uploaded_by = upload.uploaded_by if upload else None
        subject_item.uploaded_by_name = names.get(upload.uploaded_by) if upload else None
        subject_item.uploaded_at = upload.uploaded_at if upload else None
        subject_item.reviewer_id = review.reviewer_id if review else None
        subject_item.reviewer_name = names.get(review.reviewer_id) if review else None
        subject_item.reviewed_at = review.created_at if review else None
        subject_item.completeness_status = required_item_status(
            subject_item.upload_status,
            subject_item.review_status,
            subject_item.required,
        )


def materialize_stage_files(
    db: Session,
    project_id: int,
    center_id: int,
    stage_id: int | None = None,
) -> list[StageFile]:
    ensure_project_stage_config(db, project_id)
    stage_ids = stage_ids_for_center_files(db, project_id, stage_id)
    if not stage_ids:
        return []
    template_statement = select(StageTemplate).where(
        StageTemplate.project_id == project_id,
        StageTemplate.stage_id.in_(stage_ids),
        StageTemplate.template_scope == CENTER_FILE_SCOPE,
    )
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
        StageFile.stage_id.in_(stage_ids),
    )
    stage_files = list(
        db.scalars(
            stage_file_statement.order_by(
                StageFile.stage_id,
                StageFile.id,
            )
        )
    )
    enrich_stage_files(db, stage_files)
    return stage_files


def list_ssu_progress_records(
    db: Session,
    project_id: int,
    center_id: int,
) -> list[ClinicalSsuProgress]:
    existing_stage_codes = set(
        db.scalars(
            select(ClinicalSsuProgress.stage_code).where(
                ClinicalSsuProgress.project_id == project_id,
                ClinicalSsuProgress.center_id == center_id,
            )
        )
    )
    created = False
    for stage_code, _ in SSU_STAGE_OPTIONS:
        if stage_code in existing_stage_codes:
            continue
        db.add(
            ClinicalSsuProgress(
                project_id=project_id,
                center_id=center_id,
                stage_code=stage_code,
                status="not_started",
            )
        )
        created = True
    if created:
        db.commit()
    records = list(
        db.scalars(
            select(ClinicalSsuProgress)
            .where(
                ClinicalSsuProgress.project_id == project_id,
                ClinicalSsuProgress.center_id == center_id,
            )
            .order_by(ClinicalSsuProgress.id)
        )
    )
    enrich_ssu_progress_files(db, records)
    return sorted(records, key=lambda record: (ssu_stage_order(record.stage_code), record.id))


def normalized_file_name(value: str | None) -> str:
    stem = Path(value or "").stem
    cleaned = re.sub(r"(?i)(?:^|[_\\-\\s])(v|version|版本)?\\d+(?:\\.\\d+)*$", "", stem)
    return "".join(char.lower() for char in cleaned if char.isalnum())


def enrich_ssu_progress_files(db: Session, records: list[ClinicalSsuProgress]) -> None:
    if not records:
        return
    progress_ids = [record.id for record in records]
    project_id = records[0].project_id
    center_id = records[0].center_id
    ssu_files = list(
        db.scalars(
            select(FileAsset).where(
                FileAsset.ssu_progress_id.in_(progress_ids),
                FileAsset.status == "active",
            )
        )
    )
    stage_files = list(
        db.scalars(
            select(FileAsset).where(
                FileAsset.project_id == project_id,
                FileAsset.center_id == center_id,
                FileAsset.stage_file_id.is_not(None),
                FileAsset.status == "active",
            )
        )
    )
    stage_file_names = {
        normalized_file_name(file_asset.original_name)
        for file_asset in stage_files
        if normalized_file_name(file_asset.original_name)
    }
    files_by_progress: dict[int, list[FileAsset]] = {record.id: [] for record in records}
    for file_asset in ssu_files:
        if file_asset.ssu_progress_id is not None:
            files_by_progress.setdefault(file_asset.ssu_progress_id, []).append(file_asset)
    for record in records:
        files = files_by_progress.get(record.id, [])
        record.file_count = len(files)
        record.latest_uploaded_at = max((file.uploaded_at for file in files), default=None)
        record.same_name_stage_file_count = sum(
            1
            for file_asset in files
            if normalized_file_name(file_asset.original_name) in stage_file_names
        )


def ssu_stage_order(stage_code: str) -> int:
    order = {
        "SSU_PROJECT_APPROVAL": 1,
        "SSU_ETHICS": 2,
        "SSU_AGREEMENT_SIGNING": 3,
        "SSU_PROVINCIAL_FILING": 4,
        "SSU_STARTUP_MEETING": 5,
    }
    return order.get(stage_code, 99)


def get_ssu_progress_or_404(
    db: Session,
    access: AccessContext,
    progress_id: int,
) -> ClinicalSsuProgress:
    progress = db.get(ClinicalSsuProgress, progress_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSU progress not found")
    ensure_dataset_scope(db, access, progress.project_id, progress.center_id)
    return progress


def remove_file_asset_physical_files(file_asset: FileAsset) -> None:
    paths = {file_asset.storage_path, *(version.storage_path for version in file_asset.versions)}
    for storage_path in paths:
        try:
            path = ensure_relative_path(settings.file_storage_root, storage_path)
        except ValueError:
            continue
        if path.exists():
            path.unlink()
            for parent in path.parents:
                if parent == settings.file_storage_root.resolve():
                    break
                try:
                    parent.rmdir()
                except OSError:
                    break


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


def remove_subject_physical_files(file_assets: list[FileAsset]) -> None:
    paths: set[str] = set()
    for file_asset in file_assets:
        paths.add(file_asset.storage_path)
        for version in file_asset.versions:
            paths.add(version.storage_path)

    for storage_path in paths:
        try:
            path = ensure_relative_path(settings.file_storage_root, storage_path)
        except ValueError:
            continue
        if not path.exists():
            continue
        path.unlink()
        for parent in path.parents:
            if parent == settings.file_storage_root.resolve():
                break
            try:
                parent.rmdir()
            except OSError:
                break


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
    ensure_project_stage_config(db, project_id)
    db.commit()
    phases = list(
        db.scalars(
            select(Stage)
            .where(Stage.project_id == project_id, Stage.parent_id.is_(None))
            .order_by(Stage.sort_order, Stage.id)
        )
    )
    children = list(
        db.scalars(
            select(Stage)
            .where(Stage.project_id == project_id, Stage.parent_id.is_not(None))
            .where(Stage.enabled.is_(True))
            .order_by(Stage.phase_code, Stage.sort_order, Stage.id)
        )
    )
    phase_by_code = {stage.code: stage for stage in phases}
    children_by_phase: dict[str, list[Stage]] = {}
    for child in children:
        children_by_phase.setdefault(child.phase_code or "", []).append(child)
    startup_files = (
        materialize_stage_files(db, project_id, center_id, phase_by_code["STARTUP"].id)
        if "STARTUP" in phase_by_code
        else []
    )
    closeout_files = (
        materialize_stage_files(db, project_id, center_id, phase_by_code["CLOSEOUT"].id)
        if "CLOSEOUT" in phase_by_code
        else []
    )
    trial_files = (
        materialize_stage_files(db, project_id, center_id, phase_by_code["TRIAL"].id)
        if "TRIAL" in phase_by_code
        else []
    )
    subjects = list(
        db.scalars(
            select(Subject)
            .where(Subject.project_id == project_id, Subject.center_id == center_id)
            .order_by(Subject.id)
        )
    )
    startup_groups = stage_file_groups(children_by_phase.get("STARTUP", []), startup_files)
    trial_groups = stage_file_groups(
        [
            stage
            for stage in children_by_phase.get("TRIAL", [])
            if (stage.option_code or stage.code) in CENTER_FILE_OPTION_CODES
        ],
        trial_files,
    )
    closeout_groups = stage_file_groups(children_by_phase.get("CLOSEOUT", []), closeout_files)
    ssu_progress = list_ssu_progress_records(db, project_id, center_id)
    all_stage_files = startup_files + trial_files + closeout_files
    all_stage_groups = startup_groups + trial_groups + closeout_groups
    summary = build_clinical_dataset_summary(
        all_stage_files,
        subjects,
        ssu_progress,
        all_stage_groups,
    )
    phase_reads = []
    for phase in phases:
        phase_files: list[StageFile] = []
        phase_file_groups: list[StageFileGroupRead] = []
        if phase.code == "STARTUP":
            phase_files = startup_files
            phase_file_groups = startup_groups
        if phase.code == "TRIAL":
            phase_files = trial_files
            phase_file_groups = trial_groups
        if phase.code == "CLOSEOUT":
            phase_files = closeout_files
            phase_file_groups = closeout_groups
        phase_reads.append(
            ClinicalPhaseRead(
                phase=phase,
                child_stages=children_by_phase.get(phase.code, []),
                files=phase_files,
                file_groups=phase_file_groups,
                subjects=subjects if phase.code == "TRIAL" else [],
            )
        )
    return ClinicalDatasetRead(
        project_id=project_id,
        center_id=center_id,
        stages=phases,
        child_stages=children,
        phases=phase_reads,
        startup_file_groups=startup_groups,
        startup_files=startup_files,
        ssu_progress=ssu_progress,
        trial_stages=children_by_phase.get("TRIAL", []),
        trial_file_groups=trial_groups,
        trial_files=trial_files,
        subjects=subjects,
        closeout_file_groups=closeout_groups,
        closeout_files=closeout_files,
        stage_file_count=len(all_stage_files),
        subject_count=len(subjects),
        summary=summary,
    )


def stage_file_groups(stages: list[Stage], files: list[StageFile]) -> list[StageFileGroupRead]:
    files_by_stage: dict[int, list[StageFile]] = {}
    for file in files:
        files_by_stage.setdefault(file.stage_id, []).append(file)
    return [
        StageFileGroupRead(stage=stage, files=files_by_stage.get(stage.id, []))
        for stage in stages
        if stage.enabled
    ]


def status_count_read(counter: Counter[str]) -> ClinicalStatusCountRead:
    return ClinicalStatusCountRead(
        complete=counter[DATA_COMPLETE],
        checking=counter[DATA_CHECKING],
        incomplete=counter[DATA_INCOMPLETE],
    )


def build_clinical_dataset_summary(
    stage_files: list[StageFile],
    subjects: list[Subject],
    ssu_progress: list[ClinicalSsuProgress],
    stage_groups: list[StageFileGroupRead],
) -> ClinicalDatasetSummaryRead:
    stage_file_statuses = Counter(
        stage_file.completeness_status or DATA_INCOMPLETE for stage_file in stage_files
    )
    subject_statuses = Counter(subject.data_status for subject in subjects)
    review_statuses = Counter(stage_file.review_status for stage_file in stage_files)
    review_statuses.update(subject.review_status for subject in subjects)
    optional_files = [stage_file for stage_file in stage_files if not stage_file.required]
    ssu_statuses = Counter(record.status for record in ssu_progress)
    group_summaries: list[ClinicalStageGroupSummaryRead] = []
    for group in stage_groups:
        group_statuses = Counter(
            stage_file.completeness_status or DATA_INCOMPLETE for stage_file in group.files
        )
        group_summaries.append(
            ClinicalStageGroupSummaryRead(
                stage_id=group.stage.id,
                stage_code=group.stage.code,
                stage_name=group.stage.name,
                phase_code=group.stage.phase_code,
                total=len(group.files),
                complete=group_statuses[DATA_COMPLETE],
                checking=group_statuses[DATA_CHECKING],
                incomplete=group_statuses[DATA_INCOMPLETE],
            )
        )
    return ClinicalDatasetSummaryRead(
        stage_files=status_count_read(stage_file_statuses),
        subjects=status_count_read(subject_statuses),
        reviews=ClinicalReviewSummaryRead(
            unreviewed=review_statuses["unreviewed"],
            pending=review_statuses["pending"],
            approved=review_statuses["approved"],
            rejected=review_statuses["rejected"],
        ),
        ssu=ClinicalSsuSummaryRead(
            total=len(ssu_progress),
            completed=ssu_statuses["completed"],
            blocked=ssu_statuses["blocked"],
            active=sum(
                count
                for status, count in ssu_statuses.items()
                if status not in {"not_started", "completed", "blocked"}
            ),
        ),
        optional_files=ClinicalOptionalFileSummaryRead(
            total=len(optional_files),
            not_applicable=sum(1 for stage_file in optional_files if stage_file.not_applicable),
            uploaded=sum(
                1 for stage_file in optional_files if stage_file.upload_status in UPLOADED_STATUSES
            ),
        ),
        stage_groups=group_summaries,
    )


def stage_file_has_active_file(db: Session, stage_file_id: int) -> bool:
    return (
        db.scalar(
            select(FileAsset.id)
            .where(FileAsset.stage_file_id == stage_file_id, FileAsset.status == "active")
            .limit(1)
        )
        is not None
    )


@router.get("/clinical-datasets/ssu-progress", response_model=list[ClinicalSsuProgressRead])
def list_ssu_progress(
    db: DBSession,
    access: ClinicalRead,
    project_id: Annotated[int, Query()],
    center_id: Annotated[int, Query()],
) -> list[ClinicalSsuProgress]:
    ensure_dataset_scope(db, access, project_id, center_id)
    return list_ssu_progress_records(db, project_id, center_id)


@router.post(
    "/clinical-datasets/ssu-progress",
    response_model=ClinicalSsuProgressRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ssu_progress(
    payload: ClinicalSsuProgressCreate,
    db: DBSession,
    access: ClinicalWrite,
) -> ClinicalSsuProgress:
    ensure_dataset_scope(db, access, payload.project_id, payload.center_id)
    ensure_ssu_stage_code(payload.stage_code)
    progress = ClinicalSsuProgress(**payload.model_dump())
    db.add(progress)
    commit_or_conflict(db, "SSU progress already exists")
    db.refresh(progress)
    return progress


@router.patch(
    "/clinical-datasets/ssu-progress/{progress_id}",
    response_model=ClinicalSsuProgressRead,
)
def update_ssu_progress(
    progress_id: int,
    payload: ClinicalSsuProgressUpdate,
    db: DBSession,
    access: ClinicalWrite,
) -> ClinicalSsuProgress:
    progress = get_ssu_progress_or_404(db, access, progress_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(progress, key, value)
    commit_or_conflict(db, "SSU progress update failed")
    db.refresh(progress)
    return progress


@router.post(
    "/clinical-datasets/ssu-progress/{progress_id}/apply-extracted-fields",
    response_model=ClinicalSsuProgressRead,
)
def apply_ssu_extracted_fields(
    progress_id: int,
    db: DBSession,
    access: ClinicalWrite,
    request: Request,
) -> ClinicalSsuProgress:
    progress = get_ssu_progress_or_404(db, access, progress_id)
    file_assets = list(
        db.scalars(
            select(FileAsset)
            .where(
                FileAsset.ssu_progress_id == progress.id,
                FileAsset.status == "active",
            )
            .order_by(FileAsset.id)
        )
    )
    applied_file_ids: list[int] = []
    extracted_fields = []
    for file_asset in file_assets:
        file_version = latest_file_version(db, file_asset)
        fields = analyze_file_version_fields(db, file_asset, file_version)
        extracted_fields.extend(fields)
        applied_file_ids.append(file_asset.id)
    sync_ssu_progress_from_fields(db, progress, extracted_fields)
    record_operation(
        db,
        action="clinical_dataset.ssu_apply_extracted_fields",
        request=request,
        access=access,
        target_type="clinical_ssu_progress",
        target_id=progress.id,
        project_id=progress.project_id,
        center_id=progress.center_id,
        detail={"file_ids": applied_file_ids, "file_count": len(applied_file_ids)},
    )
    db.commit()
    db.refresh(progress)
    enrich_ssu_progress_files(db, [progress])
    return progress


@router.delete(
    "/clinical-datasets/ssu-progress/{progress_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ssu_progress(
    progress_id: int,
    db: DBSession,
    access: ClinicalWrite,
) -> None:
    progress = get_ssu_progress_or_404(db, access, progress_id)
    for file_asset in db.scalars(
        select(FileAsset).where(FileAsset.ssu_progress_id == progress.id)
    ):
        remove_file_asset_physical_files(file_asset)
        db.delete(file_asset)
    db.delete(progress)
    db.commit()


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


@router.patch("/stage-files/{stage_file_id}/applicability", response_model=StageFileRead)
def update_stage_file_applicability(
    stage_file_id: int,
    payload: StageFileApplicabilityUpdate,
    db: DBSession,
    access: ClinicalWrite,
    request: Request,
) -> StageFile:
    stage_file = get_or_404(db, StageFile, stage_file_id, "stage file")
    ensure_dataset_scope(db, access, stage_file.project_id, stage_file.center_id)
    required = True if stage_file.stage_template is None else stage_file.stage_template.required
    if required and payload.not_applicable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="required stage file cannot be marked as not applicable",
        )
    if payload.not_applicable and stage_file_has_active_file(db, stage_file.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uploaded stage file cannot be marked as not applicable",
        )

    reason = payload.reason.strip() if payload.reason else None
    if payload.not_applicable:
        stage_file.not_applicable = True
        stage_file.not_applicable_reason = reason
        stage_file.not_applicable_by = access.user.id
        stage_file.not_applicable_at = datetime.now(UTC)
    else:
        stage_file.not_applicable = False
        stage_file.not_applicable_reason = None
        stage_file.not_applicable_by = None
        stage_file.not_applicable_at = None

    record_operation(
        db,
        action="stage_file.applicability.update",
        request=request,
        access=access,
        target_type="stage_file",
        target_id=stage_file.id,
        project_id=stage_file.project_id,
        center_id=stage_file.center_id,
        detail={
            "not_applicable": payload.not_applicable,
            "reason": reason,
        },
    )
    commit_or_conflict(db, "stage file applicability update failed")
    db.refresh(stage_file)
    enrich_stage_files(db, [stage_file])
    return stage_file


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
def create_subject(
    payload: SubjectCreate,
    db: DBSession,
    access: ClinicalWrite,
    request: Request,
) -> Subject:
    center = ensure_dataset_scope(db, access, payload.project_id, payload.center_id)
    subject_data = payload.model_dump()
    subject_data["center_id"] = center.id
    subject = Subject(**subject_data, added_by=access.user.id)
    db.add(subject)
    try:
        db.flush()
        create_default_subject_sections(db, subject)
        ensure_subject_image_records(db, subject)
        record_operation(
            db,
            action="subject.create",
            request=request,
            access=access,
            target_type="subject",
            target_id=subject.id,
            project_id=subject.project_id,
            center_id=subject.center_id,
            detail={"screening_no": subject.screening_no},
        )
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


def ensure_snapshot_generate_role(access: AccessContext) -> None:
    if access.is_admin or "project_manager" in access.roles:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only admins or project managers can generate released snapshots",
    )


@router.post("/subjects/{subject_id}/snapshots", response_model=SnapshotGenerateResponse)
def generate_subject_snapshot_endpoint(
    subject_id: int,
    db: DBSession,
    access: ClinicalWrite,
) -> SnapshotGenerateResponse:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    ensure_snapshot_generate_role(access)
    result = None
    try:
        result = generate_subject_snapshot(db, subject, generated_by=access.user.id)
        db.commit()
    except SnapshotPrecheckFailed as exc:
        db.commit()
        for check in exc.result.checks:
            db.refresh(check)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=SnapshotPrecheckResponse(
                subject_id=exc.result.subject_id,
                snapshot_type=exc.result.snapshot_type,
                schema_version=exc.result.schema_version,
                check_run_id=exc.result.check_run_id,
                eligible=exc.result.eligible,
                blocking_failure_count=exc.result.blocking_failure_count,
                warning_count=exc.result.warning_count,
                checks=exc.result.checks,
            ).model_dump(mode="json"),
        ) from exc
    except SnapshotFileWriteError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to write snapshot json",
        ) from exc
    except SQLAlchemyError:
        db.rollback()
        if result is not None:
            ensure_relative_path(settings.file_storage_root, result.storage_path).unlink(
                missing_ok=True
            )
        raise

    db.refresh(result.snapshot)
    return SnapshotGenerateResponse(
        snapshot=result.snapshot,
        check_run_id=result.check_run_id,
        storage_path=result.storage_path,
        file_hash=result.file_hash,
        file_size=result.file_size,
    )


@router.get("/subjects/{subject_id}/snapshots", response_model=list[SubjectSnapshotHistoryItem])
def list_subject_snapshots(
    subject_id: int,
    db: DBSession,
    access: ClinicalRead,
) -> list[SubjectSnapshotHistoryItem]:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    snapshots = list(
        db.scalars(
            select(SubjectSnapshot)
            .where(SubjectSnapshot.subject_id == subject.id)
            .order_by(SubjectSnapshot.snapshot_version.desc(), SubjectSnapshot.id.desc())
        )
    )
    generator_ids = {snapshot.generated_by for snapshot in snapshots if snapshot.generated_by}
    generators = {}
    if generator_ids:
        generators = {
            user.id: user
            for user in db.scalars(select(User).where(User.id.in_(generator_ids)))
        }
    return [
        SubjectSnapshotHistoryItem.model_validate(snapshot).model_copy(
            update={
                "generated_by_name": (
                    generators[snapshot.generated_by].full_name
                    or generators[snapshot.generated_by].username
                    if snapshot.generated_by in generators
                    else None
                )
            }
        )
        for snapshot in snapshots
    ]


@router.post("/subjects/{subject_id}/snapshots/precheck", response_model=SnapshotPrecheckResponse)
def precheck_subject_snapshot(
    subject_id: int,
    db: DBSession,
    access: ClinicalWrite,
) -> SnapshotPrecheckResponse:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    result = run_snapshot_precheck(db, subject)
    db.commit()
    for check in result.checks:
        db.refresh(check)
    return SnapshotPrecheckResponse(
        subject_id=result.subject_id,
        snapshot_type=result.snapshot_type,
        schema_version=result.schema_version,
        check_run_id=result.check_run_id,
        eligible=result.eligible,
        blocking_failure_count=result.blocking_failure_count,
        warning_count=result.warning_count,
        checks=result.checks,
    )


@router.get("/subjects/{subject_id}/snapshots/{snapshot_id}/json")
def download_subject_snapshot_json(
    subject_id: int,
    snapshot_id: int,
    db: DBSession,
    access: ExportRead,
    request: Request,
) -> FileResponse:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    try:
        export = resolve_snapshot_json_export(
            db,
            subject_id=subject.id,
            snapshot_id=snapshot_id,
        )
    except SnapshotJsonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="snapshot json not found",
        ) from exc
    except SnapshotJsonUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="snapshot json is not available for export",
        ) from exc
    except SnapshotJsonIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="snapshot json integrity check failed",
        ) from exc

    record_operation(
        db,
        action="subject_snapshot.download_json",
        request=request,
        access=access,
        target_type="subject_snapshot",
        target_id=export.snapshot.id,
        project_id=export.snapshot.project_id,
        center_id=export.snapshot.center_id,
        detail={
            "snapshot_id": export.snapshot.id,
            "snapshot_version": export.snapshot.snapshot_version,
            "schema_version": export.snapshot.schema_version,
            "file_hash": export.file_hash,
            "file_size": export.file_size,
        },
    )
    db.commit()
    return FileResponse(
        export.path,
        media_type="application/json",
        filename=export.filename,
    )


@router.put("/subjects/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    db: DBSession,
    access: ClinicalWrite,
    request: Request,
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
    if "subject_arm" in update_data:
        create_default_subject_sections(db, subject)
    record_operation(
        db,
        action="subject.update",
        request=request,
        access=access,
        target_type="subject",
        target_id=subject.id,
        project_id=subject.project_id,
        center_id=subject.center_id,
        detail={"changed_fields": sorted(update_data), "screening_no": subject.screening_no},
    )
    commit_or_conflict(db, "screening number already exists in this project center")
    db.refresh(subject)
    return subject


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    db: DBSession,
    access: ClinicalDelete,
    request: Request,
) -> None:
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_access(access, subject)
    subject_item_ids = list(
        db.scalars(select(SubjectItem.id).where(SubjectItem.subject_id == subject.id))
    )
    file_condition = FileAsset.subject_id == subject.id
    if subject_item_ids:
        file_condition = or_(file_condition, FileAsset.subject_item_id.in_(subject_item_ids))
    file_assets = list(db.scalars(select(FileAsset).where(file_condition)))
    pdf_packets = list(db.scalars(select(PdfPacket).where(PdfPacket.subject_id == subject.id)))
    record_operation(
        db,
        action="subject.delete",
        request=request,
        access=access,
        target_type="subject",
        target_id=subject.id,
        project_id=subject.project_id,
        center_id=subject.center_id,
        detail={
            "screening_no": subject.screening_no,
            "subject_item_count": len(subject_item_ids),
            "file_count": len(file_assets),
            "pdf_packet_count": len(pdf_packets),
        },
    )
    remove_subject_physical_files(file_assets)
    for packet in pdf_packets:
        remove_packet_physical_file(packet)
    db.delete(subject)
    db.commit()


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
    items = list(
        db.scalars(
            select(SubjectItem)
            .join(SubjectSection, SubjectItem.section_id == SubjectSection.id)
            .where(SubjectItem.subject_id == subject_id)
            .order_by(SubjectSection.sort_order, SubjectItem.sort_order, SubjectItem.id)
        )
    )
    enrich_subject_items(db, items)
    return items


@router.put("/subject-items/{item_id}", response_model=SubjectItemRead)
def update_subject_item(
    item_id: int,
    payload: SubjectItemUpdate,
    db: DBSession,
    access: ClinicalWrite,
    request: Request,
) -> SubjectItem:
    item = get_or_404(db, SubjectItem, item_id, "subject item")
    subject = get_or_404(db, Subject, item.subject_id, "subject")
    ensure_subject_access(access, subject)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    recalculate_subject_status(db, subject)
    update_data = payload.model_dump(exclude_unset=True)
    record_operation(
        db,
        action="subject_item.update",
        request=request,
        access=access,
        target_type="subject_item",
        target_id=item.id,
        project_id=subject.project_id,
        center_id=subject.center_id,
        detail={"changed_fields": sorted(update_data), "item_code": item.item_code},
    )
    db.commit()
    db.refresh(item)
    enrich_subject_items(db, [item])
    return item


@router.patch("/subject-items/{item_id}/remark", response_model=SubjectItemRemarkRead)
def update_subject_item_remark(
    item_id: int,
    payload: SubjectItemRemarkUpdate,
    db: DBSession,
    access: ClinicalWrite,
    request: Request,
) -> SubjectItemRemarkRead:
    item = get_or_404(db, SubjectItem, item_id, "subject item")
    subject = get_or_404(db, Subject, item.subject_id, "subject")
    ensure_subject_access(access, subject)
    next_remark = payload.remark.strip() if payload.remark else None
    if next_remark == "":
        next_remark = None
    if item.remark != next_remark:
        item.remark = next_remark
        record_operation(
            db,
            action="subject_item.remark.update",
            request=request,
            access=access,
            target_type="subject_item",
            target_id=item.id,
            project_id=subject.project_id,
            center_id=subject.center_id,
            detail={
                "item_code": item.item_code,
                "remark": item.remark,
            },
        )
        db.commit()
        db.refresh(item)
    return SubjectItemRemarkRead(success=True, remark=item.remark, updated_at=item.updated_at)


TIMELINE_ACTION_LABELS = {
    "file.upload": "上传",
    "file.replace": "重新上传",
    "review.submit": "提交审核",
    "review.approve": "通过",
    "review.reject": "驳回",
    "pdf_annotation.create": "创建批注",
    "correction_task.create": "生成整改任务",
    "correction_task.submit": "提交整改",
    "correction_task.approve": "复审通过",
    "correction_task.return": "再次退回",
    "subject_item.remark.update": "修改备注",
    "subject_item.update": "更新资料项",
}


def timeline_entry(
    *,
    source: str,
    source_id: int,
    occurred_at: datetime,
    action: str,
    actor: str | None = None,
    description: str | None = None,
    file_id: int | None = None,
    file_version: int | None = None,
    task_id: int | None = None,
    remark: str | None = None,
) -> SubjectItemTimelineEntryRead:
    return SubjectItemTimelineEntryRead(
        id=f"{source}-{source_id}-{action}",
        occurred_at=occurred_at,
        actor=actor,
        action=action,
        action_label=TIMELINE_ACTION_LABELS.get(action, action),
        description=description,
        file_id=file_id,
        file_version=file_version,
        task_id=task_id,
        remark=remark,
    )


@router.get("/subject-items/{item_id}/timeline", response_model=list[SubjectItemTimelineEntryRead])
def list_subject_item_timeline(
    item_id: int,
    db: DBSession,
    access: ClinicalRead,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SubjectItemTimelineEntryRead]:
    item = get_or_404(db, SubjectItem, item_id, "subject item")
    subject = get_or_404(db, Subject, item.subject_id, "subject")
    ensure_subject_access(access, subject)

    files = list(db.scalars(select(FileAsset).where(FileAsset.subject_item_id == item.id)))
    file_ids = [file_asset.id for file_asset in files]
    versions = (
        list(
            db.scalars(
                select(FileVersion)
                .where(FileVersion.file_id.in_(file_ids))
                .order_by(FileVersion.uploaded_at.desc(), FileVersion.id.desc())
            )
        )
        if file_ids
        else []
    )
    version_by_id = {version.id: version for version in versions}
    reviews = list(
        db.scalars(
            select(ReviewRecord)
            .where(ReviewRecord.target_type == "subject_item", ReviewRecord.target_id == item.id)
            .order_by(ReviewRecord.created_at.desc(), ReviewRecord.id.desc())
        )
    )
    annotations = list(
        db.scalars(
            select(PdfAnnotation)
            .where(PdfAnnotation.subject_item_id == item.id, PdfAnnotation.deleted_at.is_(None))
            .order_by(PdfAnnotation.created_at.desc(), PdfAnnotation.id.desc())
        )
    )
    tasks = list(
        db.scalars(
            select(CorrectionTask)
            .where(CorrectionTask.subject_item_id == item.id)
            .order_by(CorrectionTask.created_at.desc(), CorrectionTask.id.desc())
        )
    )
    logs = list(
        db.scalars(
            select(OperationLog)
            .where(
                OperationLog.target_type == "subject_item",
                OperationLog.target_id == item.id,
                OperationLog.action.in_(["subject_item.remark.update", "subject_item.update"]),
            )
            .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
        )
    )

    user_ids = {
        user_id
        for user_id in [
            *(version.uploaded_by for version in versions),
            *(review.reviewer_id for review in reviews),
            *(annotation.created_by for annotation in annotations),
            *(task.created_by for task in tasks),
        ]
        if user_id is not None
    }
    names = user_display_names(db, user_ids)
    entries: list[SubjectItemTimelineEntryRead] = []

    for version in versions:
        action = "file.upload" if version.version == 1 else "file.replace"
        entries.append(
            timeline_entry(
                source="file-version",
                source_id=version.id,
                occurred_at=version.uploaded_at,
                actor=names.get(version.uploaded_by) if version.uploaded_by else None,
                action=action,
                description=version.change_note or version.original_name,
                file_id=version.file_id,
                file_version=version.version,
            )
        )

    for review in reviews:
        action = f"review.{review.action}"
        entries.append(
            timeline_entry(
                source="review",
                source_id=review.id,
                occurred_at=review.created_at,
                actor=names.get(review.reviewer_id) if review.reviewer_id else None,
                action=action,
                description=review.comment,
            )
        )

    for annotation in annotations:
        version = version_by_id.get(annotation.file_version_id)
        entries.append(
            timeline_entry(
                source="annotation",
                source_id=annotation.id,
                occurred_at=annotation.created_at,
                actor=names.get(annotation.created_by) if annotation.created_by else None,
                action="pdf_annotation.create",
                description=annotation.comment,
                file_id=annotation.file_id,
                file_version=version.version if version else None,
            )
        )

    for task in tasks:
        source_version = version_by_id.get(task.source_file_version_id)
        latest_version = version_by_id.get(task.latest_file_version_id or 0)
        entries.append(
            timeline_entry(
                source="task",
                source_id=task.id,
                occurred_at=task.created_at,
                actor=names.get(task.created_by) if task.created_by else None,
                action="correction_task.create",
                description=task.title,
                file_id=task.file_id,
                file_version=source_version.version if source_version else None,
                task_id=task.id,
                remark=task.description,
            )
        )
        if task.submitted_at is not None:
            entries.append(
                timeline_entry(
                    source="task-submit",
                    source_id=task.id,
                    occurred_at=task.submitted_at,
                    actor=names.get(latest_version.uploaded_by)
                    if latest_version and latest_version.uploaded_by
                    else None,
                    action="correction_task.submit",
                    description=task.submission_remark,
                    file_id=task.file_id,
                    file_version=latest_version.version if latest_version else None,
                    task_id=task.id,
                )
            )
        if task.reviewed_at is not None:
            action = (
                "correction_task.approve"
                if task.review_result == "approved"
                else "correction_task.return"
            )
            entries.append(
                timeline_entry(
                    source="task-review",
                    source_id=task.id,
                    occurred_at=task.reviewed_at,
                    action=action,
                    description=task.review_comment,
                    file_id=task.file_id,
                    file_version=latest_version.version if latest_version else None,
                    task_id=task.id,
                )
            )

    for log in logs:
        detail = log.detail_json if isinstance(log.detail_json, dict) else {}
        changed_fields = detail.get("changed_fields", [])
        is_remark_update = log.action == "subject_item.remark.update" or (
            log.action == "subject_item.update"
            and isinstance(changed_fields, list)
            and "remark" in changed_fields
        )
        entries.append(
            timeline_entry(
                source="operation",
                source_id=log.id,
                occurred_at=log.created_at,
                actor=log.username,
                action="subject_item.remark.update" if is_remark_update else log.action,
                description="备注已更新" if is_remark_update else "资料项信息已更新",
                remark=detail.get("remark") if isinstance(detail.get("remark"), str) else None,
            )
        )

    entries.sort(key=lambda entry: (entry.occurred_at, entry.id), reverse=True)
    return entries[:limit]
