from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.test_dashboard import (
    create_center,
    create_project,
    create_user,
    prepare_dashboard_dataset,
)
from tests.test_image_data import image_rows, make_zip, upload_file


def test_dashboard_v323_overview_all_project_and_center_scopes(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    dataset = prepare_dashboard_dataset(client, admin_headers)
    project_id = dataset["project_id"]
    center_a_id = dataset["center_a_id"]
    today = date.today()

    milestone = client.post(
        "/api/dashboard/v31/milestones",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_a_id,
            "milestone_name": "启动时间",
            "planned_date": (today - timedelta(days=1)).isoformat(),
            "status": "in_progress",
        },
    )
    assert milestone.status_code == 201
    enrollment = client.post(
        "/api/dashboard/v31/enrollment-plans",
        headers=admin_headers,
        json={
            "project_id": project_id,
            "center_id": center_a_id,
            "contract_count": 20,
            "next_week_plan_count": 3,
            "current_enrolled_count": 8,
        },
    )
    assert enrollment.status_code == 201

    all_scope = client.get("/api/dashboard/v323/overview", headers=admin_headers)
    assert all_scope.status_code == 200
    all_body = all_scope.json()
    assert all_body["scope"]["level"] == "all"
    assert all_body["kpis"]["project_count"] >= 1
    assert all_body["kpis"]["subject_count"] >= 3
    assert all_body["enrollment"]["contract_count"] == 20
    assert all_body["manual_supplements"]["counts"]["milestones"] == 1
    assert all_body["warnings"][0]["warning_level"] == "overdue"

    project_scope = client.get(
        f"/api/dashboard/v323/overview?project_id={project_id}",
        headers=admin_headers,
    )
    assert project_scope.status_code == 200
    assert project_scope.json()["scope"]["level"] == "project"
    assert project_scope.json()["kpis"]["center_count"] == 2

    center_scope = client.get(
        f"/api/dashboard/v323/overview?project_id={project_id}&center_id={center_a_id}",
        headers=admin_headers,
    )
    assert center_scope.status_code == 200
    center_body = center_scope.json()
    assert center_body["scope"]["level"] == "center"
    assert center_body["kpis"]["center_count"] == 1
    assert center_body["enrollment"]["planned_next_week"] == 3


