from fastapi.testclient import TestClient

from app.core.config import settings


def create_project(client: TestClient, headers: dict[str, str], code: str) -> int:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={"name": f"P12 {code}", "code": code, "description": "", "status": "active"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_center(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    code: str,
) -> int:
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


def review_action(
    client: TestClient,
    headers: dict[str, str],
    action: str,
    target_type: str,
    target_id: int,
) -> None:
    payload = {"target_type": target_type, "target_id": target_id}
    response = client.post(f"/api/reviews/{action}", headers=headers, json=payload)
    assert response.status_code == 201


def test_stage_options_and_project_level_secondary_stage_controls(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "P12_STAGE")

    options = client.get("/api/stage-options", headers=admin_headers)
    assert options.status_code == 200
    assert [group["phase_code"] for group in options.json()] == ["STARTUP", "TRIAL", "CLOSEOUT"]
    assert options.json()[0]["phase_name"] == "试验准备阶段"
    assert options.json()[0]["options"][0]["name"] == "资料准备"

    startup_stages = client.get(
        f"/api/stages?project_id={project_id}&phase_code=STARTUP",
        headers=admin_headers,
    )
    assert startup_stages.status_code == 200
    assert len(startup_stages.json()) == 6
    assert all(stage["parent_id"] for stage in startup_stages.json())
    assert {stage["enabled"] for stage in startup_stages.json()} == {True}

    unknown = client.post(
        "/api/stages",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "phase_code": "STARTUP",
            "option_code": "CUSTOM_STAGE",
            "sort_order": 99,
        },
    )
    assert unknown.status_code == 400

    stage = startup_stages.json()[0]
    update = client.put(
        f"/api/stages/{stage['id']}",
        headers=admin_headers,
        json={"enabled": False, "sort_order": 99, "description": "暂停"},
    )
    assert update.status_code == 200
    assert update.json()["enabled"] is False
    assert update.json()["sort_order"] == 99

    parents = client.get(
        f"/api/projects/{project_id}/stages",
        headers=admin_headers,
    )
    assert parents.status_code == 200
    parent_id = parents.json()[0]["id"]
    assert client.delete(f"/api/stages/{parent_id}", headers=admin_headers).status_code == 400


