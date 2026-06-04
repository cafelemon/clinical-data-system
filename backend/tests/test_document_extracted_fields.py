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
        json={"name": "V350 项目", "code": "V350_PROJECT", "description": "", "status": "active"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_center(client: TestClient, headers: dict[str, str], project_id: int) -> int:
    response = client.post(
        "/api/centers",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "V350 中心",
            "code": "V350_CENTER",
            "contact_person": "",
            "status": "active",
            "description": "",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_subject(client: TestClient, headers: dict[str, str], project_id: int, center_id: int) -> dict:
    response = client.post(
        "/api/subjects",
        headers=headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "V350-S001",
            "subject_arm": "experimental",
        },
    )
    assert response.status_code == 201
    return response.json()


def subject_items(client: TestClient, headers: dict[str, str], subject_id: int) -> list[dict]:
    response = client.get(f"/api/subjects/{subject_id}/items", headers=headers)
    assert response.status_code == 200
    return response.json()


def item_by_code(items: list[dict], code: str) -> dict:
    return next(item for item in items if item["item_code"] == code)


def upload_subject_pdf(
    client: TestClient,
    headers: dict[str, str],
    item_id: int,
    filename: str,
) -> dict:
    response = client.post(
        "/api/files/upload",
        headers=headers,
        data={"file_category": "clinical_document", "subject_item_id": str(item_id)},
        files={"file": (filename, create_pdf(["field source"]), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pdf_upload_extracts_p0_fields_and_field_fix_auto_submits(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    consent = item_by_code(items, "V1_INFORMED_CONSENT")

    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "知情同意书",
                    "版本及日期：V1.1 2026年05月01日",
                    "受试者签名：2026年05月02日 10:30",
                ]
            )
        ],
    )
    file_record = upload_subject_pdf(client, admin_headers, consent["id"], "知情同意书.pdf")

    fields = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    )
    assert fields.status_code == 200
    field_rows = fields.json()
    assert {field["field_key"] for field in field_rows} == {
        "icf_version_date",
        "subject_signed_at",
        "investigator_signed_at",
    }
    assert next(field for field in field_rows if field["field_key"] == "investigator_signed_at")[
        "status"
    ] == "needs_input"
    assert next(field for field in field_rows if field["field_key"] == "subject_signed_at")[
        "normalized_value"
    ] == "2026-05-02 10:30"

    refreshed_items = subject_items(client, admin_headers, subject["id"])
    refreshed_consent = item_by_code(refreshed_items, "V1_INFORMED_CONSENT")
    assert refreshed_consent["upload_status"] == "uploaded"
    assert refreshed_consent["review_status"] == "unreviewed"

    missing_field = next(field for field in field_rows if field["field_key"] == "investigator_signed_at")
    fixed = client.patch(
        f"/api/files/{file_record['id']}/extracted-fields/{missing_field['id']}",
        headers=admin_headers,
        json={"raw_value": "研究者签名：2026年05月02日 10:45"},
    )
    assert fixed.status_code == 200
    assert fixed.json()["status"] == "confirmed"
    assert fixed.json()["normalized_value"] == "2026-05-02 10:45"

    submitted_items = subject_items(client, admin_headers, subject["id"])
    submitted_consent = item_by_code(submitted_items, "V1_INFORMED_CONSENT")
    assert submitted_consent["review_status"] == "pending"


def test_noisy_labeled_signature_dates_are_normalized(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    consent = item_by_code(items, "V1_INFORMED_CONSENT")
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "知情同意书",
                    "版本及日期：V1.0 20220810",
                    "受试者签名 没作闷",
                    "日期2023.2,13.8.23.",
                    "研究者签名",
                    "日期_2023.2.13.8:26.",
                ]
            )
        ],
    )

    file_record = upload_subject_pdf(client, admin_headers, consent["id"], "知情同意书.pdf")
    field_rows = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    ).json()

    assert next(field for field in field_rows if field["field_key"] == "subject_signed_at")[
        "normalized_value"
    ] == "2023-02-13 08:23"
    assert next(field for field in field_rows if field["field_key"] == "investigator_signed_at")[
        "normalized_value"
    ] == "2023-02-13 08:26"


