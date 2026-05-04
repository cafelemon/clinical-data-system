from fastapi.testclient import TestClient


def test_p1_master_data_crud_flow(client: TestClient, admin_headers: dict[str, str]) -> None:
    dictionary_response = client.post(
        "/api/dictionaries",
        headers=admin_headers,
        json={
            "dict_type": "project_status",
            "value": "active",
            "label": "启用",
            "color": "success",
            "sort_order": 1,
            "enabled": True,
        },
    )
    assert dictionary_response.status_code == 201
    dictionary_id = dictionary_response.json()["id"]

    dictionaries_response = client.get(
        "/api/dictionaries?dict_type=project_status",
        headers=admin_headers,
    )
    assert dictionaries_response.status_code == 200
    assert dictionaries_response.json()[0]["label"] == "启用"

    project_ids: list[int] = []
    for name, code in [
        ("小肠项目", "SMALL_INTESTINE"),
        ("结肠项目", "COLON"),
        ("胃部项目", "STOMACH"),
    ]:
        response = client.post(
            "/api/projects",
            headers=admin_headers,
            json={"name": name, "code": code, "description": "", "status": "active"},
        )
        assert response.status_code == 201
        project_ids.append(response.json()["id"])

    duplicate_project = client.post(
        "/api/projects",
        headers=admin_headers,
        json={"name": "重复项目", "code": "COLON", "description": "", "status": "active"},
    )
    assert duplicate_project.status_code == 409

    projects_response = client.get("/api/projects", headers=admin_headers)
    assert projects_response.status_code == 200
    assert [project["name"] for project in projects_response.json()] == [
        "小肠项目",
        "结肠项目",
        "胃部项目",
    ]

    update_project = client.put(
        f"/api/projects/{project_ids[0]}",
        headers=admin_headers,
        json={"description": "P1 验收项目"},
    )
    assert update_project.status_code == 200
    assert update_project.json()["description"] == "P1 验收项目"

    for name, code in [("北京中心", "BJ-01"), ("上海中心", "SH-01")]:
        response = client.post(
            "/api/centers",
            headers=admin_headers,
            json={
                "project_id": project_ids[0],
                "name": name,
                "code": code,
                "contact_person": "临床协调员",
                "status": "active",
                "description": "",
            },
        )
        assert response.status_code == 201

    centers_response = client.get(
        f"/api/projects/{project_ids[0]}/centers",
        headers=admin_headers,
    )
    assert centers_response.status_code == 200
    assert len(centers_response.json()) == 2

    stage_ids: list[int] = []
    for sort_order, name, code in [
        (1, "启动阶段", "STARTUP"),
        (2, "试验进行阶段", "TRIAL"),
        (3, "总结阶段", "CLOSEOUT"),
    ]:
        response = client.post(
            "/api/stages",
            headers=admin_headers,
            json={
                "project_id": project_ids[0],
                "name": name,
                "code": code,
                "sort_order": sort_order,
                "description": "",
            },
        )
        assert response.status_code == 201
        stage_ids.append(response.json()["id"])

    stages_response = client.get(
        f"/api/projects/{project_ids[0]}/stages",
        headers=admin_headers,
    )
    assert stages_response.status_code == 200
    assert [stage["name"] for stage in stages_response.json()] == [
        "启动阶段",
        "试验进行阶段",
        "总结阶段",
    ]

    template_response = client.post(
        "/api/stage-templates",
        headers=admin_headers,
        json={
            "project_id": project_ids[0],
            "stage_id": stage_ids[0],
            "item_name": "伦理批件",
            "item_code": "ETHICS_APPROVAL",
            "required": True,
            "sort_order": 1,
            "description": "启动阶段必备资料",
        },
    )
    assert template_response.status_code == 201

    templates_response = client.get(
        f"/api/stage-templates?project_id={project_ids[0]}&stage_id={stage_ids[0]}",
        headers=admin_headers,
    )
    assert templates_response.status_code == 200
    assert templates_response.json()[0]["item_name"] == "伦理批件"

    dictionary_update = client.put(
        f"/api/dictionaries/{dictionary_id}",
        headers=admin_headers,
        json={"label": "启用中", "enabled": True},
    )
    assert dictionary_update.status_code == 200
    assert dictionary_update.json()["label"] == "启用中"

    dictionary_delete = client.delete(f"/api/dictionaries/{dictionary_id}", headers=admin_headers)
    assert dictionary_delete.status_code == 204
