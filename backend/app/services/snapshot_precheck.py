from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import REVIEW_APPROVED, UPLOADED_STATUSES
from app.models import (
    DocumentExtractedField,
    FileAsset,
    FileVersion,
    SnapshotQualityCheck,
    Subject,
    SubjectImageRecord,
    SubjectItem,
    SubjectSection,
)
from app.models.snapshot_quality_check import (
    SNAPSHOT_CHECK_FAIL,
    SNAPSHOT_CHECK_NOT_SUPPORTED,
    SNAPSHOT_CHECK_PASS,
    SNAPSHOT_CHECK_WARN,
)
from app.models.subject_snapshot import (
    SUBJECT_SNAPSHOT_RELEASED,
    SUBJECT_SNAPSHOT_SCHEMA_VERSION,
)
from app.services.document_fields import FIELD_STATUS_NEEDS_INPUT, LOW_CONFIDENCE_THRESHOLD
from app.services.image_data import IMAGE_UPLOAD_STATUS_DONE

CHECK_CLINICAL_TREE = "clinical_tree"
CHECK_REQUIRED_DOCUMENT_UPLOAD = "required_document_upload"
CHECK_REQUIRED_DOCUMENT_REVIEW = "required_document_review"
CHECK_REQUIRED_IMAGE_UPLOAD = "required_image_upload"
CHECK_IMAGE_REVIEW = "image_review"
CHECK_FIELD_NEEDS_INPUT = "field_needs_input"
CHECK_FIELD_QUALITY_WARNINGS = "field_quality_warnings"


@dataclass(frozen=True)
class SnapshotPrecheckResult:
    check_run_id: str
    subject_id: int
    snapshot_type: str
    schema_version: str
    eligible: bool
    blocking_failure_count: int
    warning_count: int
    checks: list[SnapshotQualityCheck]


def run_snapshot_precheck(
    db: Session,
    subject: Subject,
    *,
    snapshot_type: str = SUBJECT_SNAPSHOT_RELEASED,
) -> SnapshotPrecheckResult:
    check_run_id = str(uuid4())
    checks: list[SnapshotQualityCheck] = []

    sections = list(
        db.scalars(select(SubjectSection).where(SubjectSection.subject_id == subject.id))
    )
    items = list(db.scalars(select(SubjectItem).where(SubjectItem.subject_id == subject.id)))
    required_items = [item for item in items if item.required]
    image_records = {
        record.image_type: record
        for record in db.scalars(
            select(SubjectImageRecord).where(SubjectImageRecord.subject_id == subject.id)
        )
    }
    latest_fields = latest_document_fields_for_subject(db, subject)

    def add_check(
        *,
        check_code: str,
        check_status: str,
        blocking: bool,
        message: str,
        payload_json: dict | None = None,
    ) -> None:
        check = SnapshotQualityCheck(
            check_run_id=check_run_id,
            project_id=subject.project_id,
            center_id=subject.center_id,
            subject_id=subject.id,
            snapshot_id=None,
            schema_version=SUBJECT_SNAPSHOT_SCHEMA_VERSION,
            snapshot_type=snapshot_type,
            check_code=check_code,
            check_status=check_status,
            blocking=blocking,
            message=message,
            payload_json=payload_json,
        )
        db.add(check)
        checks.append(check)

    add_clinical_tree_check(add_check, sections, items)
    add_required_document_upload_check(add_check, required_items)
    add_required_document_review_check(add_check, required_items)
    add_required_image_upload_check(add_check, image_records)
    add_image_review_check(add_check, image_records)
    add_field_needs_input_check(add_check, latest_fields)
    add_field_quality_warning_check(add_check, latest_fields)

    db.flush()
    blocking_failure_count = sum(
        1 for check in checks if check.blocking and check.check_status == SNAPSHOT_CHECK_FAIL
    )
    warning_count = sum(1 for check in checks if check.check_status == SNAPSHOT_CHECK_WARN)
    return SnapshotPrecheckResult(
        check_run_id=check_run_id,
        subject_id=subject.id,
        snapshot_type=snapshot_type,
        schema_version=SUBJECT_SNAPSHOT_SCHEMA_VERSION,
        eligible=blocking_failure_count == 0,
        blocking_failure_count=blocking_failure_count,
        warning_count=warning_count,
        checks=checks,
    )


