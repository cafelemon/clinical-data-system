from fastapi.testclient import TestClient


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
            "gender": "女",
            "age": 42,
            "enrolled_at": "2026-05-04",
            "review_status": "unreviewed",
            "data_status": "incomplete",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_clinical_dataset_flow_materializes_files_and_subject_items(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
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
    assert [item["file_name"] for item in first_stage_files.json()] == ["伦理批件"]

    second_stage_files = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_id}&stage_id={startup_stage_id}",
        headers=admin_headers,
    )
    assert second_stage_files.status_code == 200
    assert [item["id"] for item in second_stage_files.json()] == [
        item["id"] for item in first_stage_files.json()
    ]

    subject = create_subject(client, admin_headers, project_id, center_id, "P3-S001")
    duplicate = client.post(
        "/api/subjects",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "P3-S001",
        },
    )
    assert duplicate.status_code == 409

    sections = client.get(f"/api/subjects/{subject['id']}/sections", headers=admin_headers)
    assert sections.status_code == 200
    assert [section["name"] for section in sections.json()] == [
        "筛选阶段",
        "入组与检查准备阶段",
        "检查执行阶段",
        "检查后早期随访阶段",
        "异常或延迟随访阶段",
        "试验完成阶段",
    ]

    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    assert items.status_code == 200
    assert len(items.json()) == 15

    item_id = items.json()[0]["id"]
    update_item = client.put(
        f"/api/subject-items/{item_id}",
        headers=admin_headers,
        json={"upload_status": "uploaded", "review_status": "approved", "remark": "已核对"},
    )
    assert update_item.status_code == 200
    assert update_item.json()["remark"] == "已核对"

    dataset = client.get(
        f"/api/clinical-datasets?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    )
    assert dataset.status_code == 200
    assert dataset.json()["stage_file_count"] == 2
    assert dataset.json()["subject_count"] == 1


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

    denied_detail = client.get(f"/api/subjects/{subject_b['id']}", headers=readonly_headers)
    assert denied_detail.status_code == 403

    denied_write = client.post(
        "/api/subjects",
        headers=readonly_headers,
        json={
            "project_id": project_a_id,
            "center_id": center_a_id,
            "screening_no": "A-S002",
        },
    )
    assert denied_write.status_code == 403
