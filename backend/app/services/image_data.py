import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path, normalize_mime_type, safe_path_part
from app.models import Center, Project, Subject, SubjectImageRecord

IMAGE_TYPES = {"raw", "enhanced", "report"}
IMAGE_UPLOAD_STATUS_EMPTY = "not_uploaded"
IMAGE_UPLOAD_STATUS_DONE = "uploaded"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".dcm"}
REPORT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
ZIP_EXTENSIONS = {".zip"}


@dataclass(frozen=True)
class StoredImageUpload:
    original_name: str
    stored_name: str
    file_ext: str | None
    mime_type: str
    file_size: int
    file_hash: str
    storage_path: str


@dataclass(frozen=True)
class ImageArchiveStats:
    extracted_dir: str | None
    image_count: int
    image_total_size: int
    image_extensions: dict[str, int]
    parse_warning: str | None


def ensure_subject_image_records(db: Session, subject: Subject) -> dict[str, SubjectImageRecord]:
    existing = {
        record.image_type: record
        for record in db.scalars(
            select(SubjectImageRecord).where(SubjectImageRecord.subject_id == subject.id)
        )
    }
    for image_type in ("raw", "enhanced", "report"):
        record = existing.get(image_type)
        if record is None:
            record = SubjectImageRecord(
                project_id=subject.project_id,
                center_id=subject.center_id,
                subject_id=subject.id,
                image_type=image_type,
                screening_no_snapshot=subject.screening_no,
                upload_status=IMAGE_UPLOAD_STATUS_EMPTY,
            )
            db.add(record)
            db.flush()
            existing[image_type] = record
        else:
            record.project_id = subject.project_id
            record.center_id = subject.center_id
            record.screening_no_snapshot = subject.screening_no
    raw = existing["raw"]
    enhanced = existing["enhanced"]
    if enhanced.source_raw_record_id is None:
        enhanced.source_raw_record_id = raw.id
    return existing


def ensure_subjects_image_records(db: Session, subjects: list[Subject]) -> None:
    for subject in subjects:
        ensure_subject_image_records(db, subject)


def image_record_directory(
    project: Project,
    center: Center,
    subject: Subject,
    image_type: str,
    version: int,
) -> Path:
    return (
        Path("projects")
        / safe_path_part(project.code)
        / "centers"
        / safe_path_part(center.code)
        / "subjects"
        / safe_path_part(subject.screening_no)
        / "image_data"
        / image_type
        / f"v{version}"
    )


def store_image_upload(upload_file: UploadFile, target_dir: Path) -> StoredImageUpload:
    original_name = Path(upload_file.filename or "upload.bin").name
    suffix = Path(original_name).suffix.lower()
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
                    raise HTTPException(status_code=413, detail="file too large")
                hasher.update(chunk)
                output.write(chunk)
    finally:
        upload_file.file.close()
    return StoredImageUpload(
        original_name=original_name,
        stored_name=stored_name,
        file_ext=suffix.lstrip(".") or None,
        mime_type=normalize_mime_type(upload_file.content_type, original_name),
        file_size=size,
        file_hash=hasher.hexdigest(),
        storage_path=relative_path.as_posix(),
    )


def validate_upload_file(record: SubjectImageRecord, upload_file: UploadFile) -> None:
    suffix = Path(upload_file.filename or "").suffix.lower()
    if record.image_type in {"raw", "enhanced"} and suffix not in ZIP_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image data must be uploaded as a zip package",
        )
    if record.image_type == "report" and suffix not in REPORT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="report must be PDF, Word, or Excel",
        )


def analyze_and_extract_zip(
    zip_storage_path: str,
    extract_dir: str,
    screening_no: str,
) -> ImageArchiveStats:
    zip_path = ensure_relative_path(settings.file_storage_root, zip_storage_path)
    extract_path = ensure_relative_path(settings.file_storage_root, extract_dir)
    extract_path.mkdir(parents=True, exist_ok=True)
    image_count = 0
    image_total_size = 0
    extensions: dict[str, int] = {}
    warnings: list[str] = []
    top_level_names: set[str] = set()

    try:
        with zipfile.ZipFile(zip_path) as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                target_relative = safe_zip_member_path(item.filename)
                top_level = target_relative.parts[0] if target_relative.parts else ""
                if top_level:
                    top_level_names.add(top_level)
                suffix = Path(target_relative.name).suffix.lower()
                if suffix not in IMAGE_EXTENSIONS:
                    continue
                target_path = (extract_path / Path(*target_relative.parts)).resolve()
                if not target_path.is_relative_to(extract_path.resolve()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="zip contains unsafe path",
                    )
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target_path.open("wb") as output:
                    shutil.copyfileobj(source, output)
                image_count += 1
                image_total_size += item.file_size
                extensions[suffix.lstrip(".")] = extensions.get(suffix.lstrip("."), 0) + 1
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid zip package",
        ) from exc

    if len(top_level_names) == 1:
        only_root = next(iter(top_level_names))
        if only_root != screening_no:
            warnings.append(f"压缩包根目录 {only_root} 与试验序列号 {screening_no} 不一致")
    if image_count == 0:
        warnings.append("未识别到常见图片文件")
    return ImageArchiveStats(
        extracted_dir=extract_dir,
        image_count=image_count,
        image_total_size=image_total_size,
        image_extensions=extensions,
        parse_warning="；".join(warnings) if warnings else None,
    )


def safe_zip_member_path(filename: str) -> PurePosixPath:
    candidate = PurePosixPath(filename)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="zip contains unsafe path",
        )
    if not candidate.parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="zip contains empty path",
        )
    return candidate


def clear_record_physical_files(record: SubjectImageRecord) -> None:
    if record.storage_path:
        try:
            path = ensure_relative_path(settings.file_storage_root, record.storage_path)
            path.unlink(missing_ok=True)
        except ValueError:
            pass
    if record.extracted_dir:
        try:
            path = ensure_relative_path(settings.file_storage_root, record.extracted_dir)
            shutil.rmtree(path, ignore_errors=True)
        except ValueError:
            pass


def reset_record_metadata(record: SubjectImageRecord) -> None:
    record.original_name = None
    record.stored_name = None
    record.file_ext = None
    record.mime_type = None
    record.file_size = 0
    record.file_hash = None
    record.storage_path = None
    record.extracted_dir = None
    record.upload_status = IMAGE_UPLOAD_STATUS_EMPTY
    record.image_count = 0
    record.image_total_size = 0
    record.image_extensions_json = None
    record.parse_warning = None
    record.uploaded_by = None
    record.uploaded_at = None