def test_invalid_noisy_signature_date_stays_needs_input(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    consent = item_by_code(items, "V1_INFORMED_CONSENT")
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "知情同意书",
                    "版本及日期：V1.0 20220810",
                    "受试者签名 没作闷",
                    "日期2023.13.99.8.23.",
                    "研究者签名：2026年05月02日 10:45",
                ]
            )
        ],
    )

    file_record = upload_subject_pdf(client, admin_headers, consent["id"], "知情同意书.pdf")
    field_rows = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    ).json()
    subject_signed_at = next(field for field in field_rows if field["field_key"] == "subject_signed_at")

    assert subject_signed_at["normalized_value"] is None
    assert subject_signed_at["status"] == "needs_input"


def test_p0_handover_and_ct_fields_are_extracted(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    handover = item_by_code(items, "V1_INFORMED_CONSENT_HANDOVER")
    ct_report = item_by_code(items, "V1_CT_REPORT")
    current_text = {
        "value": "",
    }
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [current_text["value"]],
    )

    current_text["value"] = "\n".join(
        [
            "知情同意书交接记录表",
            "知情同意书签署日期：2026年05月02日",
            "受试者领用知情同意书时间：2026年05月03日",
        ]
    )
    handover_file = upload_subject_pdf(client, admin_headers, handover["id"], "知情同意书交接表.pdf")
    handover_fields = client.get(
        f"/api/files/{handover_file['id']}/extracted-fields",
        headers=admin_headers,
    ).json()
    assert {field["field_key"] for field in handover_fields} == {
        "icf_signed_date",
        "subject_received_date",
    }
    assert all(field["status"] == "extracted" for field in handover_fields)

    current_text["value"] = "\n".join(
        [
            "医学影像检查报告单",
            "登记号：CT-20260504",
            "检查名称：腹部CT",
            "检查时间：2026年05月04日 09:20",
            "印象：小肠未见明显异常。",
            "报告医师：张医生",
        ]
    )
    ct_file = upload_subject_pdf(client, admin_headers, ct_report["id"], "CT检查报告.pdf")
    ct_fields = client.get(
        f"/api/files/{ct_file['id']}/extracted-fields",
        headers=admin_headers,
    ).json()
    assert {field["field_key"] for field in ct_fields} == {
        "registration_no",
        "exam_name",
        "exam_at",
        "impression",
    }
    assert next(field for field in ct_fields if field["field_key"] == "registration_no")[
        "raw_value"
    ] == "CT-20260504"
    assert next(field for field in ct_fields if field["field_key"] == "exam_at")[
        "normalized_value"
    ] == "2026-05-04 09:20"


def test_p0_fields_return_editable_skeleton_when_ocr_has_no_values(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    consent = item_by_code(items, "V1_INFORMED_CONSENT")
    monkeypatch.setattr("app.services.document_fields.extract_page_texts", lambda *_: [""])

    file_record = upload_subject_pdf(client, admin_headers, consent["id"], "知情同意书.pdf")
    fields = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    )

    assert fields.status_code == 200
    field_rows = fields.json()
    assert {field["field_key"] for field in field_rows} == {
        "icf_version_date",
        "subject_signed_at",
        "investigator_signed_at",
    }
    assert all(field["status"] == "needs_input" for field in field_rows)
    assert all(field["confidence"] == 0 for field in field_rows)


