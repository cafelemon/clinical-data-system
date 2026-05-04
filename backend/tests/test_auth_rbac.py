from fastapi.testclient import TestClient


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def role_id_by_name(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.get("/api/roles", headers=headers)
    assert response.status_code == 200
    roles = response.json()
    return next(role["id"] for role in roles if role["name"] == name)


def create_project(client: TestClient, headers: dict[str, str], name: str, code: str) -> int:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={"name": name, "code": code, "description": "", "status": "active"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_login_me_and_unauthorized_access(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    no_token_response = client.get("/api/projects")
    assert no_token_response.status_code == 401

    bad_login = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401

    me_response = client.get("/api/auth/me", headers=admin_headers)
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["username"] == "admin"
    assert me["is_admin"] is True
    assert "users:write" in me["permissions"]


def test_rbac_write_permission_and_project_scope(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_a_id = create_project(client, admin_headers, "项目 A", "PROJECT_A")
    project_b_id = create_project(client, admin_headers, "项目 B", "PROJECT_B")

    readonly_role_id = role_id_by_name(client, admin_headers, "readonly")
    create_readonly = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "readonly_user",
            "password": "Readonly@123",
            "full_name": "只读用户",
            "email": None,
            "is_active": True,
            "role_ids": [readonly_role_id],
            "project_ids": [project_a_id],
            "center_ids": [],
        },
    )
    assert create_readonly.status_code == 201

    readonly_headers = login_headers(client, "readonly_user", "Readonly@123")
    scoped_projects = client.get("/api/projects", headers=readonly_headers)
    assert scoped_projects.status_code == 200
    assert [project["id"] for project in scoped_projects.json()] == [project_a_id]

    forbidden_create = client.post(
        "/api/projects",
        headers=readonly_headers,
        json={"name": "项目 C", "code": "PROJECT_C", "description": "", "status": "active"},
    )
    assert forbidden_create.status_code == 403

    project_manager_role_id = role_id_by_name(client, admin_headers, "project_manager")
    create_manager = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "project_manager",
            "password": "Manager@123",
            "full_name": "项目负责人",
            "email": None,
            "is_active": True,
            "role_ids": [project_manager_role_id],
            "project_ids": [project_a_id],
            "center_ids": [],
        },
    )
    assert create_manager.status_code == 201

    manager_headers = login_headers(client, "project_manager", "Manager@123")
    update_allowed = client.put(
        f"/api/projects/{project_a_id}",
        headers=manager_headers,
        json={"description": "授权项目可维护"},
    )
    assert update_allowed.status_code == 200

    update_denied = client.put(
        f"/api/projects/{project_b_id}",
        headers=manager_headers,
        json={"description": "越权项目"},
    )
    assert update_denied.status_code == 403


def test_center_scope_filters_centers_and_parent_project(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "中心范围项目", "CENTER_SCOPE_PROJECT")
    center_a = client.post(
        "/api/centers",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "name": "中心 A",
            "code": "CENTER_A",
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    ).json()["id"]
    client.post(
        "/api/centers",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "name": "中心 B",
            "code": "CENTER_B",
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    )

    center_manager_role_id = role_id_by_name(client, admin_headers, "center_manager")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "center_manager",
            "password": "Center@123",
            "full_name": "中心负责人",
            "email": None,
            "is_active": True,
            "role_ids": [center_manager_role_id],
            "project_ids": [],
            "center_ids": [center_a],
        },
    )
    assert create_user.status_code == 201

    center_headers = login_headers(client, "center_manager", "Center@123")
    projects = client.get("/api/projects", headers=center_headers)
    assert projects.status_code == 200
    assert [project["id"] for project in projects.json()] == [project_id]

    centers = client.get(f"/api/projects/{project_id}/centers", headers=center_headers)
    assert centers.status_code == 200
    assert [center["id"] for center in centers.json()] == [center_a]

