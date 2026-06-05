import hashlib
import mimetypes
from pathlib import Path
from typing import Annotated, TypeVar
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
from starlette.responses import FileResponse

from app.api.deps import AccessContext, require_permission
from app.core.clinical_data import (
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
    UPLOAD_REPLACED,
    UPLOAD_UPLOADED,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.files import (
    CATEGORY_FOLDERS,
    FILE_CATEGORIES,
    StoredUpload,
    ensure_relative_path,
    normalize_mime_type,
    preview_media_type,
    safe_path_part,
)
from app.models import (
    Center,
    ClinicalSsuProgress,
    DocumentExtractedField,
    FileAsset,
    FileVersion,
    Project,
    Stage,
    StageFile,
    Subject,
    SubjectItem,
)
from app.schemas import FileRead, FileVersionRead
from app.schemas.document_field import DocumentExtractedFieldRead, DocumentExtractedFieldUpdate
from app.services.audit import record_operation
from app.services.clinical_status import recalculate_subject_status, reset_stage_file_status
from app.services.document_fields import (
    analyze_file_version_fields,
    latest_file_version,
    sync_subject_item_after_fields,
    update_field,
)

router = APIRouter()
ModelT = TypeVar(
    "ModelT",
    FileAsset,
    FileVersion,
    DocumentExtractedField,
    Project,
    Center,
    Stage,
    StageFile,
    ClinicalSsuProgress,
    Subject,
    SubjectItem,
)
DBSession = Annotated[Session, Depends(get_db)]
FileReadAccess = Annotated[AccessContext, Depends(require_permission("files:read"))]
FileWriteAccess = Annotated[AccessContext, Depends(require_permission("files:write"))]
FileDeleteAccess = Annotated[AccessContext, Depends(require_permission("files:delete"))]


def get_or_404(db: Session, model: type[ModelT], item_id: int, label: str) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return item


def ensure_file_scope(access: AccessContext, file_asset: FileAsset) -> None:
    if not access.can_access_center(file_asset.center_id, file_asset.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File scope denied")


def ensure_project_file_scope(access: AccessContext, project_id: int, center_id: int) -> None:
    if not access.can_access_center(center_id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File scope denied")


def ensure_category(file_category: str) -> str:
    if file_category not in FILE_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid file category")
    return file_category


def resolve_binding(
    db: Session,
    access: AccessContext,
    stage_file_id: int | None,
    subject_item_id: int | None,
    ssu_progress_id: int | None = None,
) -> dict[
    str,
    int | None | Project | Center | Stage | StageFile | ClinicalSsuProgress | Subject | SubjectItem,
]:
    binding_count = sum(
        1
        for value in (stage_file_id, subject_item_id, ssu_progress_id)
        if value is not None
    )
    if binding_count != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage_file_id, subject_item_id and ssu_progress_id are mutually exclusive and one is required",
        )

    if stage_file_id is not None:
        stage_file = get_or_404(db, StageFile, stage_file_id, "stage file")
        ensure_project_file_scope(access, stage_file.project_id, stage_file.center_id)
        project = get_or_404(db, Project, stage_file.project_id, "project")
        center = get_or_404(db, Center, stage_file.center_id, "center")
        stage = get_or_404(db, Stage, stage_file.stage_id, "stage")
        return {
            "project": project,
            "center": center,
            "stage": stage,
            "stage_file": stage_file,
            "subject": None,
            "subject_item": None,
            "project_id": project.id,
            "center_id": center.id,
            "stage_id": stage.id,
            "stage_file_id": stage_file.id,
            "ssu_progress_id": None,
            "subject_id": None,
            "subject_item_id": None,
        }

    if ssu_progress_id is not None:
        ssu_progress = get_or_404(db, ClinicalSsuProgress, ssu_progress_id, "SSU progress")
        ensure_project_file_scope(access, ssu_progress.project_id, ssu_progress.center_id)
        project = get_or_404(db, Project, ssu_progress.project_id, "project")
        center = get_or_404(db, Center, ssu_progress.center_id, "center")
        return {
            "project": project,
            "center": center,
            "stage": None,
            "stage_file": None,
            "ssu_progress": ssu_progress,
            "subject": None,
            "subject_item": None,
            "project_id": project.id,
            "center_id": center.id,
            "stage_id": None,
            "stage_file_id": None,
            "ssu_progress_id": ssu_progress.id,
            "subject_id": None,
            "subject_item_id": None,
        }

    subject_item = get_or_404(db, SubjectItem, subject_item_id or 0, "subject item")
    subject = get_or_404(db, Subject, subject_item.subject_id, "subject")
    ensure_project_file_scope(access, subject.project_id, subject.center_id)
    project = get_or_404(db, Project, subject.project_id, "project")
    center = get_or_404(db, Center, subject.center_id, "center")
    return {
        "project": project,
        "center": center,
        "stage": None,
        "stage_file": None,
        "ssu_progress": None,
        "subject": subject,
        "subject_item": subject_item,
        "project_id": project.id,
        "center_id": center.id,
        "stage_id": None,
        "stage_file_id": None,
        "ssu_progress_id": None,
        "subject_id": subject.id,
        "subject_item_id": subject_item.id,
    }


def relative_directory(
    binding: dict[
        str,
        int | None | Project | Center | Stage | StageFile | ClinicalSsuProgress | Subject | SubjectItem,
    ],
    file_category: str,
    version: int,
) -> Path:
    project = binding["project"]
    center = binding["center"]
    if not isinstance(project, Project) or not isinstance(center, Center):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="invalid binding",
        )
    base = Path("projects") / safe_path_part(project.code) / "centers" / safe_path_part(center.code)

    stage_file = binding["stage_file"]
    if isinstance(stage_file, StageFile):
        stage = binding["stage"]
        if not isinstance(stage, Stage):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="invalid stage binding",
            )
        return (
            base
            / "stage_files"
            / safe_path_part(stage.code)
            / str(stage_file.id)
            / f"v{version}"
        )

    ssu_progress = binding.get("ssu_progress")
    if isinstance(ssu_progress, ClinicalSsuProgress):
        return (
            base
            / "ssu_progress"
            / safe_path_part(ssu_progress.stage_code)
            / str(ssu_progress.id)
            / f"v{version}"
        )

    subject = binding["subject"]
    subject_item = binding["subject_item"]
    if not isinstance(subject, Subject) or not isinstance(subject_item, SubjectItem):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="invalid binding",
        )
    return (
        base
        / "subjects"
        / safe_path_part(subject.screening_no)
        / CATEGORY_FOLDERS[file_category]
        / safe_path_part(subject_item.item_code)
        / f"v{version}"
    )


