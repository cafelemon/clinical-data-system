import mimetypes
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.api.deps import AccessContext, require_permission
from app.core.config import settings
from app.core.database import get_db
from app.core.files import ensure_relative_path
from app.models import Center, ImageEvidenceIndex, Project, Subject, SubjectImageRecord
from app.schemas import (
    LandmarkConfirmRequest,
    LandmarkIndexResponse,
    ReportImageIndexResponse,
    SubjectImageRowRead,
    SubjectImageUploadRead,
)
from app.services.audit import record_operation
from app.services.image_data import (
    IMAGE_TYPES,
    IMAGE_UPLOAD_STATUS_DONE,
    analyze_and_extract_zip,
    clear_record_physical_files,
    ensure_subject_image_records,
    ensure_subjects_image_records,
    image_record_directory,
    reset_record_metadata,
    store_image_upload,
    validate_upload_file,
)
from app.services.landmark_index import (
    clear_landmark_index,
    confirm_landmark_candidate,
    landmark_counts,
    landmark_index_state,
    maybe_rebuild_landmark_index,
    rebuild_landmark_index,
)
from app.services.report_image_index import (
    clear_report_image_index,
    rebuild_report_image_index,
)

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
ImageReadAccess = Annotated[AccessContext, Depends(require_permission("image_data:read"))]
ImageEvidenceManageAccess = Annotated[
    AccessContext,
    Depends(require_permission("image_data:manage_evidence")),
]
ImageUpload = Annotated[UploadFile, File()]


