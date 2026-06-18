import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.models import OperationLog, SnapshotQualityCheck, SubjectItem, SubjectSnapshot
from tests.test_dashboard import create_user
from tests.test_snapshot_precheck import (
    create_latest_field,
    db_session,
    mark_required_documents_approved,
    mark_required_images_uploaded,
    setup_subject,
)


def prepare_snapshot_ready_subject(
    client: TestClient,
    admin_headers: dict[str, str],
    suffix: str,
) -> tuple[int, int, dict]:
    project_id, center_id, subject = setup_subject(client, admin_headers, suffix)
    with db_session(client) as db:
        mark_required_documents_approved(db, subject["id"])
        mark_required_images_uploaded(db, subject["id"])
        first_required_item = db.scalar(
            select(SubjectItem).where(
                SubjectItem.subject_id == subject["id"],
                SubjectItem.required.is_(True),
            )
        )
        assert first_required_item is not None
        create_latest_field(
            db,
            subject_id=subject["id"],
            subject_item_id=first_required_item.id,
            status="confirmed",
            confidence=0.92,
        )
        db.commit()
    return project_id, center_id, subject


def snapshot_file_path(storage_path: str) -> Path:
    return settings.file_storage_root / storage_path


def test_generate_released_snapshot_writes_json_and_links_checks(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = prepare_snapshot_ready_subject(client, admin_headers, "SNAP_GEN_OK")

    response = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    snapshot = body["snapshot"]
    assert snapshot["snapshot_version"] == 1
    assert snapshot["snapshot_type"] == "released_snapshot"
    assert snapshot["status"] == "released"
    assert snapshot["generated_by"] is not None
    assert snapshot["generated_at"] == snapshot["locked_at"]
    assert body["storage_path"] == snapshot["storage_path"]
    assert body["file_hash"] == snapshot["file_hash"]
    assert body["file_size"] == snapshot["file_size"]

    path = snapshot_file_path(body["storage_path"])
    assert path.exists()
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == body["file_hash"]
    assert len(content) == body["file_size"]
    payload = json.loads(content.decode("utf-8"))
    assert payload["schema_version"] == "subject-snapshot-json/v0"
    assert payload["snapshot_id"] == snapshot["id"]
    assert payload["snapshot_type"] == "released_snapshot"
    assert payload["subject"]["screening_no"] == subject["screening_no"]
    assert payload["clinical_tree"]
    assert "subject_signed_at" in payload["fields_index"]
    assert set(payload["images_index"]) == {"enhanced", "raw", "report"}
    assert payload["algorithm_runs"] == []
    assert payload["quality_summary"]["eligible"] is True

    with db_session(client) as db:
        linked_checks = list(
            db.scalars(
                select(SnapshotQualityCheck).where(
                    SnapshotQualityCheck.check_run_id == body["check_run_id"]
                )
            )
        )
        assert linked_checks
        assert {check.snapshot_id for check in linked_checks} == {snapshot["id"]}


def test_generate_released_snapshot_increments_versions_without_overwrite(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = prepare_snapshot_ready_subject(client, admin_headers, "SNAP_GEN_VER")

    first = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)
    second = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["snapshot"]["snapshot_version"] == 1
    assert second_body["snapshot"]["snapshot_version"] == 2
    assert first_body["storage_path"] != second_body["storage_path"]
    assert snapshot_file_path(first_body["storage_path"]).exists()
    assert snapshot_file_path(second_body["storage_path"]).exists()


def test_generate_snapshot_precheck_failure_persists_checks_without_snapshot_or_file(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = setup_subject(client, admin_headers, "SNAP_GEN_BLOCK")

    response = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["eligible"] is False
    assert detail["blocking_failure_count"] > 0
    with db_session(client) as db:
        assert db.scalar(select(func.count()).select_from(SubjectSnapshot)) == 0
        checks = list(
            db.scalars(
                select(SnapshotQualityCheck).where(
                    SnapshotQualityCheck.check_run_id == detail["check_run_id"]
                )
            )
        )
        assert checks
        assert {check.snapshot_id for check in checks} == {None}
    assert not any(settings.file_storage_root.rglob("subject_snapshot_v*.json"))


def test_generate_snapshot_permissions_are_admin_or_project_manager_only(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id, _, subject = prepare_snapshot_ready_subject(
        client,
        admin_headers,
        "SNAP_GEN_PERM",
    )
    other_project_id, _, _ = setup_subject(client, admin_headers, "SNAP_GEN_OTHER")

    project_manager_headers = create_user(
        client,
        admin_headers,
        "snapshot_project_manager",
        "project_manager",
        project_ids=[project_id],
    )
    project_manager_response = client.post(
        f"/api/subjects/{subject['id']}/snapshots",
        headers=project_manager_headers,
    )
    assert project_manager_response.status_code == 200

    scoped_out_headers = create_user(
        client,
        admin_headers,
        "snapshot_scoped_out",
        "project_manager",
        project_ids=[other_project_id],
    )
    scoped_out_response = client.post(
        f"/api/subjects/{subject['id']}/snapshots",
        headers=scoped_out_headers,
    )
    assert scoped_out_response.status_code == 403

    for username, role in [
        ("snapshot_readonly", "readonly"),
        ("snapshot_rd", "rd_user"),
        ("snapshot_coordinator", "clinical_coordinator"),
    ]:
        headers = create_user(
            client,
            admin_headers,
            username,
            role,
            project_ids=[project_id],
        )
        response = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=headers)
        assert response.status_code == 403


def test_download_snapshot_json_returns_file_and_records_operation(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = prepare_snapshot_ready_subject(client, admin_headers, "SNAP_EXPORT_OK")
    generated = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)
    assert generated.status_code == 200
    body = generated.json()
    snapshot = body["snapshot"]
    expected_content = snapshot_file_path(body["storage_path"]).read_bytes()

    response = client.get(
        f"/api/subjects/{subject['id']}/snapshots/{snapshot['id']}/json",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert f"subject_snapshot_{subject['screening_no']}_v1.json" in response.headers[
        "content-disposition"
    ]
    assert response.content == expected_content
    assert hashlib.sha256(response.content).hexdigest() == body["file_hash"]
    with db_session(client) as db:
        log = db.scalar(
            select(OperationLog)
            .where(OperationLog.action == "subject_snapshot.download_json")
            .order_by(OperationLog.id.desc())
        )
        assert log is not None
        assert log.target_type == "subject_snapshot"
        assert log.target_id == snapshot["id"]
        assert log.detail_json["snapshot_version"] == 1
        assert log.detail_json["file_hash"] == body["file_hash"]


def test_download_snapshot_json_allows_export_read_scope_and_denies_scope_out(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id, _, subject = prepare_snapshot_ready_subject(
        client,
        admin_headers,
        "SNAP_EXPORT_SCOPE",
    )
    other_project_id, _, _ = setup_subject(client, admin_headers, "SNAP_EXPORT_OTHER_SCOPE")
    generated = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)
    assert generated.status_code == 200
    snapshot_id = generated.json()["snapshot"]["id"]

    rd_headers = create_user(
        client,
        admin_headers,
        "snapshot_export_rd",
        "rd_user",
        project_ids=[project_id],
    )
    allowed = client.get(
        f"/api/subjects/{subject['id']}/snapshots/{snapshot_id}/json",
        headers=rd_headers,
    )
    assert allowed.status_code == 200

    scoped_out_headers = create_user(
        client,
        admin_headers,
        "snapshot_export_scoped_out",
        "rd_user",
        project_ids=[other_project_id],
    )
    denied = client.get(
        f"/api/subjects/{subject['id']}/snapshots/{snapshot_id}/json",
        headers=scoped_out_headers,
    )
    assert denied.status_code == 403


def test_download_snapshot_json_rejects_wrong_subject_and_unreleased_snapshot(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject_a = prepare_snapshot_ready_subject(client, admin_headers, "SNAP_EXPORT_A")
    _, _, subject_b = prepare_snapshot_ready_subject(client, admin_headers, "SNAP_EXPORT_B")
    generated_a = client.post(f"/api/subjects/{subject_a['id']}/snapshots", headers=admin_headers)
    generated_b = client.post(f"/api/subjects/{subject_b['id']}/snapshots", headers=admin_headers)
    assert generated_a.status_code == 200
    assert generated_b.status_code == 200
    snapshot_a = generated_a.json()["snapshot"]
    snapshot_b = generated_b.json()["snapshot"]

    wrong_subject = client.get(
        f"/api/subjects/{subject_a['id']}/snapshots/{snapshot_b['id']}/json",
        headers=admin_headers,
    )
    assert wrong_subject.status_code == 404

    with db_session(client) as db:
        snapshot = db.get(SubjectSnapshot, snapshot_a["id"])
        assert snapshot is not None
        snapshot.status = "draft"
        db.commit()
    unreleased = client.get(
        f"/api/subjects/{subject_a['id']}/snapshots/{snapshot_a['id']}/json",
        headers=admin_headers,
    )
    assert unreleased.status_code == 409


def test_download_snapshot_json_handles_missing_file_and_integrity_mismatch(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, missing_subject = prepare_snapshot_ready_subject(
        client,
        admin_headers,
        "SNAP_EXPORT_MISSING",
    )
    missing_generated = client.post(
        f"/api/subjects/{missing_subject['id']}/snapshots",
        headers=admin_headers,
    )
    assert missing_generated.status_code == 200
    missing_body = missing_generated.json()
    snapshot_file_path(missing_body["storage_path"]).unlink()
    missing_response = client.get(
        f"/api/subjects/{missing_subject['id']}/snapshots/"
        f"{missing_body['snapshot']['id']}/json",
        headers=admin_headers,
    )
    assert missing_response.status_code == 404

    _, _, tampered_subject = prepare_snapshot_ready_subject(
        client,
        admin_headers,
        "SNAP_EXPORT_TAMPERED",
    )
    tampered_generated = client.post(
        f"/api/subjects/{tampered_subject['id']}/snapshots",
        headers=admin_headers,
    )
    assert tampered_generated.status_code == 200
    tampered_body = tampered_generated.json()
    snapshot_file_path(tampered_body["storage_path"]).write_text("{}", encoding="utf-8")
    tampered_response = client.get(
        f"/api/subjects/{tampered_subject['id']}/snapshots/"
        f"{tampered_body['snapshot']['id']}/json",
        headers=admin_headers,
    )
    assert tampered_response.status_code == 500


def test_list_subject_snapshots_returns_history_desc_without_side_effects(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    _, _, subject = prepare_snapshot_ready_subject(client, admin_headers, "SNAP_HISTORY")
    first = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)
    second = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)
    assert first.status_code == 200
    assert second.status_code == 200

    with db_session(client) as db:
        snapshot_count = db.scalar(select(func.count()).select_from(SubjectSnapshot))
        check_count = db.scalar(select(func.count()).select_from(SnapshotQualityCheck))

    response = client.get(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)

    assert response.status_code == 200
    history = response.json()
    assert [snapshot["snapshot_version"] for snapshot in history] == [2, 1]
    assert history[0]["generated_by_name"] is not None
    assert history[0]["status"] == "released"
    assert history[0]["file_hash"] == second.json()["file_hash"]
    with db_session(client) as db:
        assert db.scalar(select(func.count()).select_from(SubjectSnapshot)) == snapshot_count
        assert db.scalar(select(func.count()).select_from(SnapshotQualityCheck)) == check_count


def test_list_subject_snapshots_permissions_and_missing_subject(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id, _, subject = prepare_snapshot_ready_subject(
        client,
        admin_headers,
        "SNAP_HISTORY_PERM",
    )
    other_project_id, _, _ = setup_subject(client, admin_headers, "SNAP_HISTORY_OTHER")
    generated = client.post(f"/api/subjects/{subject['id']}/snapshots", headers=admin_headers)
    assert generated.status_code == 200

    project_manager_headers = create_user(
        client,
        admin_headers,
        "snapshot_history_project_manager",
        "project_manager",
        project_ids=[project_id],
    )
    readonly_headers = create_user(
        client,
        admin_headers,
        "snapshot_history_readonly",
        "readonly",
        project_ids=[project_id],
    )
    rd_headers = create_user(
        client,
        admin_headers,
        "snapshot_history_rd",
        "rd_user",
        project_ids=[project_id],
    )
    for headers in [project_manager_headers, readonly_headers, rd_headers]:
        response = client.get(f"/api/subjects/{subject['id']}/snapshots", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1

    scoped_out_headers = create_user(
        client,
        admin_headers,
        "snapshot_history_scoped_out",
        "rd_user",
        project_ids=[other_project_id],
    )
    scoped_out = client.get(f"/api/subjects/{subject['id']}/snapshots", headers=scoped_out_headers)
    assert scoped_out.status_code == 403

    missing = client.get("/api/subjects/999999/snapshots", headers=admin_headers)
    assert missing.status_code == 404