def latest_document_fields_for_subject(
    db: Session,
    subject: Subject,
) -> list[DocumentExtractedField]:
    file_assets = list(
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
    if not file_assets:
        return []

    file_version_ids: list[int] = []
    for file_asset in file_assets:
        file_version = db.scalar(
            select(FileVersion).where(
                FileVersion.file_id == file_asset.id,
                FileVersion.version == file_asset.version,
            )
        )
        if file_version is not None:
            file_version_ids.append(file_version.id)

    if not file_version_ids:
        return []

    return list(
        db.scalars(
            select(DocumentExtractedField)
            .where(DocumentExtractedField.file_version_id.in_(file_version_ids))
            .order_by(DocumentExtractedField.id)
        )
    )


def add_clinical_tree_check(
    add_check,
    sections: list[SubjectSection],
    items: list[SubjectItem],
) -> None:
    if sections and items:
        add_check(
            check_code=CHECK_CLINICAL_TREE,
            check_status=SNAPSHOT_CHECK_PASS,
            blocking=False,
            message="受试者临床树已建立。",
            payload_json={"section_count": len(sections), "item_count": len(items)},
        )
        return
    add_check(
        check_code=CHECK_CLINICAL_TREE,
        check_status=SNAPSHOT_CHECK_FAIL,
        blocking=True,
        message="受试者临床树缺失，不能生成正式 Snapshot。",
        payload_json={"section_count": len(sections), "item_count": len(items)},
    )


def add_required_document_upload_check(add_check, required_items: list[SubjectItem]) -> None:
    missing_items = [
        required_item_payload(item)
        for item in required_items
        if item.upload_status not in UPLOADED_STATUSES
    ]
    if not missing_items:
        add_check(
            check_code=CHECK_REQUIRED_DOCUMENT_UPLOAD,
            check_status=SNAPSHOT_CHECK_PASS,
            blocking=False,
            message="必填资料项均已上传。",
            payload_json={"required_count": len(required_items), "missing_count": 0},
        )
        return
    add_check(
        check_code=CHECK_REQUIRED_DOCUMENT_UPLOAD,
        check_status=SNAPSHOT_CHECK_FAIL,
        blocking=True,
        message="存在未上传的必填资料项。",
        payload_json={"required_count": len(required_items), "missing_items": missing_items},
    )


def add_required_document_review_check(add_check, required_items: list[SubjectItem]) -> None:
    unapproved_items = [
        required_item_payload(item)
        for item in required_items
        if item.review_status != REVIEW_APPROVED
    ]
    if not unapproved_items:
        add_check(
            check_code=CHECK_REQUIRED_DOCUMENT_REVIEW,
            check_status=SNAPSHOT_CHECK_PASS,
            blocking=False,
            message="必填资料项均已审核通过。",
            payload_json={"required_count": len(required_items), "unapproved_count": 0},
        )
        return
    add_check(
        check_code=CHECK_REQUIRED_DOCUMENT_REVIEW,
        check_status=SNAPSHOT_CHECK_FAIL,
        blocking=True,
        message="存在未审核通过的必填资料项。",
        payload_json={
            "required_count": len(required_items),
            "unapproved_items": unapproved_items,
        },
    )


def add_required_image_upload_check(
    add_check,
    image_records: dict[str, SubjectImageRecord],
) -> None:
    required_types = ("raw", "report")
    missing_types = [
        image_type
        for image_type in required_types
        if image_records.get(image_type) is None
        or image_records[image_type].upload_status != IMAGE_UPLOAD_STATUS_DONE
    ]
    payload = {
        "required_types": list(required_types),
        "missing_types": missing_types,
        "enhanced_uploaded": (
            image_records.get("enhanced") is not None
            and image_records["enhanced"].upload_status == IMAGE_UPLOAD_STATUS_DONE
        ),
    }
    if not missing_types:
        add_check(
            check_code=CHECK_REQUIRED_IMAGE_UPLOAD,
            check_status=SNAPSHOT_CHECK_PASS,
            blocking=False,
            message="必传影像 raw/report 均已上传。",
            payload_json=payload,
        )
        return
    add_check(
        check_code=CHECK_REQUIRED_IMAGE_UPLOAD,
        check_status=SNAPSHOT_CHECK_FAIL,
        blocking=True,
        message="必传影像 raw/report 尚未全部上传。",
        payload_json=payload,
    )


def add_image_review_check(
    add_check,
    image_records: dict[str, SubjectImageRecord],
) -> None:
    add_check(
        check_code=CHECK_IMAGE_REVIEW,
        check_status=SNAPSHOT_CHECK_NOT_SUPPORTED,
        blocking=False,
        message="当前影像记录没有审核状态字段，本版只校验 raw/report 上传。",
        payload_json={"image_record_count": len(image_records)},
    )


def add_field_needs_input_check(
    add_check,
    fields: list[DocumentExtractedField],
) -> None:
    needs_input = [
        field_payload(field) for field in fields if field.status == FIELD_STATUS_NEEDS_INPUT
    ]
    if not needs_input:
        add_check(
            check_code=CHECK_FIELD_NEEDS_INPUT,
            check_status=SNAPSHOT_CHECK_PASS,
            blocking=False,
            message="已抽取字段中没有待补录字段。",
            payload_json={"field_count": len(fields), "needs_input_count": 0},
        )
        return
    add_check(
        check_code=CHECK_FIELD_NEEDS_INPUT,
        check_status=SNAPSHOT_CHECK_FAIL,
        blocking=True,
        message="存在待补录字段，不能生成正式 Snapshot。",
        payload_json={"field_count": len(fields), "needs_input_fields": needs_input},
    )


def add_field_quality_warning_check(
    add_check,
    fields: list[DocumentExtractedField],
) -> None:
    warning_fields = [
        field_payload(field)
        for field in fields
        if field.manually_edited or field.confidence < LOW_CONFIDENCE_THRESHOLD
    ]
    if not warning_fields:
        add_check(
            check_code=CHECK_FIELD_QUALITY_WARNINGS,
            check_status=SNAPSHOT_CHECK_PASS,
            blocking=False,
            message="字段质量未发现低置信或人工修改提示。",
            payload_json={"field_count": len(fields), "warning_count": 0},
        )
        return
    add_check(
        check_code=CHECK_FIELD_QUALITY_WARNINGS,
        check_status=SNAPSHOT_CHECK_WARN,
        blocking=False,
        message="存在低置信或人工修改字段，生成前请关注质量摘要。",
        payload_json={"field_count": len(fields), "warning_fields": warning_fields},
    )


def required_item_payload(item: SubjectItem) -> dict:
    return {
        "subject_item_id": item.id,
        "item_code": item.item_code,
        "item_name": item.item_name,
        "upload_status": item.upload_status,
        "review_status": item.review_status,
    }


def field_payload(field: DocumentExtractedField) -> dict:
    return {
        "field_id": field.id,
        "file_version_id": field.file_version_id,
        "document_type": field.document_type,
        "field_key": field.field_key,
        "field_label": field.field_label,
        "status": field.status,
        "confidence": field.confidence,
        "manually_edited": field.manually_edited,
    }
