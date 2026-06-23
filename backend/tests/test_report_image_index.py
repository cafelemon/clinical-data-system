import hashlib
from collections.abc import Generator
from contextlib import contextmanager
from io import BytesIO

import fitz
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import ImageEvidenceIndex
from app.models.image_evidence import (
    IMAGE_EVIDENCE_REPORT_IMAGE,
    IMAGE_EVIDENCE_REPORT_PACKAGE,
)
from tests.test_dashboard import create_center, create_project, create_subject, create_user
from tests.test_image_data import image_rows, upload_file


@contextmanager
def db_session(client: TestClient) -> Generator[Session, None, None]:
    override = client.app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    try:
        yield db
    finally:
        session_generator.close()


def make_png(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 16), color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf(images_by_page: list[list[bytes]]) -> bytes:
    document = fitz.open()
    for page_images in images_by_page:
        page = document.new_page(width=300, height=300)
        for image_index, image_bytes in enumerate(page_images):
            top = 20 + image_index * 80
            page.insert_image(
                fitz.Rect(20, top, 120, top + 60),
                stream=image_bytes,
            )
    payload = document.tobytes()
    document.close()
    return payload


def setup_report_record(
    client: TestClient,
    admin_headers: dict[str, str],
    suffix: str,
) -> tuple[int, int, dict]:
    project_id = create_project(client, admin_headers, suffix)
    center_id = create_center(client, admin_headers, project_id, suffix)
    create_subject(client, admin_headers, project_id, center_id, f"{suffix}-001")
    report_record = image_rows(
        client,
        admin_headers,
        project_id,
        center_id,
        "report",
    )[0]["record"]
    return project_id, center_id, report_record


def evidence_for_record(
    db: Session,
    record_id: int,
) -> list[ImageEvidenceIndex]:
    return list(
        db.scalars(
            select(ImageEvidenceIndex)
            .where(ImageEvidenceIndex.subject_image_record_id == record_id)
            .order_by(ImageEvidenceIndex.evidence_type, ImageEvidenceIndex.id)
        )
    )


def test_pdf_upload_automatically_indexes_and_deduplicates_images(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, report_record = setup_report_record(client, admin_headers, "REPORT_INDEX")
    repeated_image = make_png((20, 120, 220))
    report_pdf = make_pdf([[repeated_image], [repeated_image]])

    upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report.pdf",
        report_pdf,
        "application/pdf",
    )

    assert upload.status_code == 200
    assert upload.json()["record"]["parse_warning"] is None
    with db_session(client) as db:
        evidence = evidence_for_record(db, report_record["id"])
        packages = [row for row in evidence if row.evidence_type == IMAGE_EVIDENCE_REPORT_PACKAGE]
        images = [row for row in evidence if row.evidence_type == IMAGE_EVIDENCE_REPORT_IMAGE]
        assert len(packages) == 1
        assert packages[0].payload_json["index_status"] == "indexed"
        assert packages[0].payload_json["indexed_image_count"] == 1
        assert packages[0].payload_json["duplicate_count"] == 1
        assert len(images) == 1

        image = images[0]
        assert image.evidence_source == "embedded_pdf_image"
        assert image.match_status is None
        assert image.gastrointestinal_location is None
        assert image.payload_json["report_version"] == 1
        assert len(image.payload_json["occurrences"]) == 2
        assert {item["page"] for item in image.payload_json["occurrences"]} == {1, 2}
        image_path = settings.file_storage_root / image.relative_path
        assert image_path.exists()
        image_bytes = image_path.read_bytes()
        assert image.file_hash == hashlib.sha256(image_bytes).hexdigest()
        assert image.file_size == len(image_bytes)


def test_rebuild_replaces_existing_index_without_duplicates(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, report_record = setup_report_record(client, admin_headers, "REPORT_REBUILD")
    report_pdf = make_pdf([[make_png((80, 40, 160))]])
    upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report.pdf",
        report_pdf,
        "application/pdf",
    )
    assert upload.status_code == 200

    rebuild = client.post(
        f"/api/image-data/{report_record['id']}/report-images/index",
        headers=admin_headers,
    )

    assert rebuild.status_code == 200
    payload = rebuild.json()
    assert payload["index_status"] == "indexed"
    assert payload["report_version"] == 1
    assert payload["indexed_image_count"] == 1
    assert payload["duplicate_count"] == 0
    assert len(payload["evidence"]) == 1
    with db_session(client) as db:
        evidence = evidence_for_record(db, report_record["id"])
        assert len(evidence) == 2