def test_template_scopes_dataset_groups_and_subject_generation(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers, "P12_DATASET")
    center_id = create_center(client, admin_headers, project_id, "P12_CENTER")

    startup_stage = client.get(
        f"/api/stages?project_id={project_id}&phase_code=STARTUP",
        headers=admin_headers,
    ).json()[0]
    trial_stages = client.get(
        f"/api/stages?project_id={project_id}&phase_code=TRIAL",
        headers=admin_headers,
    ).json()
    disabled_trial_stage = trial_stages[-1]
    assert client.put(
        f"/api/stages/{disabled_trial_stage['id']}",
        headers=admin_headers,
        json={"enabled": False},
    ).status_code == 200

    center_template = client.post(
        "/api/stage-templates",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "stage_id": startup_stage["id"],
            "template_scope": "center_file",
            "item_name": "伦理批件",
            "item_code": "ETHICS_APPROVAL",
            "required": True,
            "sort_order": 1,
            "description": "",
        },
    )
    assert center_template.status_code == 201

    wrong_scope = client.post(
        "/api/stage-templates",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "stage_id": startup_stage["id"],
            "template_scope": "subject_item",
            "item_name": "错误用途",
            "item_code": "WRONG_SCOPE",
            "required": True,
            "sort_order": 1,
            "description": "",
        },
    )
    assert wrong_scope.status_code == 400

    dataset = client.get(
        f"/api/clinical-datasets?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    )
    assert dataset.status_code == 200
    assert len(dataset.json()["startup_file_groups"]) == 6
    assert len(dataset.json()["startup_files"]) == 27
    assert len(dataset.json()["ssu_progress"]) == 5
    assert [record["stage_code"] for record in dataset.json()["ssu_progress"]] == [
        "SSU_PROJECT_APPROVAL",
        "SSU_ETHICS",
        "SSU_AGREEMENT_SIGNING",
        "SSU_PROVINCIAL_FILING",
        "SSU_STARTUP_MEETING",
    ]
    first_ssu = dataset.json()["ssu_progress"][0]
    update_ssu = client.patch(
        f"/api/clinical-datasets/ssu-progress/{first_ssu['id']}",
        headers=admin_headers,
        json={
            "status": "completed",
            "submitted_at": "2026-05-01",
            "approved_at": "2026-05-02",
            "completed_at": "2026-05-03",
            "version_info": "v1",
            "file_checklist": "申请表、方案",
            "summary": "立项完成",
            "fee_detail": "无需付款",
            "notes": "已核对",
        },
    )
    assert update_ssu.status_code == 200
    assert update_ssu.json()["status"] == "completed"
    assert update_ssu.json()["version_info"] == "v1"
    invalid_ssu = client.post(
        "/api/clinical-datasets/ssu-progress",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "stage_code": "STARTUP_MATERIALS",
            "status": "not_started",
        },
    )
    assert invalid_ssu.status_code == 400
    assert dataset.json()["startup_file_groups"][0]["stage"]["code"] == "STARTUP_MATERIALS"
    assert len(dataset.json()["startup_file_groups"][0]["files"]) == 27
    assert dataset.json()["trial_file_groups"][0]["stage"]["code"] == "TRIAL_MATERIALS"
    assert len(dataset.json()["trial_files"]) == 19
    first_file = next(
        file for file in dataset.json()["startup_files"] if file["file_type"] == "ETHICS_APPROVAL"
    )
    optional_file = next(
        file
        for file in dataset.json()["startup_files"]
        if file["file_type"] == "STARTUP_005_RECRUITMENT_DOCUMENTS"
    )
    assert first_file["file_name"] == "伦理批件"
    assert first_file["completeness_status"] == "incomplete"
    assert optional_file["required"] is False
    assert optional_file["completeness_status"] == "incomplete"

    optional_applicability = client.patch(
        f"/api/stage-files/{optional_file['id']}/applicability",
        headers=admin_headers,
        json={"not_applicable": True, "reason": "本中心无招募宣传材料"},
    )
    assert optional_applicability.status_code == 200
    assert optional_applicability.json()["completeness_status"] == "complete"

    completeness = client.get(
        f"/api/completeness/summary?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    )
    assert completeness.status_code == 200
    assert {
        stage["stage_name"] for stage in completeness.json()["stages"]
    } >= {"试验准备阶段资料准备", "试验结束阶段资料准备"}

    upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "clinical_document", "stage_file_id": str(first_file["id"])},
        files={"file": ("ethics.pdf", b"%PDF-ethics", "application/pdf")},
    )
    assert upload.status_code == 201
    review_action(client, admin_headers, "submit", "stage_file", first_file["id"])
    review_action(client, admin_headers, "approve", "stage_file", first_file["id"])

    refreshed = client.get(
        f"/api/clinical-datasets?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    ).json()
    refreshed_file = next(
        file for file in refreshed["startup_files"] if file["file_type"] == "ETHICS_APPROVAL"
    )
    assert refreshed_file["uploaded_by"] is not None
    assert refreshed_file["reviewer_id"] is not None
    assert refreshed_file["completeness_status"] == "complete"

    subject = client.post(
        "/api/subjects",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "P12-S001",
            "subject_arm": "experimental",
        },
    )
    assert subject.status_code == 201
    sections = client.get(
        f"/api/subjects/{subject.json()['id']}/sections",
        headers=admin_headers,
    )
    assert sections.status_code == 200
    section_codes = [section["section_code"] for section in sections.json()]
    assert section_codes == [
        "V1_SCREENING_VISIT",
        "V2_EXPERIMENTAL_FOLLOWUP_VISIT",
    ]

    items = client.get(f"/api/subjects/{subject.json()['id']}/items", headers=admin_headers)
    assert items.status_code == 200
    assert all(item["stage_template_id"] for item in items.json())
    item_codes = {item["item_code"] for item in items.json()}
    item_names = {item["item_name"] for item in items.json()}
    assert "V1_INFORMED_CONSENT" in item_codes
    assert "知情同意书" in item_names
    assert "SCREENING_CONSENT" not in item_codes
    assert {"uploaded_by", "reviewer_id", "completeness_status"}.issubset(items.json()[0])


def test_deleted_default_subject_templates_are_not_regenerated(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "P12_DELETE_DEFAULT")
    center_id = create_center(client, admin_headers, project_id, "P12_DELETE_DEFAULT")
    templates = client.get(
        f"/api/stage-templates?project_id={project_id}&template_scope=subject_item",
        headers=admin_headers,
    )
    assert templates.status_code == 200
    target = next(
        template
        for template in templates.json()
        if template["item_code"] == "V2_BOWEL_PREPARATION"
    )

    delete = client.delete(f"/api/stage-templates/{target['id']}", headers=admin_headers)
    assert delete.status_code == 204

    refreshed = client.get(
        f"/api/stage-templates?project_id={project_id}&template_scope=subject_item",
        headers=admin_headers,
    )
    assert refreshed.status_code == 200
    assert "V2_BOWEL_PREPARATION" not in {template["item_code"] for template in refreshed.json()}

    subject = client.post(
        "/api/subjects",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "P12-DELETE-S001",
            "subject_arm": "experimental",
        },
    )
    assert subject.status_code == 201
    items = client.get(f"/api/subjects/{subject.json()['id']}/items", headers=admin_headers)
    assert items.status_code == 200
    assert "V2_BOWEL_PREPARATION" not in {item["item_code"] for item in items.json()}
