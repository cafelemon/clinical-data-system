from collections.abc import Generator
from contextlib import contextmanager
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Subject, SubjectImageRecord
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


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def image_rows(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    center_id: int,
    image_type: str = "raw",
) -> list[dict]:
    response = client.get(
        "/api/image-data",
        headers=headers,
        params={"project_id": project_id, "center_id": center_id, "image_type": image_type},
    )
    assert response.status_code == 200
    return response.json()


def upload_file(
    client: TestClient,
    headers: dict[str, str],
    record_id: int,
    filename: str,
    content: bytes,
    content_type: str,
):
    return client.post(
        f"/api/image-data/{record_id}/upload",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


def setup_subject(
    client: TestClient,
    admin_headers: dict[str, str],
    suffix: str = "IMG",
) -> tuple[int, int, dict]:
    project_id = create_project(client, admin_headers, suffix)
    center_id = create_center(client, admin_headers, project_id, suffix)
    subject = create_subject(client, admin_headers, project_id, center_id, f"{suffix}-001")
    return project_id, center_id, subject


def test_subject_image_records_sync_lazy_fill_and_delete_cascade(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id, center_id, subject = setup_subject(client, admin_headers, "IMG_SYNC")

    rows = image_rows(client, admin_headers, project_id, center_id, "raw")
    assert len(rows) == 1
    assert rows[0]["record"]["image_type"] == "raw"
    assert rows[0]["record"]["upload_status"] == "not_uploaded"

    with db_session(client) as db:
        db.execute(delete(SubjectImageRecord).where(SubjectImageRecord.subject_id == subject["id"]))
        db.commit()
        assert db.scalar(
            select(SubjectImageRecord).where(SubjectImageRecord.subject_id == subject["id"])
        ) is None

    lazy_rows = image_rows(client, admin_headers, project_id, center_id, "enhanced")
    assert len(lazy_rows) == 1
    assert lazy_rows[0]["record"]["image_type"] == "enhanced"
    assert lazy_rows[0]["raw_record"]["image_type"] == "raw"

    delete_response = client.delete(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert delete_response.status_code == 204
    with db_session(client) as db:
        assert db.get(Subject, subject["id"]) is None
        remaining = list(
            db.scalars(
                select(SubjectImageRecord).where(
                    SubjectImageRecord.subject_id == subject["id"]
                )
            )
        )
        assert remaining == []


def test_raw_zip_upload_stats_and_unsafe_zip_rejection(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id, center_id, _ = setup_subject(client, admin_headers, "IMG_RAW")
    raw_record = image_rows(client, admin_headers, project_id, center_id, "raw")[0]["record"]

    upload = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "raw.zip",
        make_zip(
            {
                "OTHER_ROOT/a.jpg": b"jpeg",
                "OTHER_ROOT/b.PNG": b"png-data",
                "OTHER_ROOT/readme.txt": b"ignore",
            }
        ),
        "application/zip",
    )
    assert upload.status_code == 200
    record = upload.json()["record"]
    assert record["upload_status"] == "uploaded"
    assert record["version"] == 1
    assert record["image_count"] == 2
    assert record["image_total_size"] == len(b"jpeg") + len(b"png-data")
    assert record["image_extensions_json"] == {"jpg": 1, "png": 1}
    assert "与试验序列号" in record["parse_warning"]

    rejected = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "bad.zip",
        make_zip({"../escape.jpg": b"x"}),
        "application/zip",
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "zip contains unsafe path"


def test_zip_with_screening_root_extracts_without_warning(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers, "IMG_06012")
    center_id = create_center(client, admin_headers, project_id, "IMG_06012")
    create_subject(client, admin_headers, project_id, center_id, "06012")
    raw_record = image_rows(client, admin_headers, project_id, center_id, "raw")[0]["record"]

    upload = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "06012.zip",
        make_zip({"06012/a.jpg": b"jpeg", "06012/nested/b.PNG": b"png-data"}),
        "application/zip",
    )

    assert upload.status_code == 200
    record = upload.json()["record"]
    assert record["original_name"] == "06012.zip"
    assert record["upload_status"] == "uploaded"
    assert record["storage_path"].endswith(".zip")
    assert record["extracted_dir"]
    assert record["image_count"] == 2
    assert record["image_total_size"] == len(b"jpeg") + len(b"png-data")
    assert record["image_extensions_json"] == {"jpg": 1, "png": 1}
    assert record["parse_warning"] is None
    extracted_dir = settings.file_storage_root / record["extracted_dir"]
    assert (extracted_dir / "06012" / "a.jpg").exists()
    assert (extracted_dir / "06012" / "nested" / "b.PNG").exists()


def test_image_upload_uses_three_gb_default_limit_and_rejects_over_limit(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    assert settings.max_upload_size_mb == 3072
    project_id, center_id, _ = setup_subject(client, admin_headers, "IMG_LIMIT")
    raw_record = image_rows(client, admin_headers, project_id, center_id, "raw")[0]["record"]

    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    too_large = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "raw.zip",
        make_zip({"IMG_LIMIT-001/a.jpg": b"x"}),
        "application/zip",
    )

    assert too_large.status_code == 413
    assert too_large.json()["detail"] == "file too large"


def test_enhanced_and_report_upload_rules(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id, center_id, _ = setup_subject(client, admin_headers, "IMG_RULE")
    enhanced_record = image_rows(client, admin_headers, project_id, center_id, "enhanced")[0][
        "record"
    ]
    report_record = image_rows(client, admin_headers, project_id, center_id, "report")[0]["record"]

    no_raw = upload_file(
        client,
        admin_headers,
        enhanced_record["id"],
        "enhanced.zip",
        make_zip({"IMG_RULE-001/a.jpg": b"x"}),
        "application/zip",
    )
    assert no_raw.status_code == 400
    assert "raw image data" in no_raw.json()["detail"]

    report_rejected = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report.zip",
        make_zip({"report.txt": b"x"}),
        "application/zip",
    )
    assert report_rejected.status_code == 400

    report_upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report.pdf",
        b"%PDF-1.4",
        "application/pdf",
    )
    assert report_upload.status_code == 200
    assert report_upload.json()["record"]["image_count"] == 0

    raw_record = image_rows(client, admin_headers, project_id, center_id, "raw")[0]["record"]
    raw_upload = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "raw.zip",
        make_zip({"IMG_RULE-001/a.jpg": b"x"}),
        "application/zip",
    )
    assert raw_upload.status_code == 200
    enhanced_upload = upload_file(
        client,
        admin_headers,
        enhanced_record["id"],
        "enhanced.zip",
        make_zip({"IMG_RULE-001/a.jpg": b"enhanced"}),
        "application/zip",
    )
    assert enhanced_upload.status_code == 200
    assert enhanced_upload.json()["record"]["source_raw_record_id"] == raw_record["id"]


