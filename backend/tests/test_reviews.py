from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings


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


def create_user(
    client: TestClient,
    headers: dict[str, str],
    username: str,
    role: str,
    project_ids: list[int],
    center_ids: list[int] | None = None,
) -> dict[str, str]:
    role_id = role_id_by_name(client, headers, role)
    password = "User@12345"
    response = client.post(
        "/api/users",
        headers=headers,
        json={
            "username": username,
            "password": password,
            "full_name": username,
            "email": None,
            "is_active": True,
            "role_ids": [role_id],
            "project_ids": project_ids,
            "center_ids": center_ids or [],
        },
    )
    assert response.status_code == 201
    return login_headers(client, username, password)


def create_stage_file_bundle(
    client: TestClient,
    headers: dict[str, str],
    suffix: str,
) -> dict:
    project_id = create_project(client, headers, f"P5 项目 {suffix}", f"P5_PROJECT_{suffix}")
    center_id = create_center(client, headers, project_id, f"P5_CENTER_{suffix}")
    stage_id = create_stage(client, headers, project_id, "STARTUP")
    template = client.post(
        "/api/stage-templates",
        headers=headers,
        json={
            "project_id": project_id,
            "stage_id": stage_id,
            "item_name": "伦理批件",
            "item_code": f"ETHICS_{suffix}",
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
    stage_file = response.json()[0]
    stage_file["project_id"] = project_id
    stage_file["center_id"] = center_id
    return stage_file


def create_subject_bundle(
    client: TestClient,
    headers: dict[str, str],
    suffix: str,
) -> tuple[int, int, dict, list[dict]]:
    project_id = create_project(client, headers, f"P5 受试者项目 {suffix}", f"P5_SUBJECT_{suffix}")
    center_id = create_center(client, headers, project_id, f"P5_SUBJECT_CENTER_{suffix}")
    subject = client.post(
        "/api/subjects",
        headers=headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": f"P5-{suffix}-S001",
        },
    )
    assert subject.status_code == 201
    items = client.get(f"/api/subjects/{subject.json()['id']}/items", headers=headers)
    assert items.status_code == 200
    return project_id, center_id, subject.json(), items.json()


def upload_stage_file(client: TestClient, headers: dict[str, str], stage_file_id: int) -> int:
    response = client.post(
        "/api/files/upload",
        headers=headers,
        data={"file_category": "clinical_document", "stage_file_id": str(stage_file_id)},
        files={"file": ("stage.pdf", b"%PDF-stage", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload_subject_item(
    client: TestClient, headers: dict[str, str], item_id: int, name: str
) -> int:
    response = client.post(
        "/api/files/upload",
        headers=headers,
        data={"file_category": "clinical_document", "subject_item_id": str(item_id)},
        files={"file": (name, b"%PDF-item", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def review_action(
    client: TestClient,
    headers: dict[str, str],
    action: str,
    target_type: str,
    target_id: int,
    comment: str | None = None,
):
    payload = {"target_type": target_type, "target_id": target_id}
    if comment is not None:
        payload["comment"] = comment
    return client.post(f"/api/reviews/{action}", headers=headers, json=payload)


def batch_approve(
    client: TestClient,
    headers: dict[str, str],
    targets: list[dict[str, int | str]],
):
    return client.post("/api/reviews/approve-batch", headers=headers, json={"targets": targets})


def test_review_flow_records_stage_file_and_subject_item(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    stage_file = create_stage_file_bundle(client, admin_headers, "FLOW")
    upload_stage_file(client, admin_headers, stage_file["id"])

    stage_files = client.get(
        f"/api/stage-files?project_id={stage_file['project_id']}&center_id={stage_file['center_id']}",
        headers=admin_headers,
    )
    assert stage_files.json()[0]["upload_status"] == "uploaded"
    assert stage_files.json()[0]["review_status"] == "unreviewed"

    submit = review_action(client, admin_headers, "submit", "stage_file", stage_file["id"])
    assert submit.status_code == 201
    assert submit.json()["action"] == "submit"
    assert submit.json()["review_status"] == "pending"

    approve = review_action(client, admin_headers, "approve", "stage_file", stage_file["id"])
    assert approve.status_code == 201
    assert approve.json()["review_status"] == "approved"

    records = client.get(
        f"/api/reviews?target_type=stage_file&target_id={stage_file['id']}",
        headers=admin_headers,
    )
    assert records.status_code == 200
    assert [record["action"] for record in records.json()] == ["approve", "submit"]

    _, _, subject, items = create_subject_bundle(client, admin_headers, "FLOW")
    item = items[0]
    upload_subject_item(client, admin_headers, item["id"], "consent.pdf")
    assert (
        review_action(client, admin_headers, "submit", "subject_item", item["id"]).status_code
        == 201
    )

    reject_without_reason = review_action(
        client, admin_headers, "reject", "subject_item", item["id"]
    )
    assert reject_without_reason.status_code == 400

    reject = review_action(
        client,
        admin_headers,
        "reject",
        "subject_item",
        item["id"],
        "缺少研究者签名",
    )
    assert reject.status_code == 201
    assert reject.json()["comment"] == "缺少研究者签名"

    refreshed_items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    refreshed_item = next(row for row in refreshed_items.json() if row["id"] == item["id"])
    assert refreshed_item["upload_status"] == "supplement_required"
    assert refreshed_item["review_status"] == "rejected"


def test_review_permissions_and_scope(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    stage_file_a = create_stage_file_bundle(client, admin_headers, "SCOPE_A")
    stage_file_b = create_stage_file_bundle(client, admin_headers, "SCOPE_B")
    upload_stage_file(client, admin_headers, stage_file_a["id"])
    upload_stage_file(client, admin_headers, stage_file_b["id"])

    coordinator_headers = create_user(
        client,
        admin_headers,
        "p5_coordinator",
        "clinical_coordinator",
        [stage_file_a["project_id"]],
    )
    reviewer_headers = create_user(
        client,
        admin_headers,
        "p5_reviewer",
        "reviewer",
        [stage_file_a["project_id"]],
    )
    readonly_headers = create_user(
        client,
        admin_headers,
        "p5_readonly",
        "readonly",
        [stage_file_a["project_id"]],
    )

    submit = review_action(client, coordinator_headers, "submit", "stage_file", stage_file_a["id"])
    assert submit.status_code == 201
    assert (
        review_action(
            client, coordinator_headers, "approve", "stage_file", stage_file_a["id"]
        ).status_code
        == 403
    )

    denied_upload = client.post(
        "/api/files/upload",
        headers=reviewer_headers,
        data={"file_category": "clinical_document", "stage_file_id": str(stage_file_a["id"])},
        files={"file": ("reviewer.pdf", b"%PDF", "application/pdf")},
    )
    assert denied_upload.status_code == 403
    assert (
        review_action(
            client, reviewer_headers, "approve", "stage_file", stage_file_a["id"]
        ).status_code
        == 201
    )
    assert (
        review_action(
            client, readonly_headers, "submit", "stage_file", stage_file_a["id"]
        ).status_code
        == 403
    )

    assert (
        review_action(client, admin_headers, "submit", "stage_file", stage_file_b["id"]).status_code
        == 201
    )
    scoped_approve = review_action(
        client, reviewer_headers, "approve", "stage_file", stage_file_b["id"]
    )
    assert scoped_approve.status_code == 403

    scoped_recalculate = client.post(
        "/api/completeness/recalculate",
        headers=reviewer_headers,
        json={"project_id": stage_file_b["project_id"]},
    )
    assert scoped_recalculate.status_code == 403


def test_batch_approve_auto_submits_pending_targets_and_skips(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    uploaded_stage_file = create_stage_file_bundle(client, admin_headers, "BATCH_UPLOADED")
    empty_stage_file = create_stage_file_bundle(client, admin_headers, "BATCH_EMPTY")
    upload_stage_file(client, admin_headers, uploaded_stage_file["id"])

    _, _, subject, items = create_subject_bundle(client, admin_headers, "BATCH")
    pending_item = items[0]
    empty_item = items[1]
    upload_subject_item(client, admin_headers, pending_item["id"], "pending-consent.pdf")
    assert (
        review_action(
            client,
            admin_headers,
            "submit",
            "subject_item",
            pending_item["id"],
        ).status_code
        == 201
    )

    response = batch_approve(
        client,
        admin_headers,
        [
            {"target_type": "stage_file", "target_id": uploaded_stage_file["id"]},
            {"target_type": "stage_file", "target_id": empty_stage_file["id"]},
            {"target_type": "subject_item", "target_id": pending_item["id"]},
            {"target_type": "subject_item", "target_id": empty_item["id"]},
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["approved_count"] == 2
    assert body["skipped_count"] == 2
    results = {(row["target_type"], row["target_id"]): row for row in body["results"]}
    assert results[("stage_file", uploaded_stage_file["id"])]["submitted"] is True
    assert results[("stage_file", uploaded_stage_file["id"])]["approved"] is True
    assert results[("subject_item", pending_item["id"])]["submitted"] is False
    assert results[("subject_item", pending_item["id"])]["approved"] is True
    assert results[("stage_file", empty_stage_file["id"])]["status"] == "skipped"
    assert results[("subject_item", empty_item["id"])]["status"] == "skipped"

    stage_files = client.get(
        (
            f"/api/stage-files?project_id={uploaded_stage_file['project_id']}"
            f"&center_id={uploaded_stage_file['center_id']}"
        ),
        headers=admin_headers,
    )
    assert stage_files.status_code == 200
    refreshed_stage_file = next(
        row for row in stage_files.json() if row["id"] == uploaded_stage_file["id"]
    )
    assert refreshed_stage_file["review_status"] == "approved"

    refreshed_items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    assert refreshed_items.status_code == 200
    refreshed_pending_item = next(
        row for row in refreshed_items.json() if row["id"] == pending_item["id"]
    )
    assert refreshed_pending_item["review_status"] == "approved"

    stage_records = client.get(
        f"/api/reviews?target_type=stage_file&target_id={uploaded_stage_file['id']}",
        headers=admin_headers,
    )
    assert stage_records.status_code == 200
    assert [record["action"] for record in stage_records.json()] == ["approve", "submit"]

    logs = client.get(
        "/api/operation-logs?action=review.approve_batch",
        headers=admin_headers,
    )
    assert logs.status_code == 200
    assert logs.json()["total"] == 1


def test_batch_approve_requires_review_permission(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    stage_file = create_stage_file_bundle(client, admin_headers, "BATCH_PERMISSION")
    upload_stage_file(client, admin_headers, stage_file["id"])
    coordinator_headers = create_user(
        client,
        admin_headers,
        "p5_batch_coordinator",
        "clinical_coordinator",
        [stage_file["project_id"]],
    )

    response = batch_approve(
        client,
        coordinator_headers,
        [{"target_type": "stage_file", "target_id": stage_file["id"]}],
    )

    assert response.status_code == 403


def test_subject_completeness_recalculate_scenarios(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id, center_id, subject, items = create_subject_bundle(client, admin_headers, "COMPLETE")

    initial = client.post(
        "/api/completeness/recalculate",
        headers=admin_headers,
        json={"subject_id": subject["id"]},
    )
    assert initial.status_code == 200
    assert initial.json()["subjects"]["incomplete"] == 1

    first_file_id = upload_subject_item(client, admin_headers, items[0]["id"], "item-0.pdf")
    one_uploaded = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert one_uploaded.json()["data_status"] == "incomplete"

    for index, item in enumerate(items[1:], start=1):
        upload_subject_item(client, admin_headers, item["id"], f"item-{index}.pdf")
    all_uploaded = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert all_uploaded.json()["data_status"] == "checking"

    for item in items:
        assert (
            review_action(client, admin_headers, "submit", "subject_item", item["id"]).status_code
            == 201
        )
        assert (
            review_action(client, admin_headers, "approve", "subject_item", item["id"]).status_code
            == 201
        )
    complete = client.post(
        "/api/completeness/recalculate",
        headers=admin_headers,
        json={"project_id": project_id, "center_id": center_id},
    )
    assert complete.status_code == 200
    assert complete.json()["subjects"]["complete"] == 1
    completed_subject = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert completed_subject.json()["data_status"] == "complete"

    replace = client.post(
        f"/api/files/{first_file_id}/replace",
        headers=admin_headers,
        data={"change_note": "补充版本"},
        files={"file": ("item-0-v2.pdf", b"%PDF-v2", "application/pdf")},
    )
    assert replace.status_code == 200
    checking_subject = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert checking_subject.json()["data_status"] == "checking"

    assert (
        review_action(client, admin_headers, "submit", "subject_item", items[0]["id"]).status_code
        == 201
    )
    reject = review_action(
        client,
        admin_headers,
        "reject",
        "subject_item",
        items[0]["id"],
        "补充材料不一致",
    )
    assert reject.status_code == 201
    rejected_summary = client.get(
        f"/api/completeness/summary?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    )
    assert rejected_summary.status_code == 200
    assert rejected_summary.json()["subjects"]["incomplete"] == 1