def write_upload(upload_file: UploadFile, target_dir: Path) -> StoredUpload:
    original_name = Path(upload_file.filename or "upload.bin").name
    suffix = Path(original_name).suffix.lower()
    file_ext = suffix.lstrip(".") or None
    stored_name = f"{uuid4().hex}{suffix}"
    relative_path = target_dir / stored_name
    destination = ensure_relative_path(settings.file_storage_root, relative_path.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)

    max_size = settings.max_upload_size_mb * 1024 * 1024
    hasher = hashlib.sha256()
    size = 0
    try:
        upload_file.file.seek(0)
        with destination.open("wb") as output:
            while chunk := upload_file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail="file too large",
                    )
                hasher.update(chunk)
                output.write(chunk)
    finally:
        upload_file.file.close()

    mime_type = normalize_mime_type(
        upload_file.content_type or mimetypes.guess_type(original_name)[0],
        original_name,
    )
    return StoredUpload(
        original_name=original_name,
        stored_name=stored_name,
        file_ext=file_ext,
        mime_type=mime_type,
        file_size=size,
        file_hash=hasher.hexdigest(),
        storage_path=relative_path.as_posix(),
    )


def mark_binding_file_changed(
    db: Session,
    binding: dict[
        str,
        int | None | Project | Center | Stage | StageFile | ClinicalSsuProgress | Subject | SubjectItem,
    ],
    upload_status: str,
) -> None:
    stage_file = binding["stage_file"]
    if isinstance(stage_file, StageFile):
        stage_file.upload_status = upload_status
        stage_file.review_status = DEFAULT_REVIEW_STATUS
        stage_file.not_applicable = False
        stage_file.not_applicable_reason = None
        stage_file.not_applicable_by = None
        stage_file.not_applicable_at = None
        return

    subject_item = binding["subject_item"]
    subject = binding["subject"]
    if isinstance(subject_item, SubjectItem) and isinstance(subject, Subject):
        subject_item.upload_status = upload_status
        subject_item.review_status = DEFAULT_REVIEW_STATUS
        recalculate_subject_status(db, subject)