def test_normalized_and_split_lines_are_used_for_field_extraction(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    ct_report = item_by_code(items, "V1_CT_REPORT")
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "医学影像检 查 报告",
                    "登记号",
                    "CT-20260504",
                    "检查项目 腹部CT",
                    "检查日期",
                    "2026年05月04日 09:20",
                    "检查结论:",
                    "小肠未见明显异常。",
                    "审核医师：张医生",
                ]
            )
        ],
    )

    file_record = upload_subject_pdf(client, admin_headers, ct_report["id"], "CT检查报告.pdf")
    field_rows = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    ).json()

    assert next(field for field in field_rows if field["field_key"] == "registration_no")[
        "raw_value"
    ] == "CT-20260504"
    assert next(field for field in field_rows if field["field_key"] == "exam_name")[
        "raw_value"
    ] == "腹部CT"
    assert next(field for field in field_rows if field["field_key"] == "exam_at")[
        "normalized_value"
    ] == "2026-05-04 09:20"
    assert next(field for field in field_rows if field["field_key"] == "impression")[
        "raw_value"
    ] == "小肠未见明显异常."


def test_pdf_packet_segment_fields_preview_and_copy_to_file(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    consent = item_by_code(items, "V1_INFORMED_CONSENT")
    monkeypatch.setattr(
        "app.services.pdf_packets.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "知情同意书",
                    "版本及日期：V1.1 2026年05月01日",
                    "受试者签名：2026年05月02日 10:30",
                    "研究者签名：2026年05月02日 10:45",
                ]
            )
        ],
    )
    packet_upload = client.post(
        "/api/pdf-packets/upload",
        headers=admin_headers,
        data={"project_id": str(project_id), "center_id": str(center_id), "subject_id": str(subject["id"])},
        files={"file": ("packet.pdf", create_pdf(["page 1"]), "application/pdf")},
    )
    assert packet_upload.status_code == 201
    packet_id = packet_upload.json()["id"]
    segments = client.get(f"/api/pdf-packets/{packet_id}/segments", headers=admin_headers).json()
    segment = segments[0]

    preview = client.get(f"/api/pdf-packet-segments/{segment['id']}/preview", headers=admin_headers)
    assert preview.status_code == 200
    preview_path = tmp_path / "segment-preview.pdf"
    preview_path.write_bytes(preview.content)
    assert pdf_page_count(preview_path) == 1

    segment_fields = client.get(
        f"/api/pdf-packet-segments/{segment['id']}/extracted-fields",
        headers=admin_headers,
    )
    assert segment_fields.status_code == 200
    assert all(field["status"] == "extracted" for field in segment_fields.json())

    uploaded = client.post(
        f"/api/pdf-packet-segments/{segment['id']}/upload",
        headers=admin_headers,
        json={"subject_item_id": consent["id"]},
    )
    assert uploaded.status_code == 200
    file_id = uploaded.json()["file"]["id"]
    file_fields = client.get(f"/api/files/{file_id}/extracted-fields", headers=admin_headers)
    assert file_fields.status_code == 200
    assert {field["field_key"] for field in file_fields.json()} == {
        "icf_version_date",
        "subject_signed_at",
        "investigator_signed_at",
    }


def test_extracted_field_write_requires_file_write_permission(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = subject_items(client, admin_headers, subject["id"])
    consent = item_by_code(items, "V1_INFORMED_CONSENT")
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: ["知情同意书\n版本及日期：V1.1"],
    )
    file_record = upload_subject_pdf(client, admin_headers, consent["id"], "知情同意书.pdf")
    field = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    ).json()[0]

    readonly_role_id = role_id_by_name(client, admin_headers, "readonly")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "field_readonly",
            "password": "Readonly@123",
            "full_name": "字段只读",
            "email": None,
            "is_active": True,
            "role_ids": [readonly_role_id],
            "project_ids": [project_id],
            "center_ids": [],
        },
    )
    assert create_user.status_code == 201
    readonly_headers = login_headers(client, "field_readonly", "Readonly@123")

    readable = client.get(f"/api/files/{file_record['id']}/extracted-fields", headers=readonly_headers)
    assert readable.status_code == 200
    denied = client.patch(
        f"/api/files/{file_record['id']}/extracted-fields/{field['id']}",
        headers=readonly_headers,
        json={"raw_value": "V1.1"},
    )
    assert denied.status_code == 403