def test_new_report_version_removes_old_evidence_and_files(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, report_record = setup_report_record(client, admin_headers, "REPORT_VERSION")
    first_upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report-v1.pdf",
        make_pdf([[make_png((200, 20, 20))]]),
        "application/pdf",
    )
    assert first_upload.status_code == 200
    with db_session(client) as db:
        first_image = next(
            row
            for row in evidence_for_record(db, report_record["id"])
            if row.evidence_type == IMAGE_EVIDENCE_REPORT_IMAGE
        )
        first_evidence_id = first_image.id
        first_image_path = settings.file_storage_root / first_image.relative_path
        assert first_image_path.exists()

    second_upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report-v2.pdf",
        make_pdf([[make_png((20, 200, 20)), make_png((20, 20, 200))]]),
        "application/pdf",
    )

    assert second_upload.status_code == 200
    assert second_upload.json()["record"]["version"] == 2
    assert not first_image_path.exists()
    with db_session(client) as db:
        assert db.get(ImageEvidenceIndex, first_evidence_id) is None
        evidence = evidence_for_record(db, report_record["id"])
        packages = [row for row in evidence if row.evidence_type == IMAGE_EVIDENCE_REPORT_PACKAGE]
        images = [row for row in evidence if row.evidence_type == IMAGE_EVIDENCE_REPORT_IMAGE]
        assert len(packages) == 1
        assert packages[0].payload_json["report_version"] == 2
        assert len(images) == 2
        assert all(row.payload_json["report_version"] == 2 for row in images)


def test_empty_invalid_and_office_reports_preserve_uploaded_record(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, empty_record = setup_report_record(client, admin_headers, "REPORT_EMPTY")
    empty_upload = upload_file(
        client,
        admin_headers,
        empty_record["id"],
        "empty.pdf",
        make_pdf([[]]),
        "application/pdf",
    )
    assert empty_upload.status_code == 200
    assert empty_upload.json()["record"]["upload_status"] == "uploaded"
    assert "未识别到内嵌图片" in empty_upload.json()["record"]["parse_warning"]

    _, _, invalid_record = setup_report_record(client, admin_headers, "REPORT_INVALID")
    invalid_upload = upload_file(
        client,
        admin_headers,
        invalid_record["id"],
        "invalid.pdf",
        b"%PDF-1.4 invalid",
        "application/pdf",
    )
    assert invalid_upload.status_code == 200
    assert invalid_upload.json()["record"]["upload_status"] == "uploaded"
    assert "索引失败" in invalid_upload.json()["record"]["parse_warning"]

    _, _, office_record = setup_report_record(client, admin_headers, "REPORT_OFFICE")
    office_upload = upload_file(
        client,
        admin_headers,
        office_record["id"],
        "report.docx",
        b"not-a-real-docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert office_upload.status_code == 200
    assert office_upload.json()["record"]["upload_status"] == "uploaded"
    assert "仅支持 PDF" in office_upload.json()["record"]["parse_warning"]

    with db_session(client) as db:
        for record_id, expected_status in (
            (empty_record["id"], "empty"),
            (invalid_record["id"], "failed"),
            (office_record["id"], "not_supported"),
        ):
            evidence = evidence_for_record(db, record_id)
            assert len(evidence) == 1
            assert evidence[0].evidence_type == IMAGE_EVIDENCE_REPORT_PACKAGE
            assert evidence[0].payload_json["index_status"] == expected_status


def test_report_delete_removes_evidence_and_extracted_images(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, report_record = setup_report_record(client, admin_headers, "REPORT_DELETE")
    upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report.pdf",
        make_pdf([[make_png((120, 120, 20))]]),
        "application/pdf",
    )
    assert upload.status_code == 200
    with db_session(client) as db:
        image = next(
            row
            for row in evidence_for_record(db, report_record["id"])
            if row.evidence_type == IMAGE_EVIDENCE_REPORT_IMAGE
        )
        image_path = settings.file_storage_root / image.relative_path
        assert image_path.exists()

    deleted = client.delete(
        f"/api/image-data/{report_record['id']}",
        headers=admin_headers,
    )

    assert deleted.status_code == 204
    assert not image_path.exists()
    with db_session(client) as db:
        assert evidence_for_record(db, report_record["id"]) == []


def test_report_image_index_api_validates_type_state_permission_and_scope(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id, center_id, report_record = setup_report_record(
        client,
        admin_headers,
        "REPORT_API",
    )
    raw_record = image_rows(
        client,
        admin_headers,
        project_id,
        center_id,
        "raw",
    )[0]["record"]

    not_report = client.post(
        f"/api/image-data/{raw_record['id']}/report-images/index",
        headers=admin_headers,
    )
    assert not_report.status_code == 400

    not_uploaded = client.post(
        f"/api/image-data/{report_record['id']}/report-images/index",
        headers=admin_headers,
    )
    assert not_uploaded.status_code == 409

    readonly_headers = create_user(
        client,
        admin_headers,
        "report_readonly",
        "readonly",
        project_ids=[project_id],
    )
    forbidden = client.post(
        f"/api/image-data/{report_record['id']}/report-images/index",
        headers=readonly_headers,
    )
    assert forbidden.status_code == 403

    other_project_id = create_project(client, admin_headers, "REPORT_OTHER")
    outside_headers = create_user(
        client,
        admin_headers,
        "report_outside",
        "clinical_coordinator",
        project_ids=[other_project_id],
    )
    outside_scope = client.post(
        f"/api/image-data/{report_record['id']}/report-images/index",
        headers=outside_headers,
    )
    assert outside_scope.status_code == 403

    missing = client.post(
        "/api/image-data/999999/report-images/index",
        headers=admin_headers,
    )
    assert missing.status_code == 404