def ensure_project_access(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_center_access(access: AccessContext, center: Center) -> None:
    if not access.can_access_center(center.id, center.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")


def ensure_record_scope(access: AccessContext, record: SubjectImageRecord) -> None:
    if not access.can_access_center(record.center_id, record.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Image scope denied")


def ensure_upload_permission(access: AccessContext, record: SubjectImageRecord) -> None:
    permission_by_type = {
        "raw": "image_data:upload_raw",
        "enhanced": "image_data:upload_enhanced",
        "report": "image_data:upload_report",
    }
    if not access.has_permission(permission_by_type[record.image_type]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def ensure_download_permission(access: AccessContext, record: SubjectImageRecord) -> None:
    permission_by_type = {
        "raw": "image_data:upload_raw",
        "enhanced": "image_data:upload_enhanced",
        "report": "image_data:upload_report",
    }
    if not access.has_permission(permission_by_type[record.image_type]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def get_record_or_404(db: Session, record_id: int) -> SubjectImageRecord:
    record = db.get(SubjectImageRecord, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="image record not found")
    return record


def scoped_subject_statement(access: AccessContext):
    statement = select(Subject).order_by(Subject.screening_no, Subject.id)
    if access.is_admin:
        return statement
    conditions = []
    if access.project_ids:
        conditions.append(Subject.project_id.in_(access.project_ids))
    if access.center_ids:
        conditions.append(Subject.center_id.in_(access.center_ids))
    if not conditions:
        return statement.where(False)
    return statement.where(or_(*conditions))


@router.get("/image-data", response_model=list[SubjectImageRowRead])
def list_image_data(
    db: DBSession,
    access: ImageReadAccess,
    project_id: int | None = None,
    center_id: int | None = None,
    image_type: str = "raw",
) -> list[SubjectImageRowRead]:
    if image_type not in IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid image type")
    statement = scoped_subject_statement(access)
    if project_id is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
        ensure_project_access(access, project_id)
        statement = statement.where(Subject.project_id == project_id)
    if center_id is not None:
        center = db.get(Center, center_id)
        if center is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="center not found")
        ensure_center_access(access, center)
        if project_id is not None and center.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="center does not belong to project",
            )
        statement = statement.where(Subject.center_id == center_id)
    subjects = list(db.scalars(statement))
    ensure_subjects_image_records(db, subjects)
    if subjects:
        db.commit()
    rows: list[SubjectImageRowRead] = []
    for subject in subjects:
        records = ensure_subject_image_records(db, subject)
        row_record = records[image_type]
        rows.append(
            SubjectImageRowRead(
                subject_id=subject.id,
                project_id=subject.project_id,
                center_id=subject.center_id,
                screening_no=subject.screening_no,
                subject_arm=subject.subject_arm,
                gender=subject.gender,
                age=subject.age,
                record=row_record,
                raw_record=records["raw"],
            )
        )
    return rows


@router.post("/image-data/{record_id}/upload", response_model=SubjectImageUploadRead)
def upload_image_record(
    record_id: int,
    db: DBSession,
    access: ImageReadAccess,
    request: Request,
    file: ImageUpload,
) -> SubjectImageUploadRead:
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    ensure_upload_permission(access, record)
    validate_upload_file(record, file)
    subject = db.get(Subject, record.subject_id)
    project = db.get(Project, record.project_id)
    center = db.get(Center, record.center_id)
    if subject is None or project is None or center is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="image record scope not found",
        )
    records = ensure_subject_image_records(db, subject)
    if record.image_type == "enhanced" and records["raw"].upload_status != IMAGE_UPLOAD_STATUS_DONE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw image data must be uploaded before enhanced image data",
        )

    next_version = record.version + 1
    target_dir = image_record_directory(project, center, subject, record.image_type, next_version)
    clear_landmark_index(db, record.subject_id)
    if record.image_type == "report":
        clear_report_image_index(db, record)
    clear_record_physical_files(record)
    stored = store_image_upload(file, target_dir)
    record.original_name = stored.original_name
    record.stored_name = stored.stored_name
    record.file_ext = stored.file_ext
    record.mime_type = stored.mime_type
    record.file_size = stored.file_size
    record.file_hash = stored.file_hash
    record.storage_path = stored.storage_path
    record.version = next_version
    record.upload_status = IMAGE_UPLOAD_STATUS_DONE
    record.uploaded_by = access.user.id
    record.uploaded_at = datetime.now(UTC)
    record.screening_no_snapshot = subject.screening_no
    record.parse_warning = None
    if record.image_type in {"raw", "enhanced"}:
        extract_dir = (target_dir / "extracted").as_posix()
        try:
            stats = analyze_and_extract_zip(stored.storage_path, extract_dir, subject.screening_no)
        except HTTPException:
            shutil.rmtree(
                ensure_relative_path(settings.file_storage_root, target_dir.as_posix()),
                ignore_errors=True,
            )
            reset_record_metadata(record)
            raise
        record.extracted_dir = stats.extracted_dir
        record.image_count = stats.image_count
        record.image_total_size = stats.image_total_size
        record.image_extensions_json = stats.image_extensions
        record.parse_warning = stats.parse_warning
    else:
        record.extracted_dir = None
        record.image_count = 0
        record.image_total_size = 0
        record.image_extensions_json = None
        rebuild_report_image_index(db, record, indexed_by=access.user.id)
    if record.image_type == "enhanced":
        record.source_raw_record_id = records["raw"].id
    landmark_result = maybe_rebuild_landmark_index(
        db,
        record.subject_id,
        indexed_by=access.user.id,
    )
    record_operation(
        db,
        action="image_data.upload",
        request=request,
        access=access,
        target_type="subject_image_record",
        target_id=record.id,
        project_id=record.project_id,
        center_id=record.center_id,
        detail={
            "image_type": record.image_type,
            "screening_no": subject.screening_no,
            "file_size": record.file_size,
            "image_count": record.image_count,
            "landmark_index_status": (
                landmark_result.index_status if landmark_result is not None else None
            ),
        },
    )
    db.commit()
    db.refresh(record)
    return SubjectImageUploadRead(record=record)


@router.post(
    "/image-data/{record_id}/report-images/index",
    response_model=ReportImageIndexResponse,
)
def index_report_images(
    record_id: int,
    db: DBSession,
    access: ImageReadAccess,
    request: Request,
) -> ReportImageIndexResponse:
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    if record.image_type != "report":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="record is not an electronic report",
        )
    ensure_upload_permission(access, record)
    if record.upload_status != IMAGE_UPLOAD_STATUS_DONE or record.storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="electronic report has not been uploaded",
        )

    clear_landmark_index(db, record.subject_id)
    result = rebuild_report_image_index(db, record, indexed_by=access.user.id)
    landmark_result = maybe_rebuild_landmark_index(
        db,
        record.subject_id,
        indexed_by=access.user.id,
    )
    record_operation(
        db,
        action="image_data.report_images.index",
        request=request,
        access=access,
        target_type="subject_image_record",
        target_id=record.id,
        project_id=record.project_id,
        center_id=record.center_id,
        detail={
            "screening_no": record.screening_no_snapshot,
            "report_version": result.report_version,
            "index_status": result.index_status,
            "indexed_image_count": len(result.evidence),
            "duplicate_count": result.duplicate_count,
            "landmark_index_status": (
                landmark_result.index_status if landmark_result is not None else None
            ),
        },
    )
    db.commit()
    return ReportImageIndexResponse(
        record_id=result.record_id,
        report_version=result.report_version,
        index_status=result.index_status,
        report_package_evidence_id=result.report_package.id,
        indexed_image_count=len(result.evidence),
        duplicate_count=result.duplicate_count,
        warning=result.warning,
        evidence=result.evidence,
    )


