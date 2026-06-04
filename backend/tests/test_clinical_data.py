from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Subject


@contextmanager
def db_session(client: TestClient) -> Generator[Session, None, None]:
    override = client.app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    try:
        yield db
    finally:
        session_generator.close()


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def role_id_by_name(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.get("/api/roles", headers=headers)
    assert response.status_code == 200
    return next(role["id"] for role in response.json() if role["name"] == name)


def permission_id_by_code(client: TestClient, headers: dict[str, str], code: str) -> int:
    response = client.get("/api/permissions", headers=headers)
    assert response.status_code == 200
    return next(permission["id"] for permission in response.json() if permission["code"] == code)


def create_project(client: TestClient, headers: dict[str, str], name: str, code: str) -> int:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={"name": name, "code": code, "description": "", "status": "active"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_center(client: TestClient, headers: dict[str, str], project_id: int, code: str) -> int:
    response = client.post(
        "/api/centers",
        headers=headers,
        json={
            "project_id": project_id,
            "name": f"中心 {code}",
            "code": code,
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_stage(client: TestClient, headers: dict[str, str], project_id: int, code: str) -> int:
    stage_names = {
        "STARTUP": "启动阶段",
        "TRIAL": "试验进行阶段",
        "CLOSEOUT": "总结阶段",
    }
    sort_order = {"STARTUP": 1, "TRIAL": 2, "CLOSEOUT": 3}[code]
    response = client.post(
        "/api/stages",
        headers=headers,
        json={
            "project_id": project_id,
            "name": stage_names[code],
            "code": code,
            "sort_order": sort_order,
            "description": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_stage_template(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    stage_id: int,
    item_name: str,
    item_code: str,
) -> int:
    response = client.post(
        "/api/stage-templates",
        headers=headers,
        json={
            "project_id": project_id,
            "stage_id": stage_id,
            "item_name": item_name,
            "item_code": item_code,
            "required": True,
            "sort_order": 1,
            "description": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_subject(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    center_id: int,
    screening_no: str,
) -> dict:
    response = client.post(
        "/api/subjects",
        headers=headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": screening_no,
            "subject_arm": "experimental",
            "gender": "女",
            "age": 42,
            "enrolled_at": "2026-05-04",
            "informed_at": "2026-05-04T09:30:00",
            "visit1_date": "2026-05-05",
            "visit2_date": "2026-05-06",
            "visit3_date": "2026-05-07",
            "visit4_date": "2026-05-08",
            "review_status": "unreviewed",
            "data_status": "incomplete",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_clinical_dataset_flow_materializes_files_and_subject_items(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    assert client.get("/api/subjects").status_code == 401

    project_id = create_project(client, admin_headers, "P3 项目", "P3_PROJECT")
    center_id = create_center(client, admin_headers, project_id, "P3_CENTER")
    startup_stage_id = create_stage(client, admin_headers, project_id, "STARTUP")
    create_stage(client, admin_headers, project_id, "TRIAL")
    closeout_stage_id = create_stage(client, admin_headers, project_id, "CLOSEOUT")
    create_stage_template(
        client,
        admin_headers,
        project_id,
        startup_stage_id,
        "伦理批件",
        "ETHICS_APPROVAL",
    )
    create_stage_template(
        client,
        admin_headers,
        project_id,
        closeout_stage_id,
        "总结报告",
        "CLOSEOUT_REPORT",
    )

    first_stage_files = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_id}&stage_id={startup_stage_id}",
        headers=admin_headers,
    )
    assert first_stage_files.status_code == 200
    assert len(first_stage_files.json()) == 27
    assert "伦理批件" in [item["file_name"] for item in first_stage_files.json()]
    optional_startup_file = next(
        item
        for item in first_stage_files.json()
        if item["file_type"] == "STARTUP_005_RECRUITMENT_DOCUMENTS"
    )
    assert optional_startup_file["required"] is False
    assert optional_startup_file["not_applicable"] is False
    assert optional_startup_file["completeness_status"] == "incomplete"

    required_startup_file = next(
        item for item in first_stage_files.json() if item["file_name"] == "伦理批件"
    )
    required_applicability = client.patch(
        f"/api/stage-files/{required_startup_file['id']}/applicability",
        headers=admin_headers,
        json={"not_applicable": True, "reason": "不适用"},
    )
    assert required_applicability.status_code == 400

    mark_not_applicable = client.patch(
        f"/api/stage-files/{optional_startup_file['id']}/applicability",
        headers=admin_headers,
        json={"not_applicable": True, "reason": "本中心未招募宣传"},
    )
    assert mark_not_applicable.status_code == 200
    assert mark_not_applicable.json()["not_applicable"] is True
    assert mark_not_applicable.json()["not_applicable_reason"] == "本中心未招募宣传"
    assert mark_not_applicable.json()["not_applicable_by_name"]
    assert mark_not_applicable.json()["completeness_status"] == "complete"

    clear_not_applicable = client.patch(
        f"/api/stage-files/{optional_startup_file['id']}/applicability",
        headers=admin_headers,
        json={"not_applicable": False},
    )
    assert clear_not_applicable.status_code == 200
    assert clear_not_applicable.json()["not_applicable"] is False
    assert clear_not_applicable.json()["not_applicable_reason"] is None
    assert clear_not_applicable.json()["completeness_status"] == "incomplete"

    client.patch(
        f"/api/stage-files/{optional_startup_file['id']}/applicability",
        headers=admin_headers,
        json={"not_applicable": True, "reason": "上传后应自动清除"},
    )
    optional_upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "clinical_document", "stage_file_id": str(optional_startup_file["id"])},
        files={"file": ("optional.pdf", b"%PDF-optional", "application/pdf")},
    )
    assert optional_upload.status_code == 201
    uploaded_optional = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_id}&stage_id={startup_stage_id}",
        headers=admin_headers,
    )
    uploaded_optional_file = next(
        item
        for item in uploaded_optional.json()
        if item["file_type"] == "STARTUP_005_RECRUITMENT_DOCUMENTS"
    )
    assert uploaded_optional_file["not_applicable"] is False
    assert uploaded_optional_file["not_applicable_reason"] is None
    assert uploaded_optional_file["completeness_status"] == "checking"
    uploaded_optional_applicability = client.patch(
        f"/api/stage-files/{optional_startup_file['id']}/applicability",
        headers=admin_headers,
        json={"not_applicable": True, "reason": "已有文件"},
    )
    assert uploaded_optional_applicability.status_code == 400

    second_stage_files = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_id}&stage_id={startup_stage_id}",
        headers=admin_headers,
    )
    assert second_stage_files.status_code == 200
    assert len(second_stage_files.json()) == 27
    assert [item["id"] for item in second_stage_files.json()] == [
        item["id"] for item in first_stage_files.json()
    ]

    subject = create_subject(client, admin_headers, project_id, center_id, "P3-S001")
    assert subject["subject_arm"] == "experimental"
    assert subject["informed_at"].startswith("2026-05-04T09:30")
    assert subject["visit4_date"] == "2026-05-08"
    update_subject = client.put(
        f"/api/subjects/{subject['id']}",
        headers=admin_headers,
        json={
            "subject_arm": "control",
            "informed_at": "2026-05-04T10:45:00",
            "visit3_date": "2026-05-10",
            "review_status": "rejected",
        },
    )
    assert update_subject.status_code == 200
    assert update_subject.json()["subject_arm"] == "control"
    assert update_subject.json()["informed_at"].startswith("2026-05-04T10:45")
    assert update_subject.json()["visit3_date"] == "2026-05-10"
    with db_session(client) as db:
        db_subject = db.get(Subject, subject["id"])
        assert db_subject is not None
        db_subject.subject_arm = None
        db.commit()
    legacy_subject = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert legacy_subject.status_code == 200
    assert legacy_subject.json()["subject_arm"] is None
    duplicate = client.post(
        "/api/subjects",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "P3-S001",
            "subject_arm": "experimental",
        },
    )
    assert duplicate.status_code == 409

    sections = client.get(f"/api/subjects/{subject['id']}/sections", headers=admin_headers)
    assert sections.status_code == 200
    assert [section["name"] for section in sections.json()] == [
        "V1筛选访视阶段",
        "V2试验组随访访视",
        "V3对照组随访访视（若有）",
        "V4非预期访视（若有）",
    ]

    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    assert items.status_code == 200
    assert len(items.json()) == 22
    assert "V3_CONTROL_REPORT" in {item["item_code"] for item in items.json()}

    item_id = items.json()[0]["id"]
    update_item = client.put(
        f"/api/subject-items/{item_id}",
        headers=admin_headers,
        json={"upload_status": "uploaded", "review_status": "rejected", "remark": "已核对"},
    )
    assert update_item.status_code == 200
    assert update_item.json()["remark"] == "已核对"

    dataset = client.get(
        f"/api/clinical-datasets?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    )
    assert dataset.status_code == 200
    dataset_body = dataset.json()
    assert dataset_body["stage_file_count"] == 57
    assert len(dataset_body["ssu_progress"]) == 5
    assert len(dataset_body["trial_file_groups"]) == 1
    assert len(dataset_body["trial_files"]) == 19
    assert dataset_body["subject_count"] == 1
    assert dataset_body["summary"]["stage_files"] == {
        "complete": 0,
        "checking": 1,
        "incomplete": 56,
    }
    assert dataset_body["summary"]["subjects"] == {
        "complete": 0,
        "checking": 0,
        "incomplete": 1,
    }
    assert dataset_body["summary"]["reviews"]["rejected"] == 1
    assert dataset_body["summary"]["ssu"] == {
        "total": 5,
        "completed": 0,
        "blocked": 0,
        "active": 0,
    }
    assert dataset_body["summary"]["optional_files"]["uploaded"] == 1
    assert dataset_body["summary"]["optional_files"]["not_applicable"] == 0
    assert any(group["total"] > 0 for group in dataset_body["summary"]["stage_groups"])
    dataset_subject = dataset_body["subjects"][0]
    assert dataset_subject["subject_arm"] is None
    assert dataset_subject["informed_at"].startswith("2026-05-04T10:45")
    assert dataset_subject["visit3_date"] == "2026-05-10"
    assert dataset_subject["review_status"] == "rejected"


def test_clinical_data_scope_and_write_permission(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_a_id = create_project(client, admin_headers, "授权项目", "P3_SCOPE_A")
    project_b_id = create_project(client, admin_headers, "越权项目", "P3_SCOPE_B")
    center_a_id = create_center(client, admin_headers, project_a_id, "A_CENTER")
    center_b_id = create_center(client, admin_headers, project_b_id, "B_CENTER")
    subject_a = create_subject(client, admin_headers, project_a_id, center_a_id, "A-S001")
    subject_b = create_subject(client, admin_headers, project_b_id, center_b_id, "B-S001")

    readonly_role_id = role_id_by_name(client, admin_headers, "readonly")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "p3_readonly",
            "password": "Readonly@123",
            "full_name": "P3 只读",
            "email": None,
            "is_active": True,
            "role_ids": [readonly_role_id],
            "project_ids": [project_a_id],
            "center_ids": [],
        },
    )
    assert create_user.status_code == 201

    readonly_headers = login_headers(client, "p3_readonly", "Readonly@123")
    subjects = client.get("/api/subjects", headers=readonly_headers)
    assert subjects.status_code == 200
    assert [subject["id"] for subject in subjects.json()] == [subject_a["id"]]

    dataset_a = client.get(
        f"/api/clinical-datasets?project_id={project_a_id}&center_id={center_a_id}",
        headers=admin_headers,
    )
    assert dataset_a.status_code == 200
    ssu_id = dataset_a.json()["ssu_progress"][0]["id"]
    readonly_ssu = client.get(
        f"/api/clinical-datasets/ssu-progress?project_id={project_a_id}&center_id={center_a_id}",
        headers=readonly_headers,
    )
    assert readonly_ssu.status_code == 200
    assert len(readonly_ssu.json()) == 5
    denied_ssu_write = client.patch(
        f"/api/clinical-datasets/ssu-progress/{ssu_id}",
        headers=readonly_headers,
        json={"status": "completed"},
    )
    assert denied_ssu_write.status_code == 403

    denied_detail = client.get(f"/api/subjects/{subject_b['id']}", headers=readonly_headers)
    assert denied_detail.status_code == 403

    denied_write = client.post(
        "/api/subjects",
        headers=readonly_headers,
        json={
            "project_id": project_a_id,
            "center_id": center_a_id,
            "screening_no": "A-S002",
            "subject_arm": "experimental",
        },
    )
    assert denied_write.status_code == 403


def test_subject_delete_permission_removes_records_and_files(
    client: TestClient,
    admin_headers: dict[str, str],
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers, "删除项目", "P3_DELETE")
    center_id = create_center(client, admin_headers, project_id, "DELETE_CENTER")
    subject = create_subject(client, admin_headers, project_id, center_id, "DEL-S001")
    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    assert items.status_code == 200
    item_id = items.json()[0]["id"]

    upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "clinical_document", "subject_item_id": str(item_id)},
        files={"file": ("consent.pdf", b"%PDF-consent", "application/pdf")},
    )
    assert upload.status_code == 201
    uploaded_path = settings.file_storage_root / upload.json()["storage_path"]
    assert uploaded_path.exists()

    project_manager_role_id = role_id_by_name(client, admin_headers, "project_manager")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "p3_delete_manager",
            "password": "Manager@123",
            "full_name": "P3 删除项目负责人",
            "email": None,
            "is_active": True,
            "role_ids": [project_manager_role_id],
            "project_ids": [project_id],
            "center_ids": [],
        },
    )
    assert create_user.status_code == 201
    manager_headers = login_headers(client, "p3_delete_manager", "Manager@123")
    denied_delete = client.delete(f"/api/subjects/{subject['id']}", headers=manager_headers)
    assert denied_delete.status_code == 403

    delete_permission_id = permission_id_by_code(
        client,
        admin_headers,
        "clinical_data:delete",
    )
    delete_role = client.post(
        "/api/roles",
        headers=admin_headers,
        json={
            "name": "p3_subject_deleter",
            "label": "P3 受试者删除",
            "description": "",
            "permission_ids": [delete_permission_id],
        },
    )
    assert delete_role.status_code == 201
    create_deleter = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "p3_subject_deleter",
            "password": "Deleter@123",
            "full_name": "P3 受试者删除",
            "email": None,
            "is_active": True,
            "role_ids": [delete_role.json()["id"]],
            "project_ids": [project_id],
            "center_ids": [],
        },
    )
    assert create_deleter.status_code == 201
    deleter_headers = login_headers(client, "p3_subject_deleter", "Deleter@123")
    deleted = client.delete(f"/api/subjects/{subject['id']}", headers=deleter_headers)
    assert deleted.status_code == 204
    assert not uploaded_path.exists()
    assert client.get(f"/api/subjects/{subject['id']}", headers=admin_headers).status_code == 404
    files = client.get(f"/api/files?subject_id={subject['id']}", headers=admin_headers)
    assert files.status_code == 200
    assert files.json() == []
