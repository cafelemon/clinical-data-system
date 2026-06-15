from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.test_files import create_subject_item


def upload_subject_pdf(
    client: TestClient,
    headers: dict[str, str],
    subject_item_id: int,
    name: str = "source.pdf",
) -> dict:
    response = client.post(
        "/api/files/upload",
        headers=headers,
        data={"file_category": "clinical_document", "subject_item_id": str(subject_item_id)},
        files={"file": (name, b"%PDF-1.4\nsource", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def test_pdf_review_annotation_and_correction_task_loop(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    item = create_subject_item(client, admin_headers)
    file_record = upload_subject_pdf(client, admin_headers, item["id"])

    review_file = client.get(
        f"/api/pdf-review/files/{file_record['id']}",
        headers=admin_headers,
    )
    assert review_file.status_code == 200
    review_payload = review_file.json()
    assert review_payload["version"] == 1
    assert review_payload["annotations"] == []

    create_annotation = client.post(
        "/api/pdf-review/annotations",
        headers=admin_headers,
        json={
            "file_id": file_record["id"],
            "file_version_id": review_payload["file_version_id"],
            "page_no": 1,
            "x": 0.1,
            "y": 0.2,
            "width": 0.3,
            "height": 0.1,
            "issue_type": "missing_signature",
            "severity": "high",
            "comment": "签名缺失",
        },
    )
    assert create_annotation.status_code == 201
    annotation_id = create_annotation.json()["id"]
    assert create_annotation.json()["status"] == "task_created"

    review_file_after_first = client.get(
        f"/api/pdf-review/files/{file_record['id']}",
        headers=admin_headers,
    )
    assert review_file_after_first.status_code == 200
    assert review_file_after_first.json()["active_task_status"] == "pending"
    assert review_file_after_first.json()["active_task_annotation_count"] == 1

    auto_tasks = client.get(
        f"/api/correction-tasks?file_id={file_record['id']}",
        headers=admin_headers,
    )
    assert auto_tasks.status_code == 200
    assert len(auto_tasks.json()) == 1
    auto_task = auto_tasks.json()[0]
    assert auto_task["status"] == "pending"
    assert [annotation["id"] for annotation in auto_task["annotations"]] == [annotation_id]

    create_task = client.post(
        "/api/correction-tasks",
        headers=admin_headers,
        json={
            "file_id": file_record["id"],
            "file_version_id": review_payload["file_version_id"],
            "annotation_ids": [annotation_id],
            "title": "知情同意书需整改",
            "description": "请补充签名页",
        },
    )
    assert create_task.status_code == 201
    task = create_task.json()
    assert task["id"] == auto_task["id"]
    assert task["status"] == "pending"
    assert task["annotations"][0]["status"] == "task_created"

    second_annotation = client.post(
        "/api/pdf-review/annotations",
        headers=admin_headers,
        json={
            "file_id": file_record["id"],
            "file_version_id": review_payload["file_version_id"],
            "page_no": 2,
            "x": 0.2,
            "y": 0.3,
            "width": 0.2,
            "height": 0.1,
            "issue_type": "missing_date",
            "severity": "medium",
            "comment": "日期缺失",
        },
    )
    assert second_annotation.status_code == 201

    review_file_after_second = client.get(
        f"/api/pdf-review/files/{file_record['id']}",
        headers=admin_headers,
    )
    assert review_file_after_second.status_code == 200
    assert review_file_after_second.json()["active_task_id"] == task["id"]
    assert review_file_after_second.json()["active_task_annotation_count"] == 2

    updated_items = client.get(f"/api/subjects/{item['subject_id']}/items", headers=admin_headers)
    updated_item = next(row for row in updated_items.json() if row["id"] == item["id"])
    assert updated_item["upload_status"] == "supplement_required"
    assert updated_item["review_status"] == "rejected"

    submit_task = client.post(
        f"/api/correction-tasks/{task['id']}/submit",
        headers=admin_headers,
        data={"remark": "已补签"},
        files={"file": ("corrected-v2.pdf", b"%PDF-1.4\ncorrected-v2", "application/pdf")},
    )
    assert submit_task.status_code == 200
    submitted = submit_task.json()["task"]
    assert submitted["status"] == "submitted"
    assert submitted["latest_file_version_id"] is not None

    versions = client.get(f"/api/files/{file_record['id']}/versions", headers=admin_headers)
    assert [version["version"] for version in versions.json()] == [1, 2]

    return_task = client.post(
        f"/api/correction-tasks/{task['id']}/return",
        headers=admin_headers,
        json={"comment": "仍缺日期"},
    )
    assert return_task.status_code == 200
    returned = return_task.json()
    assert returned["status"] == "returned"
    assert returned["annotations"][0]["status"] == "rejected"

    submit_again = client.post(
        f"/api/correction-tasks/{task['id']}/submit",
        headers=admin_headers,
        data={"remark": "已补日期"},
        files={"file": ("corrected-v3.pdf", b"%PDF-1.4\ncorrected-v3", "application/pdf")},
    )
    assert submit_again.status_code == 200
    assert submit_again.json()["task"]["status"] == "submitted"

    approve_task = client.post(
        f"/api/correction-tasks/{task['id']}/approve",
        headers=admin_headers,
        json={"comment": "复审通过"},
    )
    assert approve_task.status_code == 200
    approved = approve_task.json()
    assert approved["status"] == "closed"
    assert approved["review_result"] == "approved"
    assert approved["annotations"][0]["status"] == "resolved"

    final_versions = client.get(f"/api/files/{file_record['id']}/versions", headers=admin_headers)
    assert [version["version"] for version in final_versions.json()] == [1, 2, 3]

    final_items = client.get(f"/api/subjects/{item['subject_id']}/items", headers=admin_headers)
    final_item = next(row for row in final_items.json() if row["id"] == item["id"])
    assert final_item["upload_status"] == "replaced"
    assert final_item["review_status"] == "approved"


def test_pending_annotation_delete_updates_or_cancels_task_and_submitted_delete_is_blocked(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    item = create_subject_item(client, admin_headers)
    file_record = upload_subject_pdf(client, admin_headers, item["id"])

    review_file = client.get(
        f"/api/pdf-review/files/{file_record['id']}",
        headers=admin_headers,
    )
    assert review_file.status_code == 200
    file_version_id = review_file.json()["file_version_id"]

    first_annotation = client.post(
        "/api/pdf-review/annotations",
        headers=admin_headers,
        json={
            "file_id": file_record["id"],
            "file_version_id": file_version_id,
            "page_no": 1,
            "x": 0.1,
            "y": 0.1,
            "width": 0.2,
            "height": 0.1,
            "issue_type": "missing_signature",
            "severity": "high",
            "comment": "签名缺失",
        },
    )
    assert first_annotation.status_code == 201

    second_annotation = client.post(
        "/api/pdf-review/annotations",
        headers=admin_headers,
        json={
            "file_id": file_record["id"],
            "file_version_id": file_version_id,
            "page_no": 2,
            "x": 0.2,
            "y": 0.2,
            "width": 0.2,
            "height": 0.1,
            "issue_type": "missing_date",
            "severity": "medium",
            "comment": "日期缺失",
        },
    )
    assert second_annotation.status_code == 201

    tasks = client.get(f"/api/correction-tasks?file_id={file_record['id']}", headers=admin_headers)
    assert tasks.status_code == 200
    task = tasks.json()[0]
    assert task["status"] == "pending"
    assert len(task["annotations"]) == 2

    delete_first = client.delete(
        f"/api/pdf-review/annotations/{first_annotation.json()['id']}",
        headers=admin_headers,
    )
    assert delete_first.status_code == 204
    task_after_first_delete = client.get(
        f"/api/correction-tasks/{task['id']}",
        headers=admin_headers,
    )
    assert task_after_first_delete.status_code == 200
    assert task_after_first_delete.json()["status"] == "pending"
    assert len(task_after_first_delete.json()["annotations"]) == 1

    delete_second = client.delete(
        f"/api/pdf-review/annotations/{second_annotation.json()['id']}",
        headers=admin_headers,
    )
    assert delete_second.status_code == 204
    cancelled_task = client.get(
        f"/api/correction-tasks/{task['id']}",
        headers=admin_headers,
    )
    assert cancelled_task.status_code == 200
    assert cancelled_task.json()["status"] == "cancelled"
    assert cancelled_task.json()["annotations"] == []

    recreated_annotation = client.post(
        "/api/pdf-review/annotations",
        headers=admin_headers,
        json={
            "file_id": file_record["id"],
            "file_version_id": file_version_id,
            "page_no": 3,
            "x": 0.15,
            "y": 0.25,
            "width": 0.2,
            "height": 0.1,
            "issue_type": "wrong_document",
            "severity": "medium",
            "comment": "资料类型不匹配",
        },
    )
    assert recreated_annotation.status_code == 201

    replacement_task = client.get(
        f"/api/correction-tasks?file_id={file_record['id']}",
        headers=admin_headers,
    )
    assert replacement_task.status_code == 200
    active_task = replacement_task.json()[0]
    assert active_task["id"] != task["id"]

    submit_task = client.post(
        f"/api/correction-tasks/{active_task['id']}/submit",
        headers=admin_headers,
        data={"remark": "已整改"},
        files={"file": ("corrected.pdf", b"%PDF-1.4\ncorrected", "application/pdf")},
    )
    assert submit_task.status_code == 200

    delete_after_submit = client.delete(
        f"/api/pdf-review/annotations/{recreated_annotation.json()['id']}",
        headers=admin_headers,
    )
    assert delete_after_submit.status_code == 400
    assert "correction flow has started" in delete_after_submit.json()["detail"]


def test_subject_item_remark_autosave_endpoint_and_timeline(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    item = create_subject_item(client, admin_headers)

    remark = client.patch(
        f"/api/subject-items/{item['id']}/remark",
        headers=admin_headers,
        json={"remark": "需补充签名页"},
    )
    assert remark.status_code == 200
    assert remark.json()["success"] is True
    assert remark.json()["remark"] == "需补充签名页"

    file_record = upload_subject_pdf(client, admin_headers, item["id"], "first.pdf")
    replace = client.post(
        f"/api/files/{file_record['id']}/replace",
        headers=admin_headers,
        data={"change_note": "整改后重新上传"},
        files={"file": ("second.pdf", b"%PDF-1.4\nsecond", "application/pdf")},
    )
    assert replace.status_code == 200

    timeline = client.get(
        f"/api/subject-items/{item['id']}/timeline",
        headers=admin_headers,
    )
    assert timeline.status_code == 200
    labels = [entry["action_label"] for entry in timeline.json()]
    assert "修改备注" in labels
    assert "上传" in labels
    assert "重新上传" in labels
