from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clinical_data import REVIEW_APPROVED, UPLOAD_UPLOADED
from app.core.database import get_db
from app.models import (
    DocumentExtractedField,
    FileAsset,
    FileVersion,
    SnapshotQualityCheck,
    SubjectImageRecord,
    SubjectItem,
    SubjectSnapshot,
)
from app.services.snapshot_precheck import (
    CHECK_FIELD_NEEDS_INPUT,
    CHECK_FIELD_QUALITY_WARNINGS,
    CHECK_IMAGE_REVIEW,
    CHECK_REQUIRED_DOCUMENT_REVIEW,
    CHECK_REQUIRED_DOCUMENT_UPLOAD,
    CHECK_REQUIRED_IMAGE_UPLOAD,
)
from tests.test_dashboard import create_center, create_project, create_subject, create_user


@contextmanager
def db_session(client: TestClient) -> Generator[Session, None, None]:
    override = client.app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    try:
        yield db
    finally:
        session_generator.close()


def setup_subject(
    client: TestClient,
    headers: dict[str, str],
    suffix: str,
) -> tuple[int, int, dict]:
    project_id = create_project(client, headers, suffix)
    center_id = create_center(client, headers, project_id, suffix)
    subject = create_subject(client, headers, project_id, center_id, f"{suffix}-001")
    return project_id, center_id, subject


def mark_required_documents_approved(db: Session, subject_id: int) -> None:
    for item in db.scalars(select(SubjectItem).where(SubjectItem.subject_id == subject_id)):
        if item.required:
            item.upload_status = UPLOAD_UPLOADED
            item.review_status = REVIEW_APPROVED


def mark_required_images_uploaded(db: Session, subject_id: int) -> None:
    for record in db.scalars(
        select(SubjectImageRecord).where(SubjectImageRecord.subject_id == subject_id)
    ):
        if record.image_type in {"raw", "report"}:
            record.upload_status = "uploaded"


def create_latest_field(
    db: Session,
    *,
    subject_id: int,
    subject_item_id: int,
    status: str,
    confidence: float,
    manually_edited: bool = False,
) -> DocumentExtractedField:
    subject_item = db.get(SubjectItem, subject_item_id)
    assert subject_item is not None
    file_asset = FileAsset(
        file_id=f"snapshot-precheck-{subject_id}",
        original_name="snapshot-precheck.pdf",
        stored_name="snapshot-precheck.pdf",
        file_ext="pdf",
        mime_type="application/pdf",
        file_size=100,
        file_hash="a" * 64,
        storage_path="tests/snapshot-precheck.pdf",
        project_id=subject_item.subject.project_id,
        center_id=subject_item.subject.center_id,
        subject_id=subject_id,
        subject_item_id=subject_item_id,
        file_category="raw_pdf",
        version=1,
        status="active",
    )
    db.add(file_asset)
    db.flush()
    file_version = FileVersion(
        file_id=file_asset.id,
        version=1,
        storage_path=file_asset.storage_path,
        file_hash=file_asset.file_hash,
        file_size=file_asset.file_size,
        mime_type=file_asset.mime_type,
        original_name=file_asset.original_name,
        stored_name=file_asset.stored_name,
    )
    db.add(file_version)
    db.flush()
    field = DocumentExtractedField(
        file_version_id=file_version.id,
        document_type="informed_consent",
        field_key="subject_signed_at",
        field_label="受试者签署时间",
        value_type="datetime",
        raw_value="2025.12.18 08.07",
        normalized_value="2025-12-18 08:07",
        source_page_no=1,
        source_text="受试者签署时间 2025.12.18 08.07",
        confidence=confidence,
        status=status,
        manually_edited=manually_edited,
    )
    db.add(field)
    db.flush()
    return field


def check_by_code(body: dict, check_code: str) -> dict:
    return next(check for check in body["checks"] if check["check_code"] == check_code)


