import json
import subprocess
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.config import settings

ROOT_DIR = Path(__file__).resolve().parents[2]


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


def create_project(client: TestClient, headers: dict[str, str], suffix: str) -> int:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": f"P8 项目 {suffix}",
            "code": f"P8_PROJECT_{suffix}",
            "description": "",
            "status": "active",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_center(client: TestClient, headers: dict[str, str], project_id: int, suffix: str) -> int:
    response = client.post(
        "/api/centers",
        headers=headers,
        json={
            "project_id": project_id,
            "name": f"P8 中心 {suffix}",
            "code": f"P8_CENTER_{suffix}",
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_stage_template(client: TestClient, headers: dict[str, str], project_id: int) -> int:
    stage = client.post(
        "/api/stages",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "启动阶段",
            "code": f"STARTUP_{project_id}",
            "sort_order": 1,
            "description": "",
        },
    )
    assert stage.status_code == 201
    template = client.post(
        "/api/stage-templates",
        headers=headers,
        json={
            "project_id": project_id,
            "stage_id": stage.json()["id"],
            "item_name": "伦理批件",
            "item_code": f"ETHICS_{project_id}",
            "required": True,
            "sort_order": 1,
            "description": "",
        },
    )
    assert template.status_code == 201
    return stage.json()["id"]


def create_subject(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    center_id: int,
    screening_no: str,
) -> int:
    response = client.post(
        "/api/subjects",
        headers=headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": screening_no,
            "subject_arm": "experimental",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_user(
    client: TestClient,
    admin_headers: dict[str, str],
    username: str,
    role: str,
    project_ids: list[int] | None = None,
    center_ids: list[int] | None = None,
) -> dict[str, str]:
    response = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": username,
            "password": "User@12345",
            "full_name": username,
            "email": None,
            "is_active": True,
            "role_ids": [role_id_by_name(client, admin_headers, role)],
            "project_ids": project_ids or [],
            "center_ids": center_ids or [],
        },
    )
    assert response.status_code == 201
    return login_headers(client, username, "User@12345")