def test_image_data_role_permissions(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id, center_id, _ = setup_subject(client, admin_headers, "IMG_PERM")
    raw_record = image_rows(client, admin_headers, project_id, center_id, "raw")[0]["record"]
    enhanced_record = image_rows(client, admin_headers, project_id, center_id, "enhanced")[0][
        "record"
    ]
    report_record = image_rows(client, admin_headers, project_id, center_id, "report")[0]["record"]

    raw_upload = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "raw.zip",
        make_zip({"IMG_PERM-001/a.jpg": b"x"}),
        "application/zip",
    )
    assert raw_upload.status_code == 200

    rd_headers = create_user(
        client,
        admin_headers,
        "img_rd_user",
        "rd_user",
        project_ids=[project_id],
    )
    rd_raw_upload = upload_file(
        client,
        rd_headers,
        raw_record["id"],
        "raw2.zip",
        make_zip({"IMG_PERM-001/b.jpg": b"x"}),
        "application/zip",
    )
    assert rd_raw_upload.status_code == 403
    raw_copy = client.get(f"/api/image-data/{raw_record['id']}/raw-copy", headers=rd_headers)
    assert raw_copy.status_code == 200
    rd_enhanced = upload_file(
        client,
        rd_headers,
        enhanced_record["id"],
        "enhanced.zip",
        make_zip({"IMG_PERM-001/a.jpg": b"x"}),
        "application/zip",
    )
    assert rd_enhanced.status_code == 200

    coordinator_headers = create_user(
        client,
        admin_headers,
        "img_coordinator",
        "clinical_coordinator",
        center_ids=[center_id],
    )
    coordinator_report = upload_file(
        client,
        coordinator_headers,
        report_record["id"],
        "report.pdf",
        b"%PDF-1.4",
        "application/pdf",
    )
    assert coordinator_report.status_code == 200
    coordinator_enhanced = upload_file(
        client,
        coordinator_headers,
        enhanced_record["id"],
        "enhanced2.zip",
        make_zip({"IMG_PERM-001/c.jpg": b"x"}),
        "application/zip",
    )
    assert coordinator_enhanced.status_code == 403
