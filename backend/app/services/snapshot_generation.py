from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path, safe_path_part
from app.models import (
    Center,
    DocumentExtractedField,
    FileAsset,
    FileVersion,
    Project,
    Subject,
    SubjectImageRecord,
    SubjectItem,
    SubjectSection,
    SubjectSnapshot,
)
from app.models.subject_snapshot import (
    SUBJECT_SNAPSHOT_RELEASED,
    SUBJECT_SNAPSHOT_SCHEMA_VERSION,
)
from app.services.snapshot_precheck import SnapshotPrecheckResult, run_snapshot_precheck

SUBJECT_SNAPSHOT_STATUS_RELEASED = "released"


@dataclass(frozen=True)
class SnapshotGenerationResult:
    snapshot: SubjectSnapshot
    check_run_id: str
    storage_path: str
    file_hash: str
    file_size: int


class SnapshotPrecheckFailed(Exception):
    def __init__(self, result: SnapshotPrecheckResult) -> None:
        super().__init__("snapshot precheck failed")
        self.result = result


class SnapshotFileWriteError(Exception):
    pass


def generate_subject_snapshot(
    db: Session,
    subject: Subject,
    *,
    generated_by: int,
) -> SnapshotGenerationResult:
    precheck = run_snapshot_precheck(db, subject, snapshot_type=SUBJECT_SNAPSHOT_RELEASED)
    if not precheck.eligible:
        raise SnapshotPrecheckFailed(precheck)

    project = db.get(Project, subject.project_id)
    center = db.get(Center, subject.center_id)
    if project is None or center is None:
        raise SnapshotFileWriteError("project or center missing")

    snapshot_version = next_snapshot_version(db, subject.id)
    generated_at = datetime.now(UTC)
    snapshot = SubjectSnapshot(
        project_id=subject.project_id,
        center_id=subject.center_id,
        subject_id=subject.id,
        screening_no_snapshot=subject.screening_no,
        schema_version=SUBJECT_SNAPSHOT_SCHEMA_VERSION,
        snapshot_version=snapshot_version,
        snapshot_type=SUBJECT_SNAPSHOT_RELEASED,
        status=SUBJECT_SNAPSHOT_STATUS_RELEASED,
        generated_by=generated_by,
        generated_at=generated_at,
        locked_at=generated_at,
    )
    db.add(snapshot)
    db.flush()

    payload = build_snapshot_payload(
        db,
        subject=subject,
        project=project,
        center=center,
        snapshot=snapshot,
        generated_at=generated_at,
        precheck=precheck,
    )
    storage_path = snapshot_storage_path(project, center, subject, snapshot_version)
    destination = ensure_relative_path(settings.file_storage_root, storage_path)

    try:
        file_hash, file_size = write_snapshot_json(destination, payload)
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise SnapshotFileWriteError(str(exc)) from exc

    snapshot.storage_path = storage_path
    snapshot.file_hash = file_hash
    snapshot.file_size = file_size
    for check in precheck.checks:
        check.snapshot_id = snapshot.id
    db.flush()

    return SnapshotGenerationResult(
        snapshot=snapshot,
        check_run_id=precheck.check_run_id,
        storage_path=storage_path,
        file_hash=file_hash,
        file_size=file_size,
    )


def next_snapshot_version(db: Session, subject_id: int) -> int:
    current_max = db.scalar(
        select(func.max(SubjectSnapshot.snapshot_version)).where(
            SubjectSnapshot.subject_id == subject_id
        )
    )
    return int(current_max or 0) + 1


def snapshot_storage_path(
    project: Project,
    center: Center,
    subject: Subject,
    snapshot_version: int,
) -> str:
    return (
        Path("projects")
        / safe_path_part(project.code)
        / "centers"
        / safe_path_part(center.code)
        / "subjects"
        / safe_path_part(subject.screening_no)
        / "snapshots"
        / f"v{snapshot_version}"
        / f"subject_snapshot_v{snapshot_version}.json"
    ).as_posix()


