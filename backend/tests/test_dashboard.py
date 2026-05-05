from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import (
    DATA_COMPLETE,
    DATA_INCOMPLETE,
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    UPLOAD_SUPPLEMENT_REQUIRED,
    UPLOAD_UPLOADED,
)
from app.core.database import get_db
from app.models import StageFile, Subject, SubjectItem


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


def create_project(client: TestClient, headers: dict[str, str], suffix: str) -> int:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": f"P6 项目 {suffix}",
            "code": f"P6_PROJECT_{suffix}",
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
            "name": f"中心 {suffix}",
            "code": f"P6_CENTER_{suffix}",
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_stage_and_template(client: TestClient, headers: dict[str, str], project_id: int) -> int:
    stage = client.post(
        "/api/stages",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "启动阶段",
            "code": "STARTUP",
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
            "item_code": "ETHICS_APPROVAL",
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
    enrolled_at: date | None = None,
) -> dict:
    payload = {
        "project_id": project_id,
        "center_id": center_id,
        "screening_no": screening_no,
    }
    if enrolled_at is not None:
        payload["enrolled_at"] = enrolled_at.isoformat()
    response = client.post("/api/subjects", headers=headers, json=payload)
    assert response.status_code == 201
    return response.json()


def mark_subject_complete(db: Session, subject_id: int, completed_at: datetime) -> None:
    subject = db.get(Subject, subject_id)
    assert subject is not None
    subject.data_status = DATA_COMPLETE
    subject.review_status = REVIEW_APPROVED
    subject.completed_at = completed_at
    for item in db.scalars(select(SubjectItem).where(SubjectItem.subject_id == subject_id)):
        item.upload_status = UPLOAD_UPLOADED
        item.review_status = REVIEW_APPROVED
    db.commit()


def prepare_dashboard_dataset(
    client: TestClient,
    admin_headers: dict[str, str],
) -> dict:
    today = date.today()
    project_id = create_project(client, admin_headers, "DASH")
    center_a_id = create_center(client, admin_headers, project_id, "A")
    center_b_id = create_center(client, admin_headers, project_id, "B")
    stage_id = create_stage_and_template(client, admin_headers, project_id)

    stage_files = client.get(
        f"/api/stage-files?project_id={project_id}&center_id={center_a_id}&stage_id={stage_id}",
        headers=admin_headers,
    )
    assert stage_files.status_code == 200

    subject_a = create_subject(
        client,
        admin_headers,
        project_id,
        center_a_id,
        "P6-A-001",
        today - timedelta(days=25),
    )
    subject_b = create_subject(
        client,
        admin_headers,
        project_id,
        center_a_id,
        "P6-A-002",
        today - timedelta(days=2),
    )
    subject_c = create_subject(client, admin_headers, project_id, center_b_id, "P6-B-001")

    with db_session(client) as db:
        stage_file = db.get(StageFile, stage_files.json()[0]["id"])
        assert stage_file is not None
        stage_file.upload_status = UPLOAD_UPLOADED
        stage_file.review_status = REVIEW_APPROVED
        mark_subject_complete(
            db,
            subject_a["id"],
            datetime.combine(today - timedelta(days=21), time(10, 0), UTC),
        )
        mark_subject_complete(
            db,
            subject_b["id"],
            datetime.combine(today, time(10, 0), UTC),
        )

    return {
        "project_id": project_id,
        "center_a_id": center_a_id,
        "center_b_id": center_b_id,
        "subject_c_id": subject_c["id"],
    }


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


def test_completed_at_is_set_once_and_not_cleared_on_regression(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "COMPLETE_AT")
    center_id = create_center(client, admin_headers, project_id, "COMPLETE_AT")
    subject = create_subject(client, admin_headers, project_id, center_id, "P6-COMPLETE-001")

    with db_session(client) as db:
        for item in db.scalars(
            select(SubjectItem).where(SubjectItem.subject_id == subject["id"])
        ):
            item.upload_status = UPLOAD_UPLOADED
            item.review_status = REVIEW_APPROVED
        db.commit()

    recalculate = client.post(
        "/api/completeness/recalculate",
        headers=admin_headers,
        json={"subject_id": subject["id"]},
    )
    assert recalculate.status_code == 200

    completed = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert completed.status_code == 200
    assert completed.json()["data_status"] == DATA_COMPLETE
    completed_at = completed.json()["completed_at"]
    assert completed_at is not None

    with db_session(client) as db:
        first_item = db.scalar(
            select(SubjectItem)
            .where(SubjectItem.subject_id == subject["id"])
            .order_by(SubjectItem.id)
        )
        assert first_item is not None
        first_item.upload_status = UPLOAD_SUPPLEMENT_REQUIRED
        first_item.review_status = REVIEW_REJECTED
        db.commit()

    recalculate_again = client.post(
        "/api/completeness/recalculate",
        headers=admin_headers,
        json={"subject_id": subject["id"]},
    )
    assert recalculate_again.status_code == 200
    regressed = client.get(f"/api/subjects/{subject['id']}", headers=admin_headers)
    assert regressed.json()["data_status"] == DATA_INCOMPLETE
    assert regressed.json()["completed_at"] == completed_at


