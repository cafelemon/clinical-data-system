from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.files import preview_media_type


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def role_id_by_name(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.get("/api/roles", headers=headers)
    assert response.status_code == 200
    return next(role["id"] for role in response.json() if role["name"] == name)


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
    stage_names = {"STARTUP": "启动阶段", "TRIAL": "试验进行阶段", "CLOSEOUT": "总结阶段"}
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


def create_stage_file(client: TestClient, headers: dict[str, str], code_suffix: str = "A") -> dict:
    project_id = create_project(
        client,
        headers,
        f"P4 项目 {code_suffix}",
        f"P4_PROJECT_{code_suffix}",
    )
    center_id = create_center(client, headers, project_id, f"P4_CENTER_{code_suffix}")
    stage_id = create_stage(client, headers, project_id, "STARTUP")
    template = client.post(
        "/api/stage-templates",
        headers=headers,
        json={
            "project_id": project_id,
            "stage_id": stage_id,
            "item_name": "伦理批件",
            "item_code": f"ETHICS_{code_suffix}",
            "required": True,
            "sort_order": 1,
            "description": "",
        },
    )
    assert template.status_code == 201
    response = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_id}&stage_id={stage_id}",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()[0]


def create_subject_item(client: TestClient, headers: dict[str, str]) -> dict:
    project_id = create_project(client, headers, "P4 受试者项目", "P4_SUBJECT_PROJECT")
    center_id = create_center(client, headers, project_id, "P4_SUBJECT_CENTER")
    subject = client.post(
        "/api/subjects",
        headers=headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "P4-S001",
            "subject_arm": "experimental",
        },
    )
    assert subject.status_code == 201
    items = client.get(f"/api/subjects/{subject.json()['id']}/items", headers=headers)
    assert items.status_code == 200
    return items.json()[0]


def storage_path(root: Path, storage_path_value: str) -> Path:
    return root / storage_path_value