def write_snapshot_json(destination: Path, payload: dict[str, Any]) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    destination.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def build_snapshot_payload(
    db: Session,
    *,
    subject: Subject,
    project: Project,
    center: Center,
    snapshot: SubjectSnapshot,
    generated_at: datetime,
    precheck: SnapshotPrecheckResult,
) -> dict[str, Any]:
    sections = list(
        db.scalars(
            select(SubjectSection)
            .where(SubjectSection.subject_id == subject.id)
            .order_by(SubjectSection.sort_order, SubjectSection.id)
        )
    )
    items = list(
        db.scalars(
            select(SubjectItem)
            .where(SubjectItem.subject_id == subject.id)
            .order_by(SubjectItem.sort_order, SubjectItem.id)
        )
    )
    documents = latest_documents_for_subject(db, subject)
    fields = latest_fields_for_documents(db, documents)
    image_records = list(
        db.scalars(
            select(SubjectImageRecord)
            .where(SubjectImageRecord.subject_id == subject.id)
            .order_by(SubjectImageRecord.image_type)
        )
    )

    return {
        "schema_version": SUBJECT_SNAPSHOT_SCHEMA_VERSION,
        "generated_at": isoformat(generated_at),
        "snapshot_id": snapshot.id,
        "snapshot_type": snapshot.snapshot_type,
        "project": project_payload(project),
        "center": center_payload(center),
        "subject": subject_payload(subject),
        "clinical_tree": clinical_tree_payload(sections, items, documents),
        "fields_index": fields_index_payload(fields, documents),
        "images_index": images_index_payload(image_records),
        "source_documents": source_documents_payload(documents),
        "algorithm_runs": [],
        "quality_summary": quality_summary_payload(precheck),
    }


def latest_documents_for_subject(
    db: Session,
    subject: Subject,
) -> list[tuple[FileAsset, FileVersion]]:
    assets = list(
        db.scalars(
            select(FileAsset)
            .where(
                FileAsset.subject_id == subject.id,
                FileAsset.subject_item_id.is_not(None),
                FileAsset.status == "active",
            )
            .order_by(FileAsset.id)
        )
    )
    documents: list[tuple[FileAsset, FileVersion]] = []
    for asset in assets:
        version = db.scalar(
            select(FileVersion).where(
                FileVersion.file_id == asset.id,
                FileVersion.version == asset.version,
            )
        )
        if version is not None:
            documents.append((asset, version))
    return documents


def latest_fields_for_documents(
    db: Session,
    documents: list[tuple[FileAsset, FileVersion]],
) -> list[DocumentExtractedField]:
    version_ids = [version.id for _, version in documents]
    if not version_ids:
        return []
    return list(
        db.scalars(
            select(DocumentExtractedField)
            .where(DocumentExtractedField.file_version_id.in_(version_ids))
            .order_by(DocumentExtractedField.field_key, DocumentExtractedField.id)
        )
    )


def project_payload(project: Project) -> dict[str, Any]:
    return {"id": project.id, "code": project.code, "name": project.name}


def center_payload(center: Center) -> dict[str, Any]:
    return {"id": center.id, "code": center.code, "name": center.name}


def subject_payload(subject: Subject) -> dict[str, Any]:
    return {
        "id": subject.id,
        "screening_no": subject.screening_no,
        "subject_arm": subject.subject_arm,
        "gender": subject.gender,
        "age": subject.age,
        "enrolled_at": isoformat(subject.enrolled_at),
        "informed_at": isoformat(subject.informed_at),
        "visit_dates": {
            "visit1_date": isoformat(subject.visit1_date),
            "visit2_date": isoformat(subject.visit2_date),
            "visit3_date": isoformat(subject.visit3_date),
            "visit4_date": isoformat(subject.visit4_date),
            "visit5_date": isoformat(subject.visit5_date),
        },
        "data_status": subject.data_status,
        "review_status": subject.review_status,
    }