def landmark_response(result) -> LandmarkIndexResponse:
    return LandmarkIndexResponse(
        report_record_id=result.report_record_id,
        raw_record_id=result.raw_record_id,
        enhanced_record_id=result.enhanced_record_id,
        index_status=result.index_status,
        counts=landmark_counts(result.evidence),
        warning=result.warning,
        evidence=result.evidence,
    )


@router.post(
    "/image-data/{record_id}/landmarks/index",
    response_model=LandmarkIndexResponse,
)
def index_landmarks(
    record_id: int,
    db: DBSession,
    access: ImageEvidenceManageAccess,
    request: Request,
) -> LandmarkIndexResponse:
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    if record.image_type != "report":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="record is not an electronic report",
        )
    result = maybe_rebuild_landmark_index(
        db,
        record.subject_id,
        indexed_by=access.user.id,
    )
    if result is None:
        result = rebuild_landmark_index(db, record, indexed_by=access.user.id)
    record_operation(
        db,
        action="image_data.landmarks.index",
        request=request,
        access=access,
        target_type="subject_image_record",
        target_id=record.id,
        project_id=record.project_id,
        center_id=record.center_id,
        detail={
            "screening_no": record.screening_no_snapshot,
            "index_status": result.index_status,
            "counts": landmark_counts(result.evidence),
        },
    )
    db.commit()
    return landmark_response(result)


@router.get(
    "/image-data/{record_id}/landmarks",
    response_model=LandmarkIndexResponse,
)
def get_landmarks(
    record_id: int,
    db: DBSession,
    access: ImageReadAccess,
) -> LandmarkIndexResponse:
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    if record.image_type != "report":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="record is not an electronic report",
        )
    return landmark_response(landmark_index_state(db, record))


@router.post(
    "/image-evidence/{evidence_id}/confirm",
    response_model=LandmarkIndexResponse,
)
def confirm_landmark(
    evidence_id: int,
    payload: LandmarkConfirmRequest,
    db: DBSession,
    access: ImageEvidenceManageAccess,
    request: Request,
) -> LandmarkIndexResponse:
    evidence = db.get(ImageEvidenceIndex, evidence_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="image evidence not found",
        )
    ensure_record_scope(
        access,
        get_record_or_404(db, evidence.subject_image_record_id),
    )
    try:
        confirm_landmark_candidate(
            evidence,
            payload.candidate_key,
            confirmed_by=access.user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="candidate not found",
        ) from exc
    report_record_id = (evidence.payload_json or {}).get("report_record_id")
    report_record = (
        db.get(SubjectImageRecord, report_record_id)
        if isinstance(report_record_id, int)
        else None
    )
    if report_record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="landmark report source is missing",
        )
    record_operation(
        db,
        action="image_data.landmark.confirm",
        request=request,
        access=access,
        target_type="image_evidence_index",
        target_id=evidence.id,
        project_id=evidence.project_id,
        center_id=evidence.center_id,
        detail={"candidate_key": payload.candidate_key},
    )
    db.commit()
    db.refresh(evidence)
    return landmark_response(landmark_index_state(db, report_record))