def test_stage_file_upload_download_preview_replace_versions_and_delete(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "file-storage"
    monkeypatch.setattr(settings, "file_storage_root", storage_root)
    stage_file = create_stage_file(client, admin_headers)
    original = b"%PDF-1.4\noriginal"

    no_token = client.post(
        "/api/files/upload",
        data={"file_category": "raw_pdf", "stage_file_id": str(stage_file["id"])},
        files={"file": ("ethics.pdf", original, "application/pdf")},
    )
    assert no_token.status_code == 401

    upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "raw_pdf", "stage_file_id": str(stage_file["id"])},
        files={"file": ("ethics.pdf", original, "application/pdf")},
    )
    assert upload.status_code == 201
    file_record = upload.json()
    assert file_record["file_hash"] == sha256(original).hexdigest()
    assert storage_path(storage_root, file_record["storage_path"]).exists()

    stage_files = client.get(
        f"/api/stage-files?project_id={stage_file['project_id']}&center_id={stage_file['center_id']}",
        headers=admin_headers,
    )
    assert stage_files.status_code == 200
    assert stage_files.json()[0]["upload_status"] == "uploaded"
    assert stage_files.json()[0]["review_status"] == "unreviewed"

    listed = client.get(f"/api/files?stage_file_id={stage_file['id']}", headers=admin_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [file_record["id"]]

    download = client.get(f"/api/files/{file_record['id']}/download", headers=admin_headers)
    assert download.status_code == 200
    assert download.content == original

    preview = client.get(f"/api/files/{file_record['id']}/preview", headers=admin_headers)
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("application/pdf")

    generic_pdf = b"%PDF-1.4\ngeneric"
    generic_upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "raw_pdf", "stage_file_id": str(stage_file["id"])},
        files={"file": ("scanner-output.pdf", generic_pdf, "application/octet-stream")},
    )
    assert generic_upload.status_code == 201
    assert generic_upload.json()["mime_type"] == "application/pdf"
    generic_preview = client.get(
        f"/api/files/{generic_upload.json()['id']}/preview",
        headers=admin_headers,
    )
    assert generic_preview.status_code == 200
    assert generic_preview.headers["content-type"].startswith("application/pdf")

    replacement = b"%PDF-1.4\nreplacement"
    replace = client.post(
        f"/api/files/{file_record['id']}/replace",
        headers=admin_headers,
        data={"change_note": "替换版本"},
        files={"file": ("ethics-v2.pdf", replacement, "application/pdf")},
    )
    assert replace.status_code == 200
    replaced_record = replace.json()
    assert replaced_record["version"] == 2

    versions = client.get(f"/api/files/{file_record['id']}/versions", headers=admin_headers)
    assert versions.status_code == 200
    assert [version["version"] for version in versions.json()] == [1, 2]

    old_download = client.get(
        f"/api/files/{file_record['id']}/download?version=1",
        headers=admin_headers,
    )
    assert old_download.status_code == 200
    assert old_download.content == original

    excel_upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "clinical_document", "stage_file_id": str(stage_file["id"])},
        files={
            "file": (
                "sheet.xlsx",
                b"excel-bytes",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert excel_upload.status_code == 201
    excel_preview = client.get(
        f"/api/files/{excel_upload.json()['id']}/preview",
        headers=admin_headers,
    )
    assert excel_preview.status_code == 415

    delete_pdf = client.delete(f"/api/files/{file_record['id']}", headers=admin_headers)
    assert delete_pdf.status_code == 204
    assert not storage_path(storage_root, file_record["storage_path"]).exists()
    assert not storage_path(storage_root, replaced_record["storage_path"]).exists()

    delete_generic_pdf = client.delete(
        f"/api/files/{generic_upload.json()['id']}",
        headers=admin_headers,
    )
    assert delete_generic_pdf.status_code == 204

    delete_excel = client.delete(f"/api/files/{excel_upload.json()['id']}", headers=admin_headers)
    assert delete_excel.status_code == 204
    reset_stage_files = client.get(
        f"/api/stage-files?project_id={stage_file['project_id']}&center_id={stage_file['center_id']}",
        headers=admin_headers,
    )
    assert reset_stage_files.json()[0]["upload_status"] == "not_uploaded"


def test_preview_media_type_falls_back_to_pdf_filename() -> None:
    assert preview_media_type("application/octet-stream", "legacy-upload.pdf") == "application/pdf"
    assert preview_media_type(None, "legacy-upload.pdf") == "application/pdf"
    assert preview_media_type("application/octet-stream", "sheet.xlsx") is None


def test_subject_item_file_status_sync_and_size_limit(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    item = create_subject_item(client, admin_headers)

    upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "image_raw", "subject_item_id": str(item["id"])},
        files={"file": ("image.png", b"\x89PNG\r\n", "image/png")},
    )
    assert upload.status_code == 201

    items = client.get(f"/api/subjects/{item['subject_id']}/items", headers=admin_headers)
    assert items.status_code == 200
    updated_item = next(row for row in items.json() if row["id"] == item["id"])
    assert updated_item["upload_status"] == "uploaded"
    assert updated_item["review_status"] == "unreviewed"

    subject = client.get(f"/api/subjects/{item['subject_id']}", headers=admin_headers)
    assert subject.status_code == 200
    assert subject.json()["data_status"] == "incomplete"

    delete = client.delete(f"/api/files/{upload.json()['id']}", headers=admin_headers)
    assert delete.status_code == 204
    reset_items = client.get(f"/api/subjects/{item['subject_id']}/items", headers=admin_headers)
    reset_item = next(row for row in reset_items.json() if row["id"] == item["id"])
    assert reset_item["upload_status"] == "not_uploaded"

    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    too_large = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "image_raw", "subject_item_id": str(item["id"])},
        files={"file": ("image.png", b"1", "image/png")},
    )
    assert too_large.status_code == 413


def test_file_scope_and_readonly_permissions(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    stage_file_a = create_stage_file(client, admin_headers, "SCOPE_A")
    stage_file_b = create_stage_file(client, admin_headers, "SCOPE_B")
    upload_b = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "raw_pdf", "stage_file_id": str(stage_file_b["id"])},
        files={"file": ("scope.pdf", b"%PDF", "application/pdf")},
    )
    assert upload_b.status_code == 201

    readonly_role_id = role_id_by_name(client, admin_headers, "readonly")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "p4_readonly",
            "password": "Readonly@123",
            "full_name": "P4 只读",
            "email": None,
            "is_active": True,
            "role_ids": [readonly_role_id],
            "project_ids": [stage_file_a["project_id"]],
            "center_ids": [],
        },
    )
    assert create_user.status_code == 201
    readonly_headers = login_headers(client, "p4_readonly", "Readonly@123")

    denied_upload = client.post(
        "/api/files/upload",
        headers=readonly_headers,
        data={"file_category": "raw_pdf", "stage_file_id": str(stage_file_a["id"])},
        files={"file": ("readonly.pdf", b"%PDF", "application/pdf")},
    )
    assert denied_upload.status_code == 403

    denied_download = client.get(
        f"/api/files/{upload_b.json()['id']}/download",
        headers=readonly_headers,
    )
    assert denied_download.status_code == 403
