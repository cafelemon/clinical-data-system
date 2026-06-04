from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models import (
    Center,
    CorrectionTask,
    DashboardMilestone,
    Dictionary,
    FileAsset,
    FileVersion,
    PdfPacket,
    PdfPacketSegment,
    Project,
    Stage,
    StageTemplate,
    Subject,
)


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def role_id_by_name(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.get("/api/roles", headers=headers)
    assert response.status_code == 200
    return next(role["id"] for role in response.json() if role["name"] == name)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        yield db
    finally:
        generator.close()


def test_system_management_overview_defaults_and_admin_only(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    response = client.get("/api/system-management/overview", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["master_data"] == {
        "project_count": 0,
        "center_count": 0,
        "stage_count": 0,
        "disabled_stage_count": 0,
        "stage_template_count": 0,
        "dictionary_count": 0,
        "disabled_dictionary_count": 0,
    }
    assert body["identity"]["user_count"] == 1
    assert body["identity"]["active_user_count"] == 1
    assert body["audit"]["operation_log_count"] >= 1
    assert body["workflows"]["pdf_packet_count"] == 0
    assert body["manual_maintenance"]["total_count"] == 0

    readonly_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "readonly_346",
            "password": "User@12345",
            "full_name": "Readonly 346",
            "email": None,
            "is_active": True,
            "role_ids": [role_id_by_name(client, admin_headers, "readonly")],
            "project_ids": [],
            "center_ids": [],
        },
    )
    assert readonly_user.status_code == 201
    readonly_headers = login_headers(client, "readonly_346", "User@12345")
    denied = client.get("/api/system-management/overview", headers=readonly_headers)
    assert denied.status_code == 403


def test_system_management_overview_counts_modules(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    with db_session() as db:
        project = Project(name="V346 项目", code="V346_PROJECT", status="active")
        db.add(project)
        db.flush()
        center = Center(
            project_id=project.id,
            name="V346 中心",
            code="V346_CENTER",
            status="active",
        )
        db.add(center)
        db.flush()
        stage = Stage(
            project_id=project.id,
            name="V346 阶段",
            code="V346_STAGE",
            phase_code="STARTUP",
            option_code="STARTUP_MATERIALS",
            enabled=False,
            sort_order=1,
        )
        db.add(stage)
        db.flush()
        db.add(
            StageTemplate(
                project_id=project.id,
                stage_id=stage.id,
                item_name="V346 资料",
                item_code="V346_ITEM",
                template_scope="center_file",
                required=True,
                sort_order=1,
            )
        )
        db.add(
            Dictionary(
                dict_type="v346_status",
                value="disabled",
                label="停用",
                color="neutral",
                sort_order=1,
                enabled=False,
            )
        )
        subject = Subject(
            project_id=project.id,
            center_id=center.id,
            screening_no="V346-S001",
        )
        db.add(subject)
        db.flush()
        packet = PdfPacket(
            packet_id="v346-packet",
            original_name="v346.pdf",
            stored_name="v346.pdf",
            file_ext=".pdf",
            mime_type="application/pdf",
            file_size=100,
            file_hash="hash-v346",
            storage_path="v346.pdf",
            project_id=project.id,
            center_id=center.id,
            subject_id=subject.id,
            screening_no=subject.screening_no,
            page_count=2,
            status="ready",
        )
        db.add(packet)
        db.flush()
        db.add(
            PdfPacketSegment(
                packet_id=packet.id,
                page_start=1,
                page_end=2,
                detected_name="V346 资料",
                confidence=0.9,
                status="pending_review",
            )
        )
        file_asset = FileAsset(
            file_id="v346-file",
            original_name="v346.pdf",
            stored_name="v346.pdf",
            file_ext=".pdf",
            mime_type="application/pdf",
            file_size=100,
            file_hash="file-hash-v346",
            storage_path="v346-file.pdf",
            project_id=project.id,
            center_id=center.id,
            subject_id=subject.id,
            file_category="subject_item",
            version=1,
        )
        db.add(file_asset)
        db.flush()
        file_version = FileVersion(
            file_id=file_asset.id,
            version=1,
            storage_path="v346-file.pdf",
            file_hash="file-version-hash-v346",
            file_size=100,
            mime_type="application/pdf",
            original_name="v346.pdf",
            stored_name="v346.pdf",
        )
        db.add(file_version)
        db.flush()
        db.add(
            CorrectionTask(
                task_no="V346-TASK",
                project_id=project.id,
                center_id=center.id,
                file_id=file_asset.id,
                source_file_version_id=file_version.id,
                title="V346 整改",
                status="submitted",
            )
        )
        db.add(
            DashboardMilestone(
                project_id=project.id,
                center_id=center.id,
                milestone_name="V346 里程碑",
                status="in_progress",
            )
        )
        db.commit()

    response = client.get("/api/system-management/overview", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["master_data"]["project_count"] == 1
    assert body["master_data"]["center_count"] == 1
    assert body["master_data"]["stage_count"] == 1
    assert body["master_data"]["disabled_stage_count"] == 1
    assert body["master_data"]["stage_template_count"] == 1
    assert body["master_data"]["dictionary_count"] == 1
    assert body["master_data"]["disabled_dictionary_count"] == 1
    assert body["workflows"]["pdf_packet_count"] == 1
    assert body["workflows"]["pdf_packet_segment_count"] == 1
    assert body["workflows"]["correction_task_count"] == 1
    assert body["workflows"]["open_correction_task_count"] == 1
    assert body["workflows"]["pending_review_task_count"] == 1
    assert body["manual_maintenance"]["milestone_count"] == 1
    assert body["manual_maintenance"]["total_count"] == 1