def test_snapshot_precheck_complete_subject_persists_checks(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = setup_subject(client, admin_headers, "PRECHECK_OK")
    with db_session(client) as db:
        mark_required_documents_approved(db, subject["id"])
        mark_required_images_uploaded(db, subject["id"])
        before_snapshots = db.scalar(select(func.count()).select_from(SubjectSnapshot))
        db.commit()

    response = client.post(
        f"/api/subjects/{subject['id']}/snapshots/precheck",
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is True
    assert body["blocking_failure_count"] == 0
    assert body["warning_count"] == 0
    assert body["snapshot_type"] == "released_snapshot"
    assert check_by_code(body, CHECK_IMAGE_REVIEW)["check_status"] == "not_supported"
    assert check_by_code(body, CHECK_REQUIRED_IMAGE_UPLOAD)["check_status"] == "pass"
    image_payload = check_by_code(body, CHECK_REQUIRED_IMAGE_UPLOAD)["payload_json"]
    assert image_payload["enhanced_uploaded"] is False

    with db_session(client) as db:
        persisted = list(
            db.scalars(
                select(SnapshotQualityCheck).where(
                    SnapshotQualityCheck.check_run_id == body["check_run_id"]
                )
            )
        )
        assert len(persisted) == len(body["checks"])
        assert db.scalar(select(func.count()).select_from(SubjectSnapshot)) == before_snapshots


def test_snapshot_precheck_blocks_missing_required_documents_and_images(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = setup_subject(client, admin_headers, "PRECHECK_MISSING")

    response = client.post(
        f"/api/subjects/{subject['id']}/snapshots/precheck",
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is False
    assert check_by_code(body, CHECK_REQUIRED_DOCUMENT_UPLOAD)["check_status"] == "fail"
    assert check_by_code(body, CHECK_REQUIRED_DOCUMENT_REVIEW)["check_status"] == "fail"
    image_check = check_by_code(body, CHECK_REQUIRED_IMAGE_UPLOAD)
    assert image_check["check_status"] == "fail"
    assert image_check["payload_json"]["missing_types"] == ["raw", "report"]


def test_snapshot_precheck_field_needs_input_blocks_and_quality_warns(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = setup_subject(client, admin_headers, "PRECHECK_FIELD")
    with db_session(client) as db:
        mark_required_documents_approved(db, subject["id"])
        mark_required_images_uploaded(db, subject["id"])
        item = db.scalar(
            select(SubjectItem).where(
                SubjectItem.subject_id == subject["id"],
                SubjectItem.required.is_(True),
            )
        )
        assert item is not None
        field = create_latest_field(
            db,
            subject_id=subject["id"],
            subject_item_id=item.id,
            status="needs_input",
            confidence=0.0,
        )
        field_id = field.id
        db.commit()

    blocked = client.post(
        f"/api/subjects/{subject['id']}/snapshots/precheck",
        headers=admin_headers,
    )
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["eligible"] is False
    assert check_by_code(blocked_body, CHECK_FIELD_NEEDS_INPUT)["check_status"] == "fail"

    with db_session(client) as db:
        loaded_field = db.get(DocumentExtractedField, field_id)
        assert loaded_field is not None
        loaded_field.status = "confirmed"
        loaded_field.confidence = 0.6
        loaded_field.manually_edited = True
        db.commit()

    warned = client.post(
        f"/api/subjects/{subject['id']}/snapshots/precheck",
        headers=admin_headers,
    )
    assert warned.status_code == 200
    warned_body = warned.json()
    assert warned_body["eligible"] is True
    assert warned_body["warning_count"] == 1
    assert check_by_code(warned_body, CHECK_FIELD_QUALITY_WARNINGS)["check_status"] == "warn"


def test_snapshot_precheck_api_auth_scope_and_missing_subject(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_a_id, _, _ = setup_subject(client, admin_headers, "PRECHECK_SCOPE_A")
    project_b_id, _, subject_b = setup_subject(
        client,
        admin_headers,
        "PRECHECK_SCOPE_B",
    )

    readonly_headers = create_user(
        client,
        admin_headers,
        "precheck_readonly",
        "readonly",
        project_ids=[project_b_id],
    )
    readonly_response = client.post(
        f"/api/subjects/{subject_b['id']}/snapshots/precheck",
        headers=readonly_headers,
    )
    assert readonly_response.status_code == 403

    scoped_headers = create_user(
        client,
        admin_headers,
        "precheck_project_manager",
        "project_manager",
        project_ids=[project_a_id],
    )
    scoped_response = client.post(
        f"/api/subjects/{subject_b['id']}/snapshots/precheck",
        headers=scoped_headers,
    )
    assert scoped_response.status_code == 403

    missing_response = client.post("/api/subjects/999999/snapshots/precheck", headers=admin_headers)
    assert missing_response.status_code == 404
