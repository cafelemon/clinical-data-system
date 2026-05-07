from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.pdf_packets import pdf_page_count


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def role_id_by_name(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.get("/api/roles", headers=headers)
    assert response.status_code == 200
    return next(role["id"] for role in response.json() if role["name"] == name)


def create_pdf(pages: list[str]) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{4 + index * 2} 0 R".encode() for index in range(len(pages)))
        + f"] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(pages):
        page_object = 4 + index * 2
        content_object = page_object + 1
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 24 Tf 72 720 Td ({escaped}) Tj ET".encode()
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object} 0 R >>"
            ).encode()
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def create_project(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": "PDF包项目",
            "code": "PDF_PACKET_PROJECT",
            "description": "",
            "status": "active",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_center(client: TestClient, headers: dict[str, str], project_id: int) -> int:
    response = client.post(
        "/api/centers",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "PDF包中心",
            "code": "PDF_PACKET_CENTER",
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def first_trial_stage_id(client: TestClient, headers: dict[str, str], project_id: int) -> int:
    response = client.get(
        f"/api/stages?project_id={project_id}&phase_code=TRIAL",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()[0]["id"]


def create_subject_template(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    stage_id: int,
    name: str,
    code: str,
    keyword: str,
    sort_order: int,
) -> None:
    response = client.post(
        "/api/stage-templates",
        headers=headers,
        json={
            "project_id": project_id,
            "stage_id": stage_id,
            "item_name": name,
            "item_code": code,
            "template_scope": "subject_item",
            "required": True,
            "sort_order": sort_order,
            "recognition_keywords": keyword,
            "description": "",
        },
    )
    assert response.status_code == 201


def create_subject(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    center_id: int,
) -> dict:
    response = client.post(
        "/api/subjects",
        headers=headers,
        json={"project_id": project_id, "center_id": center_id, "screening_no": "010001"},
    )
    assert response.status_code == 201
    return response.json()


def test_pdf_packet_recognizes_segments_and_uploads_selected_pages(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    stage_id = first_trial_stage_id(client, admin_headers, project_id)
    create_subject_template(
        client,
        admin_headers,
        project_id,
        stage_id,
        "知情同意",
        "INFORMED_CONSENT",
        "Informed Consent",
        100,
    )
    create_subject_template(
        client,
        admin_headers,
        project_id,
        stage_id,
        "基线资料",
        "BASELINE_INFO",
        "Baseline Information",
        101,
    )
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    assert items.status_code == 200
    consent_item = next(item for item in items.json() if item["item_code"] == "INFORMED_CONSENT")
    baseline_item = next(item for item in items.json() if item["item_code"] == "BASELINE_INFO")

    pdf_bytes = create_pdf(["Informed Consent", "Baseline Information"])
    upload = client.post(
        "/api/pdf-packets/upload",
        headers=admin_headers,
        data={
            "project_id": str(project_id),
            "center_id": str(center_id),
            "subject_id": str(subject["id"]),
        },
        files={"file": ("010001.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201
    packet = upload.json()
    assert packet["page_count"] == 2
    assert packet["status"] == "ready"

    segments = client.get(f"/api/pdf-packets/{packet['id']}/segments", headers=admin_headers)
    assert segments.status_code == 200
    consent_segment = next(
        segment for segment in segments.json() if segment["detected_code"] == "INFORMED_CONSENT"
    )
    assert consent_segment["page_start"] == 1
    assert consent_segment["page_end"] == 1
    assert consent_segment["suggested_subject_item_id"] == consent_item["id"]

    baseline_segment = next(
        segment for segment in segments.json() if segment["detected_code"] == "BASELINE_INFO"
    )
    updated_segment = client.put(
        f"/api/pdf-packet-segments/{baseline_segment['id']}",
        headers=admin_headers,
        json={"detected_name": "基线资料确认", "subject_item_id": baseline_item["id"]},
    )
    assert updated_segment.status_code == 200
    assert updated_segment.json()["detected_name"] == "基线资料确认"

    manual_segment = client.post(
        f"/api/pdf-packets/{packet['id']}/segments",
        headers=admin_headers,
        json={
            "page_start": 2,
            "page_end": 2,
            "detected_name": "手工片段",
            "subject_item_id": baseline_item["id"],
        },
    )
    assert manual_segment.status_code == 201
    deleted_segment = client.delete(
        f"/api/pdf-packet-segments/{manual_segment.json()['id']}",
        headers=admin_headers,
    )
    assert deleted_segment.status_code == 204

    uploaded = client.post(
        f"/api/pdf-packet-segments/{consent_segment['id']}/upload",
        headers=admin_headers,
        json={"subject_item_id": consent_item["id"]},
    )
    assert uploaded.status_code == 200
    file_record = uploaded.json()["file"]
    assert file_record["subject_item_id"] == consent_item["id"]
    assert file_record["source_pdf_packet_id"] == packet["id"]
    assert file_record["source_page_start"] == 1
    assert file_record["source_page_end"] == 1
    extracted_path = settings.file_storage_root / file_record["storage_path"]
    assert extracted_path.exists()
    assert pdf_page_count(extracted_path) == 1

    refreshed_items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers)
    refreshed_consent = next(
        item for item in refreshed_items.json() if item["id"] == consent_item["id"]
    )
    assert refreshed_consent["upload_status"] == "uploaded"


def test_pdf_packet_write_permission_required(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    readonly_role_id = role_id_by_name(client, admin_headers, "readonly")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "pdf_readonly",
            "password": "Readonly@123",
            "full_name": "PDF只读",
            "email": None,
            "is_active": True,
            "role_ids": [readonly_role_id],
            "project_ids": [project_id],
            "center_ids": [],
        },
    )
    assert create_user.status_code == 201
    readonly_headers = login_headers(client, "pdf_readonly", "Readonly@123")

    denied = client.post(
        "/api/pdf-packets/upload",
        headers=readonly_headers,
        data={
            "project_id": str(project_id),
            "center_id": str(center_id),
            "subject_id": str(subject["id"]),
        },
        files={"file": ("010001.pdf", create_pdf(["Informed Consent"]), "application/pdf")},
    )
    assert denied.status_code == 403