def clinical_tree_payload(
    sections: list[SubjectSection],
    items: list[SubjectItem],
    documents: list[tuple[FileAsset, FileVersion]],
) -> list[dict[str, Any]]:
    items_by_section: dict[int, list[SubjectItem]] = {}
    for item in items:
        items_by_section.setdefault(item.section_id, []).append(item)
    documents_by_item: dict[int, list[dict[str, Any]]] = {}
    for asset, version in documents:
        if asset.subject_item_id is None:
            continue
        documents_by_item.setdefault(asset.subject_item_id, []).append(
            {
                "file_id": asset.id,
                "file_version_id": version.id,
                "version": version.version,
                "original_name": version.original_name,
            }
        )

    tree: list[dict[str, Any]] = []
    for section in sections:
        tree.append(
            {
                "section_id": section.id,
                "section_code": section.section_code,
                "name": section.name,
                "visit_name": section.visit_name,
                "time_window": section.time_window,
                "sort_order": section.sort_order,
                "items": [
                    {
                        "subject_item_id": item.id,
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "required": item.required,
                        "upload_status": item.upload_status,
                        "review_status": item.review_status,
                        "sort_order": item.sort_order,
                        "source_documents": documents_by_item.get(item.id, []),
                    }
                    for item in items_by_section.get(section.id, [])
                ],
            }
        )
    return tree


def fields_index_payload(
    fields: list[DocumentExtractedField],
    documents: list[tuple[FileAsset, FileVersion]],
) -> dict[str, list[dict[str, Any]]]:
    asset_by_version = {version.id: asset for asset, version in documents}
    index: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        asset = asset_by_version.get(field.file_version_id)
        entry = {
            "field_id": field.id,
            "document_type": field.document_type,
            "field_key": field.field_key,
            "field_label": field.field_label,
            "value_type": field.value_type,
            "raw_value": field.raw_value,
            "normalized_value": field.normalized_value,
            "status": field.status,
            "confidence": field.confidence,
            "source": {
                "file_id": asset.id if asset else None,
                "file_version_id": field.file_version_id,
                "subject_item_id": asset.subject_item_id if asset else None,
                "source_page_no": field.source_page_no,
                "source_text": field.source_text,
            },
            "manually_edited": field.manually_edited,
            "confirmed_by": field.confirmed_by,
            "confirmed_at": isoformat(field.confirmed_at),
        }
        index.setdefault(field.field_key, []).append(entry)
    return index


def images_index_payload(image_records: list[SubjectImageRecord]) -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for record in image_records:
        if record.image_type not in {"raw", "enhanced", "report"}:
            continue
        payload[record.image_type] = {
            "record_id": record.id,
            "upload_status": record.upload_status,
            "package": {
                "original_name": record.original_name,
                "storage_path": record.storage_path,
                "file_hash": record.file_hash,
                "file_size": record.file_size,
                "mime_type": record.mime_type,
                "version": record.version,
            },
            "extracted_dir": record.extracted_dir,
            "image_count": record.image_count,
            "image_total_size": record.image_total_size,
            "extensions": record.image_extensions_json or {},
            "parse_warning": record.parse_warning,
            "source_raw_record_id": record.source_raw_record_id,
        }
    return payload


def source_documents_payload(
    documents: list[tuple[FileAsset, FileVersion]],
) -> list[dict[str, Any]]:
    return [
        {
            "file_id": asset.id,
            "file_uuid": asset.file_id,
            "file_version_id": version.id,
            "version": version.version,
            "subject_item_id": asset.subject_item_id,
            "file_category": asset.file_category,
            "original_name": version.original_name,
            "mime_type": version.mime_type,
            "file_hash": version.file_hash,
            "file_size": version.file_size,
            "storage_path": version.storage_path,
            "uploaded_at": isoformat(version.uploaded_at),
            "source_pdf_packet_id": asset.source_pdf_packet_id,
            "source_page_start": asset.source_page_start,
            "source_page_end": asset.source_page_end,
        }
        for asset, version in documents
    ]


def quality_summary_payload(precheck: SnapshotPrecheckResult) -> dict[str, Any]:
    return {
        "check_run_id": precheck.check_run_id,
        "eligible": precheck.eligible,
        "blocking_failure_count": precheck.blocking_failure_count,
        "warning_count": precheck.warning_count,
        "checks": [
            {
                "check_code": check.check_code,
                "check_status": check.check_status,
                "blocking": check.blocking,
                "message": check.message,
                "payload": check.payload_json,
            }
            for check in precheck.checks
        ],
    }


def isoformat(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