def test_dashboard_project_metrics_distributions_and_trend(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    data = prepare_dashboard_dataset(client, admin_headers)
    project_id = data["project_id"]

    summary = client.get(f"/api/dashboard/project/{project_id}", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["completed_subject_count"] == 2
    assert summary.json()["visible_center_count"] == 2
    assert summary.json()["subject_count"] == 3
    assert summary.json()["average_days_per_subject"] == 3.0
    assert summary.json()["median_days_per_subject"] == 3.0
    assert summary.json()["project_days"] >= 1

    centers = client.get(f"/api/dashboard/project/{project_id}/centers", headers=admin_headers)
    assert centers.status_code == 200
    assert [center["subject_count"] for center in centers.json()] == [2, 1]
    assert centers.json()[0]["completion_rate"] == 100.0
    assert centers.json()[1]["completeness_status"] == DATA_INCOMPLETE

    review_status = client.get(
        f"/api/dashboard/project/{project_id}/review-status",
        headers=admin_headers,
    )
    assert review_status.status_code == 200
    assert review_status.json()["approved"] == 31
    assert review_status.json()["unreviewed"] == 16

    completeness = client.get(
        f"/api/dashboard/project/{project_id}/completeness",
        headers=admin_headers,
    )
    assert completeness.status_code == 200
    assert completeness.json()["stage_files"] == {
        "complete": 1,
        "checking": 0,
        "incomplete": 1,
    }
    assert completeness.json()["subjects"] == {
        "complete": 2,
        "checking": 0,
        "incomplete": 1,
    }

    weekly_trend = client.get(
        f"/api/dashboard/project/{project_id}/trend?granularity=week",
        headers=admin_headers,
    )
    assert weekly_trend.status_code == 200
    assert weekly_trend.json()[0]["completed_count"] == 1
    assert weekly_trend.json()[-1]["completed_count"] == 1
    assert any(point["completed_count"] == 0 for point in weekly_trend.json()[1:-1])

    monthly_trend = client.get(
        f"/api/dashboard/project/{project_id}/trend?granularity=month",
        headers=admin_headers,
    )
    assert monthly_trend.status_code == 200
    assert sum(point["completed_count"] for point in monthly_trend.json()) == 2


def test_dashboard_scope_and_permission(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    data = prepare_dashboard_dataset(client, admin_headers)
    other_project_id = create_project(client, admin_headers, "DENIED")
    center_headers = create_user(
        client,
        admin_headers,
        "p6_center_manager",
        "center_manager",
        center_ids=[data["center_a_id"]],
    )

    scoped_summary = client.get(
        f"/api/dashboard/project/{data['project_id']}",
        headers=center_headers,
    )
    assert scoped_summary.status_code == 200
    assert scoped_summary.json()["visible_center_count"] == 1
    assert scoped_summary.json()["subject_count"] == 2

    scoped_centers = client.get(
        f"/api/dashboard/project/{data['project_id']}/centers",
        headers=center_headers,
    )
    assert scoped_centers.status_code == 200
    assert [center["center_id"] for center in scoped_centers.json()] == [data["center_a_id"]]

    denied_project = client.get(
        f"/api/dashboard/project/{other_project_id}",
        headers=center_headers,
    )
    assert denied_project.status_code == 403

    master_read_id = permission_id_by_code(client, admin_headers, "master_data:read")
    role = client.post(
        "/api/roles",
        headers=admin_headers,
        json={
            "name": "p6_no_dashboard",
            "label": "无看板",
            "description": "",
            "permission_ids": [master_read_id],
        },
    )
    assert role.status_code == 201
    user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "p6_no_dashboard",
            "password": "User@12345",
            "full_name": "无看板",
            "email": None,
            "is_active": True,
            "role_ids": [role.json()["id"]],
            "project_ids": [data["project_id"]],
            "center_ids": [],
        },
    )
    assert user.status_code == 201
    no_dashboard_headers = login_headers(client, "p6_no_dashboard", "User@12345")
    forbidden = client.get(
        f"/api/dashboard/project/{data['project_id']}",
        headers=no_dashboard_headers,
    )
    assert forbidden.status_code == 403


def test_dashboard_trend_empty_without_completed_subjects(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "EMPTY_TREND")
    create_center(client, admin_headers, project_id, "EMPTY_TREND")

    trend = client.get(f"/api/dashboard/project/{project_id}/trend", headers=admin_headers)
    assert trend.status_code == 200
    assert trend.json() == []