def xlsx_bytes(headers: list[str], rows: Iterable[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def list_logs(
    client: TestClient,
    headers: dict[str, str],
    params: dict[str, object] | None = None,
) -> dict:
    response = client.get("/api/operation-logs", headers=headers, params=params or {})
    assert response.status_code == 200
    return response.json()


def actions(client: TestClient, headers: dict[str, str]) -> set[str]:
    return {item["action"] for item in list_logs(client, headers, {"limit": 200})["items"]}


def test_auth_master_identity_logs_and_redaction(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    bad_login = client.post(
        "/api/auth/login",
        json={"username": "missing_user", "password": "Secret@123"},
    )
    assert bad_login.status_code == 401
    project_id = create_project(client, admin_headers, "AUDIT")
    update = client.put(
        f"/api/projects/{project_id}",
        headers=admin_headers,
        json={"description": "审计更新"},
    )
    assert update.status_code == 200

    master_read = permission_id_by_code(client, admin_headers, "master_data:read")
    role = client.post(
        "/api/roles",
        headers=admin_headers,
        json={
            "name": "p8_audit_role",
            "label": "P8 审计角色",
            "description": "",
            "permission_ids": [master_read],
        },
    )
    assert role.status_code == 201
    role_update = client.put(
        f"/api/roles/{role.json()['id']}",
        headers=admin_headers,
        json={"permission_ids": [master_read]},
    )
    assert role_update.status_code == 200

    logout = client.post("/api/auth/logout", headers=admin_headers)
    assert logout.status_code == 200

    log_actions = actions(client, admin_headers)
    assert {
        "auth.login",
        "auth.login_failed",
        "auth.logout",
        "project.create",
        "project.update",
        "role.create",
        "role.update",
    }.issubset(log_actions)

    logs = list_logs(client, admin_headers, {"limit": 200})
    serialized = json.dumps([item["detail_json"] for item in logs["items"]], ensure_ascii=False)
    assert "Secret@123" not in serialized
    assert "password" not in serialized.lower()


def test_operation_log_filters_pagination_scope_and_permissions(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "SCOPE")
    center_a = create_center(client, admin_headers, project_id, "A")
    center_b = create_center(client, admin_headers, project_id, "B")
    create_subject(client, admin_headers, project_id, center_a, "P8-A-001")
    create_subject(client, admin_headers, project_id, center_b, "P8-B-001")

    filtered = list_logs(
        client,
        admin_headers,
        {"action": "subject.create", "project_id": project_id, "limit": 1},
    )
    assert filtered["total"] == 2
    assert len(filtered["items"]) == 1
    second_page = list_logs(
        client,
        admin_headers,
        {"action": "subject.create", "project_id": project_id, "limit": 1, "offset": 1},
    )
    assert len(second_page["items"]) == 1
    assert second_page["items"][0]["id"] != filtered["items"][0]["id"]

    center_headers = create_user(
        client,
        admin_headers,
        "p8_center_manager",
        "center_manager",
        center_ids=[center_a],
    )
    scoped_logs = list_logs(client, center_headers, {"limit": 200})
    assert scoped_logs["items"]
    assert all(item["center_id"] == center_a for item in scoped_logs["items"])

    readonly_headers = create_user(
        client,
        admin_headers,
        "p8_readonly",
        "readonly",
        project_ids=[project_id],
    )
    forbidden = client.get("/api/operation-logs", headers=readonly_headers)
    assert forbidden.status_code == 403


def test_file_review_excel_logs(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers, "FLOW")
    center_id = create_center(client, admin_headers, project_id, "FLOW")
    stage_id = create_stage_template(client, admin_headers, project_id)
    stage_files = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_id}&stage_id={stage_id}",
        headers=admin_headers,
    )
    assert stage_files.status_code == 200
    stage_file_id = stage_files.json()[0]["id"]

    upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "clinical_document", "stage_file_id": str(stage_file_id)},
        files={"file": ("ethics.txt", b"ethics file", "text/plain")},
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]
    download = client.get(f"/api/files/{file_id}/download", headers=admin_headers)
    assert download.status_code == 200
    replace = client.post(
        f"/api/files/{file_id}/replace",
        headers=admin_headers,
        files={"file": ("ethics-v2.txt", b"ethics file v2", "text/plain")},
    )
    assert replace.status_code == 200

    submit = client.post(
        "/api/reviews/submit",
        headers=admin_headers,
        json={"target_type": "stage_file", "target_id": stage_file_id, "comment": "提交"},
    )
    assert submit.status_code == 201
    approve = client.post(
        "/api/reviews/approve",
        headers=admin_headers,
        json={"target_type": "stage_file", "target_id": stage_file_id, "comment": "通过"},
    )
    assert approve.status_code == 201

    export_response = client.get(
        f"/api/export/project-progress?project_id={project_id}",
        headers=admin_headers,
    )
    assert export_response.status_code == 200
    import_response = client.post(
        "/api/import/centers",
        headers=admin_headers,
        files={
            "file": (
                "centers.xlsx",
                xlsx_bytes(
                    ["project_code", "code", "name"],
                    [["P8_PROJECT_FLOW", "P8_CENTER_IMPORTED", "导入中心"]],
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert import_response.status_code == 200

    delete = client.delete(f"/api/files/{file_id}", headers=admin_headers)
    assert delete.status_code == 204

    log_actions = actions(client, admin_headers)
    assert {
        "file.upload",
        "file.download",
        "file.replace",
        "file.delete",
        "review.submit",
        "review.approve",
        "excel.export",
        "excel.import",
    }.issubset(log_actions)


def test_backup_scripts_syntax() -> None:
    for script in [
        "scripts/backup_database.sh",
        "scripts/backup_files.sh",
        "scripts/restore_database.sh",
    ]:
        result = subprocess.run(
            ["bash", "-n", str(ROOT_DIR / script)],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
