import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path
from app.models import ImageEvidenceIndex, SubjectImageRecord
from app.models.image_evidence import (
    IMAGE_EVIDENCE_REPORT_IMAGE,
    IMAGE_EVIDENCE_REPORT_PACKAGE,
)

REPORT_IMAGE_SOURCE = "embedded_pdf_image"
REPORT_PACKAGE_SOURCE = "electronic_report"
REPORT_IMAGE_INDEX_STATUSES = {"indexed", "empty", "not_supported", "failed"}
REPORT_IMAGE_SUPPORTED_EXTENSIONS = {"pdf"}

_MIME_BY_EXTENSION = {
    "bmp": "image/bmp",
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "jpx": "image/jp2",
    "png": "image/png",
    "pnm": "image/x-portable-anymap",
    "tiff": "image/tiff",
}


@dataclass(frozen=True)
class ReportImageIndexResult:
    record_id: int
    report_version: int
    index_status: str
    report_package: ImageEvidenceIndex
    evidence: list[ImageEvidenceIndex]
    duplicate_count: int
    warning: str | None


def report_image_evidence_directory(record: SubjectImageRecord) -> Path:
    storage_path = Path(record.storage_path or "")
    return storage_path.parent / "evidence" / "report_images"


def clear_report_image_index(db: Session, record: SubjectImageRecord) -> None:
    evidence_rows = list(
        db.scalars(
            select(ImageEvidenceIndex).where(
                ImageEvidenceIndex.subject_image_record_id == record.id,
                ImageEvidenceIndex.evidence_type.in_(
                    (IMAGE_EVIDENCE_REPORT_PACKAGE, IMAGE_EVIDENCE_REPORT_IMAGE)
                ),
            )
        )
    )
    for evidence in evidence_rows:
        db.delete(evidence)

    if record.storage_path:
        try:
            evidence_dir = ensure_relative_path(
                settings.file_storage_root,
                (Path(record.storage_path).parent / "evidence").as_posix(),
            )
            shutil.rmtree(evidence_dir, ignore_errors=True)
        except ValueError:
            pass


def _warning_for_status(index_status: str, error: str | None = None) -> str | None:
    if index_status == "empty":
        return "电子报告 PDF 未识别到内嵌图片"
    if index_status == "not_supported":
        return "当前版本仅支持 PDF 电子报告图片索引"
    if index_status == "failed":
        return f"电子报告图片索引失败：{error or '未知错误'}"
    return None


def _package_evidence(
    record: SubjectImageRecord,
    *,
    indexed_by: int | None,
    indexed_at: datetime,
    index_status: str,
    image_count: int,
    duplicate_count: int,
    warning: str | None,
) -> ImageEvidenceIndex:
    return ImageEvidenceIndex(
        project_id=record.project_id,
        center_id=record.center_id,
        subject_id=record.subject_id,
        subject_image_record_id=record.id,
        evidence_type=IMAGE_EVIDENCE_REPORT_PACKAGE,
        evidence_source=REPORT_PACKAGE_SOURCE,
        relative_path=record.storage_path,
        match_status=None,
        file_hash=record.file_hash,
        file_size=record.file_size,
        gastrointestinal_location=None,
        payload_json={
            "report_version": record.version,
            "original_name": record.original_name,
            "file_ext": record.file_ext,
            "mime_type": record.mime_type,
            "index_status": index_status,
            "indexed_image_count": image_count,
            "duplicate_count": duplicate_count,
            "warning": warning,
        },
        indexed_by=indexed_by,
        indexed_at=indexed_at,
    )


def _image_evidence(
    record: SubjectImageRecord,
    *,
    indexed_by: int | None,
    indexed_at: datetime,
    relative_path: str,
    file_hash: str,
    file_size: int,
    metadata: dict[str, Any],
) -> ImageEvidenceIndex:
    return ImageEvidenceIndex(
        project_id=record.project_id,
        center_id=record.center_id,
        subject_id=record.subject_id,
        subject_image_record_id=record.id,
        evidence_type=IMAGE_EVIDENCE_REPORT_IMAGE,
        evidence_source=REPORT_IMAGE_SOURCE,
        relative_path=relative_path,
        match_status=None,
        file_hash=file_hash,
        file_size=file_size,
        gastrointestinal_location=None,
        payload_json=metadata,
        indexed_by=indexed_by,
        indexed_at=indexed_at,
    )