def ensure_ssu_pdf_upload(binding: dict[str, object], upload_file: UploadFile) -> None:
    if not isinstance(binding.get("ssu_progress"), ClinicalSsuProgress):
        return
    original_name = Path(upload_file.filename or "").name
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSU files only support PDF uploads",
        )


def has_remaining_bound_files(db: Session, file_asset: FileAsset) -> bool:
    statement = select(FileAsset).where(FileAsset.id != file_asset.id)
    if file_asset.stage_file_id is not None:
        statement = statement.where(FileAsset.stage_file_id == file_asset.stage_file_id)
    elif file_asset.subject_item_id is not None:
        statement = statement.where(FileAsset.subject_item_id == file_asset.subject_item_id)
    else:
        return False
    return db.scalar(statement.limit(1)) is not None


def reset_binding_if_empty(db: Session, file_asset: FileAsset) -> None:
    if has_remaining_bound_files(db, file_asset):
        return
    if file_asset.stage_file_id is not None:
        stage_file = db.get(StageFile, file_asset.stage_file_id)
        if stage_file is not None:
            reset_stage_file_status(stage_file)
        return
    if file_asset.subject_item_id is not None:
        subject_item = db.get(SubjectItem, file_asset.subject_item_id)
        if subject_item is None:
            return
        subject = db.get(Subject, subject_item.subject_id)
        subject_item.upload_status = DEFAULT_UPLOAD_STATUS
        subject_item.review_status = DEFAULT_REVIEW_STATUS
        if subject is not None:
            recalculate_subject_status(db, subject)


def resolve_version_path(db: Session, file_asset: FileAsset, version: int | None) -> FileVersion:
    target_version = version or file_asset.version
    file_version = db.scalar(
        select(FileVersion).where(
            FileVersion.file_id == file_asset.id,
            FileVersion.version == target_version,
        )
    )
    if file_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file version not found")
    return file_version


def remove_physical_files(file_asset: FileAsset) -> None:
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


@router.get("/files", response_model=list[FileRead])
def list_files(
    db: DBSession,
    access: FileReadAccess,
    project_id: int | None = None,
    center_id: int | None = None,
    subject_id: int | None = None,
    stage_file_id: int | None = None,
    ssu_progress_id: int | None = None,
    subject_item_id: int | None = None,
    file_category: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[FileAsset]:
    binding_count = sum(
        1
        for value in (stage_file_id, subject_item_id, ssu_progress_id)
        if value is not None
    )
    if binding_count > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="stage_file_id, subject_item_id and ssu_progress_id are mutually exclusive",
        )

    statement = select(FileAsset).order_by(FileAsset.uploaded_at.desc(), FileAsset.id.desc())
    if not access.is_admin:
        conditions = []
        if access.project_ids:
            conditions.append(FileAsset.project_id.in_(access.project_ids))
        if access.center_ids:
            conditions.append(FileAsset.center_id.in_(access.center_ids))
        if not conditions:
            return []
        statement = statement.where(or_(*conditions))
    if project_id is not None:
        ensure_project_file_scope(access, project_id, center_id or -1) if center_id else None
        statement = statement.where(FileAsset.project_id == project_id)
    if center_id is not None:
        if project_id is not None:
            ensure_project_file_scope(access, project_id, center_id)
        statement = statement.where(FileAsset.center_id == center_id)
    if subject_id is not None:
        statement = statement.where(FileAsset.subject_id == subject_id)
    if stage_file_id is not None:
        statement = statement.where(FileAsset.stage_file_id == stage_file_id)
    if ssu_progress_id is not None:
        statement = statement.where(FileAsset.ssu_progress_id == ssu_progress_id)
    if subject_item_id is not None:
        statement = statement.where(FileAsset.subject_item_id == subject_item_id)
    if file_category is not None:
        statement = statement.where(FileAsset.file_category == file_category)
    if status_filter is not None:
        statement = statement.where(FileAsset.status == status_filter)
    return list(db.scalars(statement))