@router.get("/image-evidence/{evidence_id}/preview")
def preview_image_evidence(
    evidence_id: int,
    db: DBSession,
    access: ImageReadAccess,
    variant: str = "raw",
) -> FileResponse:
    evidence = db.get(ImageEvidenceIndex, evidence_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="image evidence not found",
        )
    ensure_record_scope(
        access,
        get_record_or_404(db, evidence.subject_image_record_id),
    )
    payload = evidence.payload_json or {}
    relative_path: str | None = None
    if variant == "report":
        value = payload.get("report_relative_path")
        relative_path = value if isinstance(value, str) else evidence.relative_path
    elif variant == "enhanced":
        selected = payload.get("selected_candidate")
        if isinstance(selected, dict):
            value = selected.get("enhanced_relative_path")
            relative_path = value if isinstance(value, str) else None
    elif variant == "raw":
        relative_path = evidence.relative_path
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid preview variant",
        )
    if not relative_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="preview image not available",
        )
    try:
        path = ensure_relative_path(settings.file_storage_root, relative_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="preview image not found",
        ) from exc
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="preview image not found",
        )
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not media_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="evidence preview is not an image",
        )
    return FileResponse(path, media_type=media_type)


@router.get("/image-data/{record_id}/download")
def download_image_record(
    record_id: int,
    db: DBSession,
    access: ImageReadAccess,
    request: Request,
) -> FileResponse:
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    ensure_download_permission(access, record)
    if record.storage_path is None or record.original_name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not uploaded")
    path = image_record_file_path(record)
    record_operation(
        db,
        action="image_data.download",
        request=request,
        access=access,
        target_type="subject_image_record",
        target_id=record.id,
        project_id=record.project_id,
        center_id=record.center_id,
        detail={"image_type": record.image_type, "original_name": record.original_name},
    )
    db.commit()
    return FileResponse(path, media_type=record.mime_type, filename=record.original_name)


@router.get("/image-data/{record_id}/raw-copy")
def copy_raw_image_record(
    record_id: int,
    db: DBSession,
    access: ImageReadAccess,
    request: Request,
) -> FileResponse:
    if not access.has_permission("image_data:copy_raw"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    if record.image_type != "raw":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="record is not raw image data",
        )
    if record.storage_path is None or record.original_name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="raw image file not uploaded",
        )
    path = image_record_file_path(record)
    record.copied_by = access.user.id
    record.copied_at = datetime.now(UTC)
    record_operation(
        db,
        action="image_data.raw_copy",
        request=request,
        access=access,
        target_type="subject_image_record",
        target_id=record.id,
        project_id=record.project_id,
        center_id=record.center_id,
        detail={
            "screening_no": record.screening_no_snapshot,
            "original_name": record.original_name,
        },
    )
    db.commit()
    return FileResponse(path, media_type=record.mime_type, filename=record.original_name)


@router.delete("/image-data/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image_record(
    record_id: int,
    db: DBSession,
    access: Annotated[AccessContext, Depends(require_permission("image_data:delete"))],
    request: Request,
) -> None:
    record = get_record_or_404(db, record_id)
    ensure_record_scope(access, record)
    clear_landmark_index(db, record.subject_id)
    if record.image_type == "report":
        clear_report_image_index(db, record)
    clear_record_physical_files(record)
    record_operation(
        db,
        action="image_data.delete",
        request=request,
        access=access,
        target_type="subject_image_record",
        target_id=record.id,
        project_id=record.project_id,
        center_id=record.center_id,
        detail={"image_type": record.image_type, "screening_no": record.screening_no_snapshot},
    )
    reset_record_metadata(record)
    db.commit()


def image_record_file_path(record: SubjectImageRecord) -> Path:
    try:
        path = ensure_relative_path(settings.file_storage_root, record.storage_path or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found") from exc
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return path