def _extract_pdf_images(
    record: SubjectImageRecord,
) -> tuple[list[dict[str, Any]], int]:
    report_path = ensure_relative_path(settings.file_storage_root, record.storage_path or "")
    evidence_dir_relative = report_image_evidence_directory(record)
    evidence_dir = ensure_relative_path(
        settings.file_storage_root,
        evidence_dir_relative.as_posix(),
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)

    images_by_hash: dict[str, dict[str, Any]] = {}
    occurrence_count = 0
    with fitz.open(report_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = image_info[0]
                extracted = document.extract_image(xref)
                image_bytes = extracted["image"]
                file_hash = hashlib.sha256(image_bytes).hexdigest()
                occurrence = {
                    "page": page_index + 1,
                    "image_index": image_index,
                    "xref": xref,
                    "rects": [
                        {
                            "x0": rect.x0,
                            "y0": rect.y0,
                            "x1": rect.x1,
                            "y1": rect.y1,
                        }
                        for rect in page.get_image_rects(xref)
                    ],
                }
                occurrence_count += 1
                existing = images_by_hash.get(file_hash)
                if existing is not None:
                    existing["occurrences"].append(occurrence)
                    continue

                extension = str(extracted.get("ext") or "bin").lower()
                filename = (
                    f"page_{page_index + 1:04d}_image_{image_index:03d}_"
                    f"{file_hash[:12]}.{extension}"
                )
                relative_path = evidence_dir_relative / filename
                output_path = ensure_relative_path(
                    settings.file_storage_root,
                    relative_path.as_posix(),
                )
                output_path.write_bytes(image_bytes)
                images_by_hash[file_hash] = {
                    "relative_path": relative_path.as_posix(),
                    "file_hash": file_hash,
                    "file_size": len(image_bytes),
                    "metadata": {
                        "report_version": record.version,
                        "page": page_index + 1,
                        "image_index": image_index,
                        "xref": xref,
                        "width": extracted.get("width"),
                        "height": extracted.get("height"),
                        "extension": extension,
                        "mime_type": _MIME_BY_EXTENSION.get(
                            extension,
                            f"image/{extension}",
                        ),
                        "page_width": page.rect.width,
                        "page_height": page.rect.height,
                        "occurrences": [occurrence],
                    },
                    "occurrences": [occurrence],
                }

    for image in images_by_hash.values():
        image["metadata"]["occurrences"] = image.pop("occurrences")
    return list(images_by_hash.values()), occurrence_count - len(images_by_hash)


def rebuild_report_image_index(
    db: Session,
    record: SubjectImageRecord,
    *,
    indexed_by: int | None,
) -> ReportImageIndexResult:
    clear_report_image_index(db, record)
    indexed_at = datetime.now(UTC)
    index_status = "not_supported"
    warning: str | None = None
    extracted_images: list[dict[str, Any]] = []
    duplicate_count = 0

    file_ext = (record.file_ext or Path(record.original_name or "").suffix.lstrip(".")).lower()
    if file_ext in REPORT_IMAGE_SUPPORTED_EXTENSIONS:
        try:
            extracted_images, duplicate_count = _extract_pdf_images(record)
            index_status = "indexed" if extracted_images else "empty"
        except Exception as exc:
            index_status = "failed"
            warning = _warning_for_status(index_status, str(exc))
            try:
                evidence_dir = ensure_relative_path(
                    settings.file_storage_root,
                    report_image_evidence_directory(record).as_posix(),
                )
                shutil.rmtree(evidence_dir, ignore_errors=True)
            except ValueError:
                pass

    if warning is None:
        warning = _warning_for_status(index_status)
    record.parse_warning = warning

    evidence_rows = [
        _image_evidence(
            record,
            indexed_by=indexed_by,
            indexed_at=indexed_at,
            relative_path=image["relative_path"],
            file_hash=image["file_hash"],
            file_size=image["file_size"],
            metadata=image["metadata"],
        )
        for image in extracted_images
    ]
    package = _package_evidence(
        record,
        indexed_by=indexed_by,
        indexed_at=indexed_at,
        index_status=index_status,
        image_count=len(evidence_rows),
        duplicate_count=duplicate_count,
        warning=warning,
    )
    db.add(package)
    db.add_all(evidence_rows)
    db.flush()
    return ReportImageIndexResult(
        record_id=record.id,
        report_version=record.version,
        index_status=index_status,
        report_package=package,
        evidence=evidence_rows,
        duplicate_count=duplicate_count,
        warning=warning,
    )