@router.post("/files/upload", response_model=FileRead, status_code=status.HTTP_201_CREATED)
def upload_file(
    db: DBSession,
    access: FileWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
    file_category: Annotated[str, Form()],
    stage_file_id: Annotated[int | None, Form()] = None,
    ssu_progress_id: Annotated[int | None, Form()] = None,
    subject_item_id: Annotated[int | None, Form()] = None,
    change_note: Annotated[str | None, Form()] = None,
) -> FileAsset:
    category = ensure_category(file_category)
    binding = resolve_binding(db, access, stage_file_id, subject_item_id, ssu_progress_id)
    if isinstance(binding.get("ssu_progress"), ClinicalSsuProgress) and category != "ssu_document":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSU files must use ssu_document category",
        )
    ensure_ssu_pdf_upload(binding, file)
    stored = write_upload(file, relative_directory(binding, category, version=1))
    file_asset = FileAsset(
        file_id=str(uuid4()),
        original_name=stored.original_name,
        stored_name=stored.stored_name,
        file_ext=stored.file_ext,
        mime_type=stored.mime_type,
        file_size=stored.file_size,
        file_hash=stored.file_hash,
        storage_path=stored.storage_path,
        storage_type="local",
        project_id=int(binding["project_id"] or 0),
        center_id=int(binding["center_id"] or 0),
        subject_id=binding["subject_id"] if isinstance(binding["subject_id"], int) else None,
        stage_id=binding["stage_id"] if isinstance(binding["stage_id"], int) else None,
        stage_file_id=(
            binding["stage_file_id"] if isinstance(binding["stage_file_id"], int) else None
        ),
        ssu_progress_id=(
            binding["ssu_progress_id"] if isinstance(binding["ssu_progress_id"], int) else None
        ),
        subject_item_id=(
            binding["subject_item_id"] if isinstance(binding["subject_item_id"], int) else None
        ),
        file_category=category,
        version=1,
        uploaded_by=access.user.id,
        status="active",
    )
    db.add(file_asset)
    db.flush()
    db.add(
        file_version := FileVersion(
            file_id=file_asset.id,
            version=1,
            storage_path=stored.storage_path,
            file_hash=stored.file_hash,
            file_size=stored.file_size,
            mime_type=stored.mime_type,
            original_name=stored.original_name,
            stored_name=stored.stored_name,
            uploaded_by=access.user.id,
            change_note=change_note,
        )
    )
    mark_binding_file_changed(db, binding, UPLOAD_UPLOADED)
    analyze_file_version_fields(db, file_asset, file_version)
    sync_subject_item_after_fields(db, file_asset, user_id=access.user.id, file_version=file_version)
    record_operation(
        db,
        action="file.upload",
        request=request,
        access=access,
        target_type="file",
        target_id=file_asset.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        detail={
            "original_name": file_asset.original_name,
            "file_category": file_asset.file_category,
            "file_size": file_asset.file_size,
            "stage_file_id": file_asset.stage_file_id,
            "ssu_progress_id": file_asset.ssu_progress_id,
            "subject_item_id": file_asset.subject_item_id,
        },
    )
    db.commit()
    db.refresh(file_asset)
    return file_asset


@router.get("/files/{file_id}", response_model=FileRead)
def get_file(file_id: int, db: DBSession, access: FileReadAccess) -> FileAsset:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    return file_asset