def test_dashboard_v343_overview_counts_required_image_data(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    dataset = prepare_dashboard_dataset(client, admin_headers)
    project_id = dataset["project_id"]
    center_a_id = dataset["center_a_id"]

    initial = client.get(
        f"/api/dashboard/v323/overview?project_id={project_id}",
        headers=admin_headers,
    )
    assert initial.status_code == 200
    initial_body = initial.json()
    assert initial_body["image_data"]["raw"] == {
        "total_count": 3,
        "uploaded_count": 0,
        "not_uploaded_count": 3,
        "coverage_rate": 0.0,
    }
    assert initial_body["image_data"]["report"]["not_uploaded_count"] == 3
    assert initial_body["image_data"]["enhanced"]["not_uploaded_count"] == 3
    assert initial_body["image_data"]["required"] == {
        "complete": 0,
        "checking": 0,
        "incomplete": 6,
    }

    raw_record = next(
        row["record"]
        for row in image_rows(client, admin_headers, project_id, center_a_id, "raw")
        if row["screening_no"] == "P6-A-001"
    )
    report_record = next(
        row["record"]
        for row in image_rows(client, admin_headers, project_id, center_a_id, "report")
        if row["screening_no"] == "P6-A-001"
    )
    enhanced_record = next(
        row["record"]
        for row in image_rows(client, admin_headers, project_id, center_a_id, "enhanced")
        if row["screening_no"] == "P6-A-001"
    )

    raw_upload = upload_file(
        client,
        admin_headers,
        raw_record["id"],
        "raw.zip",
        make_zip({"P6-A-001/a.jpg": b"raw"}),
        "application/zip",
    )
    assert raw_upload.status_code == 200
    report_upload = upload_file(
        client,
        admin_headers,
        report_record["id"],
        "report.pdf",
        b"%PDF-1.4",
        "application/pdf",
    )
    assert report_upload.status_code == 200

    after_required = client.get(
        f"/api/dashboard/v323/overview?project_id={project_id}",
        headers=admin_headers,
    )
    assert after_required.status_code == 200
    required_body = after_required.json()
    assert required_body["image_data"]["raw"]["uploaded_count"] == 1
    assert required_body["image_data"]["report"]["uploaded_count"] == 1
    assert required_body["image_data"]["enhanced"]["uploaded_count"] == 0
    assert required_body["image_data"]["required"] == {
        "complete": 2,
        "checking": 0,
        "incomplete": 4,
    }
    assert required_body["completeness"]["complete"] == initial_body["completeness"]["complete"] + 2
    assert (
        required_body["completeness"]["incomplete"]
        == initial_body["completeness"]["incomplete"] - 2
    )

    center_scope = client.get(
        f"/api/dashboard/v323/overview?project_id={project_id}&center_id={center_a_id}",
        headers=admin_headers,
    )
    assert center_scope.status_code == 200
    center_body = center_scope.json()
    assert center_body["image_data"]["required"] == {
        "complete": 2,
        "checking": 0,
        "incomplete": 2,
    }
    center_a = center_body["centers"][0]
    assert center_a["image_required_complete"] == 2
    assert center_a["image_required_incomplete"] == 2
    assert center_a["image_required_coverage_rate"] == 50.0

    enhanced_upload = upload_file(
        client,
        admin_headers,
        enhanced_record["id"],
        "enhanced.zip",
        make_zip({"P6-A-001/a.jpg": b"enhanced"}),
        "application/zip",
    )
    assert enhanced_upload.status_code == 200

    after_enhanced = client.get(
        f"/api/dashboard/v323/overview?project_id={project_id}",
        headers=admin_headers,
    )
    assert after_enhanced.status_code == 200
    enhanced_body = after_enhanced.json()
    assert enhanced_body["image_data"]["enhanced"]["uploaded_count"] == 1
    assert enhanced_body["image_data"]["required"] == required_body["image_data"]["required"]
    assert enhanced_body["completeness"] == required_body["completeness"]


def test_dashboard_v31_write_requires_admin_or_project_manager(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "V323_PERM")
    center_id = create_center(client, admin_headers, project_id, "V323_PERM")
    payload = {
        "project_id": project_id,
        "center_id": center_id,
        "milestone_name": "合同完成",
    }

    center_manager_headers = create_user(
        client,
        admin_headers,
        "v323_center_manager",
        "center_manager",
        center_ids=[center_id],
    )
    denied_center_manager = client.post(
        "/api/dashboard/v31/milestones",
        headers=center_manager_headers,
        json=payload,
    )
    assert denied_center_manager.status_code == 403

    coordinator_headers = create_user(
        client,
        admin_headers,
        "v323_coordinator",
        "clinical_coordinator",
        project_ids=[project_id],
    )
    denied_coordinator = client.post(
        "/api/dashboard/v31/milestones",
        headers=coordinator_headers,
        json=payload,
    )
    assert denied_coordinator.status_code == 403

    project_manager_headers = create_user(
        client,
        admin_headers,
        "v323_project_manager",
        "project_manager",
        project_ids=[project_id],
    )
    allowed = client.post(
        "/api/dashboard/v31/milestones",
        headers=project_manager_headers,
        json=payload,
    )
    assert allowed.status_code == 201

    other_project_id = create_project(client, admin_headers, "V323_OTHER")
    other_center_id = create_center(client, admin_headers, other_project_id, "V323_OTHER")
    denied_other_project = client.post(
        "/api/dashboard/v31/milestones",
        headers=project_manager_headers,
        json={
            "project_id": other_project_id,
            "center_id": other_center_id,
            "milestone_name": "伦理批件",
        },
    )
    assert denied_other_project.status_code == 403