@router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    db: DBSession,
    access: FileReadAccess,
    request: Request,
    version: int | None = None,
) -> FileResponse:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = resolve_version_path(db, file_asset, version)
    try:
        path = ensure_relative_path(settings.file_storage_root, file_version.storage_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found") from exc
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    record_operation(
        db,
        action="file.download",
        request=request,
        access=access,
        target_type="file",
        target_id=file_asset.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        detail={
            "original_name": file_version.original_name,
            "version": file_version.version,
            "file_size": file_version.file_size,
        },
    )
    db.commit()
    return FileResponse(
        path,
        media_type=file_version.mime_type,
        filename=file_version.original_name,
    )


@router.get("/files/{file_id}/preview")
def preview_file(
    file_id: int,
    db: DBSession,
    access: FileReadAccess,
    version: int | None = None,
) -> FileResponse:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = resolve_version_path(db, file_asset, version)
    media_type = preview_media_type(file_version.mime_type, file_version.original_name)
    if media_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="preview unsupported",
        )
    try:
        path = ensure_relative_path(settings.file_storage_root, file_version.storage_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found") from exc
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    return FileResponse(
        path,
        media_type=media_type,
        filename=file_version.original_name,
        content_disposition_type="inline",
    )


@router.post("/files/{file_id}/replace", response_model=FileRead)
def replace_file(
    file_id: int,
    db: DBSession,
    access: FileWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
    change_note: Annotated[str | None, Form()] = None,
) -> FileAsset:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    binding = resolve_binding(
        db,
        access,
        file_asset.stage_file_id,
        file_asset.subject_item_id,
        file_asset.ssu_progress_id,
    )
    ensure_ssu_pdf_upload(binding, file)
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
    db.add(
        file_version := FileVersion(
            file_id=file_asset.id,
            version=next_version,
            storage_path=stored.storage_path,
            file_hash=stored.file_hash,
            file_size=stored.file_size,
            mime_type=stored.mime_type,
            original_name=stored.original_name,
            stored_name=stored.stored_name,
            uploaded_by=access.user.id,
            change_note=change_note,
        )
    )
    mark_binding_file_changed(db, binding, UPLOAD_REPLACED)
    analyze_file_version_fields(db, file_asset, file_version)
    sync_subject_item_after_fields(db, file_asset, user_id=access.user.id, file_version=file_version)
    record_operation(
        db,
        action="file.replace",
        request=request,
        access=access,
        target_type="file",
        target_id=file_asset.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        detail={
            "original_name": file_asset.original_name,
            "version": file_asset.version,
            "file_size": file_asset.file_size,
            "change_note": change_note,
        },
    )
    db.commit()
    db.refresh(file_asset)
    return file_asset


@router.get("/files/{file_id}/versions", response_model=list[FileVersionRead])
def list_file_versions(
    file_id: int,
    db: DBSession,
    access: FileReadAccess,
) -> list[FileVersion]:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    return list(
        db.scalars(
            select(FileVersion)
            .where(FileVersion.file_id == file_asset.id)
            .order_by(FileVersion.version)
        )
    )


@router.get(
    "/files/{file_id}/extracted-fields",
    response_model=list[DocumentExtractedFieldRead],
)
def list_file_extracted_fields(
    file_id: int,
    db: DBSession,
    access: FileReadAccess,
    version: int | None = None,
) -> list[DocumentExtractedField]:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = latest_file_version(db, file_asset, version)
    fields = analyze_file_version_fields(db, file_asset, file_version)
    db.commit()
    return fields


@router.post(
    "/files/{file_id}/extracted-fields/analyze",
    response_model=list[DocumentExtractedFieldRead],
)
def analyze_file_extracted_fields(
    file_id: int,
    db: DBSession,
    access: FileWriteAccess,
    request: Request,
    version: int | None = None,
    force: bool = False,
) -> list[DocumentExtractedField]:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    file_version = latest_file_version(db, file_asset, version)
    fields = analyze_file_version_fields(db, file_asset, file_version, force=force)
    sync_subject_item_after_fields(db, file_asset, user_id=access.user.id)
    record_operation(
        db,
        action="file.extracted_fields_analyze",
        request=request,
        access=access,
        target_type="file",
        target_id=file_asset.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        detail={"version": file_version.version, "field_count": len(fields), "force": force},
    )
    db.commit()
    return fields


@router.patch(
    "/files/{file_id}/extracted-fields/{field_id}",
    response_model=DocumentExtractedFieldRead,
)
def update_file_extracted_field(
    file_id: int,
    field_id: int,
    payload: DocumentExtractedFieldUpdate,
    db: DBSession,
    access: FileWriteAccess,
    request: Request,
) -> DocumentExtractedField:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    field = get_or_404(db, DocumentExtractedField, field_id, "extracted field")
    version_ids = {version.id for version in file_asset.versions}
    if field.file_version_id not in version_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="extracted field not found")
    update_field(
        db,
        field,
        raw_value=payload.raw_value,
        normalized_value=payload.normalized_value,
        status_value=payload.status,
        user_id=access.user.id,
    )
    sync_subject_item_after_fields(db, file_asset, user_id=access.user.id)
    record_operation(
        db,
        action="file.extracted_field_update",
        request=request,
        access=access,
        target_type="document_extracted_field",
        target_id=field.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        detail={"file_id": file_asset.id, "field_key": field.field_key, "status": field.status},
    )
    db.commit()
    db.refresh(field)
    return field


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: int, db: DBSession, access: FileDeleteAccess, request: Request) -> None:
    file_asset = get_or_404(db, FileAsset, file_id, "file")
    ensure_file_scope(access, file_asset)
    record_operation(
        db,
        action="file.delete",
        request=request,
        access=access,
        target_type="file",
        target_id=file_asset.id,
        project_id=file_asset.project_id,
        center_id=file_asset.center_id,
        detail={
            "original_name": file_asset.original_name,
            "version": file_asset.version,
            "file_category": file_asset.file_category,
        },
    )
    reset_binding_if_empty(db, file_asset)
    remove_physical_files(file_asset)
    db.delete(file_asset)
    db.commit()
