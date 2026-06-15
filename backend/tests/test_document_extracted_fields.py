from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.document_fields import (
    DOCUMENT_CONSENT,
    DOCUMENT_CONSENT_HANDOVER,
    DOCUMENT_CT_REPORT,
    DOCUMENT_SSU_AGREEMENT_SIGNING,
    DOCUMENT_SSU_ETHICS,
    DOCUMENT_SSU_PROJECT_APPROVAL,
    DOCUMENT_SSU_PROVINCIAL_FILING,
    DOCUMENT_SSU_STARTUP_MEETING,
    extract_values,
    field_status_for,
    FIELD_SPECS,
)
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
    page_refs = [f"{3 + index} 0 R" for index in range(len(pages))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >>".encode(),
    ]
    objects.extend(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"
        for _ in pages
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


def create_ssu_progress(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    center_id: int,
    stage_code: str,
) -> dict:
    response = client.post(
        "/api/clinical-datasets/ssu-progress",
        headers=headers,
        json={
            "project_id": project_id,
            "center_id": center_id,
            "stage_code": stage_code,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_ssu_pdf(
    client: TestClient,
    headers: dict[str, str],
    progress_id: int,
    filename: str = "SSU材料.pdf",
) -> dict:
    response = client.post(
        "/api/files/upload",
        headers=headers,
        data={"file_category": "ssu_document", "ssu_progress_id": str(progress_id)},
        files={"file": (filename, create_pdf(["ssu field source"]), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("document_type", "sample_path", "page_texts", "expected"),
    [
        (
            DOCUMENT_SSU_PROJECT_APPROVAL,
            Path("V3材料/ssu进展/1.1立项初审申请表.pdf"),
            [
                (
                    1,
                    "\n".join(
                        [
                            "立项初审申请表",
                            "递交日期: 2026 年 01 月 02 日",
                            "文件清单:",
                            "1. 立项申请表",
                            "2. 临床研究方案",
                            "通过日期: 2026年01月06日",
                        ]
                    ),
                )
            ],
            {
                "submitted_at": "2026-01-02",
                "approved_at": "2026-01-06",
                "file_checklist": "1. 立项申请表\n2. 临床研究方案",
            },
        ),
        (
            DOCUMENT_SSU_ETHICS,
            Path("V3材料/ssu进展/01中心 北京友谊伦理批件.pdf"),
            [
                (
                    1,
                    "\n".join(
                        [
                            "伦理审查批件",
                            "递交日期: 2026年01月09日",
                            "文件清单: 伦理申请表、知情同意书、研究方案",
                            "审查意见: 同意开展本研究。",
                            "签发日期: 2026年01月15日",
                        ]
                    ),
                )
            ],
            {
                "submitted_at": "2026-01-09",
                "approved_at": "2026-01-15",
                "summary": "同意开展本研究.",
            },
        ),
        (
            DOCUMENT_SSU_AGREEMENT_SIGNING,
            Path("V3材料/ssu进展/01友谊医院-临床试验协议 .pdf"),
            [
                (
                    1,
                    "\n".join(
                        [
                            "临床试验协议",
                            "协议版本: V1.1 / 2026年01月10日",
                            "签署日期: 2026年01月18日",
                        ]
                    ),
                ),
                (
                    2,
                    "\n".join(
                        [
                            "CRC协议",
                            "费用明细:",
                            "CRC服务费 30000元",
                            "签章",
                        ]
                    ),
                ),
            ],
            {
                "version_info": "V1.1 / 2026年01月10日",
                "completed_at": "2026-01-18",
                "fee_detail": "CRC服务费 30000元",
            },
        ),
        (
            DOCUMENT_SSU_PROVINCIAL_FILING,
            Path("V3材料/ssu进展/01友谊省局备案.pdf"),
            [
                (
                    1,
                    "\n".join(
                        [
                            "省局备案表",
                            "备案号: BA202601200088",
                            "省级药品监管部门盖章日期: 2026年01月22日",
                        ]
                    ),
                )
            ],
            {"completed_at": "2026-01-22"},
        ),
        (
            DOCUMENT_SSU_STARTUP_MEETING,
            Path("V3材料/ssu进展/01中心启动会/启动会会议纪要.pdf"),
            [
                (1, "启动会签到表\n签到日期: 2026年01月24日"),
                (2, "启动会会议纪要\n会议日期: 2026年01月25日\n会议地点: 北京友谊医院"),
                (3, "培训记录\n培训日期: 2026年01月26日"),
            ],
            {"completed_at": "2026-01-25"},
        ),
    ],
)
def test_v354_ssu_golden_cases_from_sample_set(
    document_type: str,
    sample_path: Path,
    page_texts: list[tuple[int, str]],
    expected: dict[str, str],
) -> None:
    assert sample_path.exists()

    values = extract_values(document_type, page_texts)

    for field_key, expected_value in expected.items():
        value = values[field_key]
        actual = value.normalized_value or value.raw_value
        assert actual == expected_value
        spec = next(spec for spec in FIELD_SPECS[document_type] if spec.key == field_key)
        assert field_status_for(spec, value) == "extracted"


def test_v354_project_approval_does_not_promote_first_date_to_approval() -> None:
    values = extract_values(
        DOCUMENT_SSU_PROJECT_APPROVAL,
        [
            (
                1,
                "\n".join(
                    [
                        "立项初审申请表",
                        "递交日期: 2026年02月01日",
                        "文件清单: 立项申请表、研究方案",
                    ]
                ),
            )
        ],
    )

    assert values["submitted_at"].normalized_value == "2026-02-01"
    assert values["approved_at"].raw_value is None


def test_v354_provincial_filing_number_is_not_used_as_date() -> None:
    values = extract_values(
        DOCUMENT_SSU_PROVINCIAL_FILING,
        [(1, "省局备案表\n备案号: BA202603180088\n经办人: 李老师")],
    )

    completed = values["completed_at"]
    assert completed.raw_value is None
    assert completed.normalized_value is None


def test_v354_p0_small_intestine_golden_cases_use_c200_samples() -> None:
    sample_paths = [
        Path(
            "data-dev/file-storage/projects/C200/centers/01/subjects/010001/"
            "documents/知情同意书/v1/aa8298afb9dc40ef94b27bd77056a4e3.pdf"
        ),
        Path(
            "data-dev/file-storage/projects/C200/centers/01/subjects/010001/"
            "documents/知情同意书交接表/v1/8c1d1f1042af41d4baf4c62d57cb9558.pdf"
        ),
        Path(
            "data-dev/file-storage/projects/C200/centers/01/subjects/010001/"
            "documents/CT报告/v1/756af1d973634c89807af7848e735ff1.pdf"
        ),
    ]
    for sample_path in sample_paths:
        assert sample_path.exists()

    consent = extract_values(
        DOCUMENT_CONSENT,
        [
            (
                1,
                "\n".join(
                    [
                        "小肠胶囊内镜项目 知情同意书",
                        "版本及日期: V1.2 2026年02月10日",
                        "受试者签名",
                        "签署时间: 2026年02月12日 09:15",
                        "研究者签名",
                        "签署时间: 2026年02月12日 09:28",
                    ]
                ),
            )
        ],
    )
    handover = extract_values(
        DOCUMENT_CONSENT_HANDOVER,
        [
            (
                1,
                "\n".join(
                    [
                        "知情同意书交接记录表",
                        "知情同意书签署日期: 2026年02月12日",
                        "受试者领用日期: 2026年02月13日",
                    ]
                ),
            )
        ],
    )
    ct_report = extract_values(
        DOCUMENT_CT_REPORT,
        [
            (
                1,
                "\n".join(
                    [
                        "医学影像检查报告单",
                        "登记号: CT20260214001",
                        "检查名称: 小肠CT增强",
                        "检查时间: 2026年02月14日 10:35",
                        "印象:",
                        "小肠壁未见明显增厚, 未见异常强化。",
                        "审核医师: 王医生",
                        "打印时间: 2026年02月14日 11:00",
                    ]
                ),
            )
        ],
    )

    assert consent["icf_version_date"].raw_value == "V1.2 2026年02月10日"
    assert consent["subject_signed_at"].normalized_value == "2026-02-12 09:15"
    assert consent["investigator_signed_at"].normalized_value == "2026-02-12 09:28"
    assert handover["icf_signed_date"].normalized_value == "2026-02-12"
    assert handover["subject_received_date"].normalized_value == "2026-02-13"
    assert ct_report["registration_no"].raw_value == "CT20260214001"
    assert ct_report["exam_name"].raw_value == "小肠CT增强"
    assert ct_report["exam_at"].normalized_value == "2026-02-14 10:35"
    assert ct_report["impression"].raw_value == "小肠壁未见明显增厚, 未见异常强化."


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

    subject_signed_at = next(
        field for field in field_rows if field["field_key"] == "subject_signed_at"
    )
    dotted_time = client.patch(
        f"/api/files/{file_record['id']}/extracted-fields/{subject_signed_at['id']}",
        headers=admin_headers,
        json={"raw_value": "2025.12.18 08.07"},
    )
    assert dotted_time.status_code == 200
    assert dotted_time.json()["status"] == "confirmed"
    assert dotted_time.json()["normalized_value"] == "2025-12-18 08:07"

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


def test_ssu_upload_creates_field_skeletons_for_all_stages(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    monkeypatch.setattr("app.services.document_fields.extract_page_texts", lambda *_: [""])
    expected_keys = {
        "SSU_PROJECT_APPROVAL": {"submitted_at", "file_checklist", "approved_at"},
        "SSU_ETHICS": {"submitted_at", "file_checklist", "summary", "approved_at"},
        "SSU_AGREEMENT_SIGNING": {"version_info", "completed_at", "fee_detail"},
        "SSU_PROVINCIAL_FILING": {"completed_at"},
        "SSU_STARTUP_MEETING": {"completed_at"},
    }

    for stage_code, keys in expected_keys.items():
        progress = create_ssu_progress(client, admin_headers, project_id, center_id, stage_code)
        file_record = upload_ssu_pdf(client, admin_headers, progress["id"], f"{stage_code}.pdf")
        fields = client.get(
            f"/api/files/{file_record['id']}/extracted-fields",
            headers=admin_headers,
        )
        assert fields.status_code == 200
        field_rows = fields.json()
        assert {field["field_key"] for field in field_rows} == keys
        assert all(field["status"] == "needs_input" for field in field_rows)


def test_ssu_ethics_fields_auto_sync_when_complete(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    progress = create_ssu_progress(client, admin_headers, project_id, center_id, "SSU_ETHICS")
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "伦理审查批件",
                    "递交日期：2026年01月02日",
                    "文件清单：伦理申请表、知情同意书",
                    "批件主旨内容：同意开展本研究",
                    "同意日期：2026年01月08日",
                ]
            )
        ],
    )
    file_record = upload_ssu_pdf(client, admin_headers, progress["id"], "伦理批件.pdf")

    fields = client.get(f"/api/files/{file_record['id']}/extracted-fields", headers=admin_headers)
    assert fields.status_code == 200
    field_rows = fields.json()
    assert all(field["status"] == "extracted" for field in field_rows)
    assert next(field for field in field_rows if field["field_key"] == "approved_at")[
        "normalized_value"
    ] == "2026-01-08"

    refreshed = client.get(
        f"/api/clinical-datasets/ssu-progress?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    )
    assert refreshed.status_code == 200
    ethics = next(record for record in refreshed.json() if record["id"] == progress["id"])
    assert ethics["status"] == "completed"
    assert ethics["submitted_at"] == "2026-01-02"
    assert ethics["approved_at"] == "2026-01-08"
    assert ethics["file_checklist"] == "伦理申请表、知情同意书"
    assert ethics["summary"] == "同意开展本研究"


def test_ssu_missing_field_does_not_sync_until_manual_fix_and_apply(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    progress = create_ssu_progress(
        client,
        admin_headers,
        project_id,
        center_id,
        "SSU_PROJECT_APPROVAL",
    )
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: [
            "\n".join(
                [
                    "立项初审申请表",
                    "递交日期：2026年02月01日",
                    "文件清单：立项申请表、研究方案",
                ]
            )
        ],
    )
    file_record = upload_ssu_pdf(client, admin_headers, progress["id"], "立项初审.pdf")
    field_rows = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    ).json()
    assert next(field for field in field_rows if field["field_key"] == "approved_at")[
        "status"
    ] == "needs_input"

    unchanged = client.get(
        f"/api/clinical-datasets/ssu-progress?project_id={project_id}&center_id={center_id}",
        headers=admin_headers,
    ).json()
    project_approval = next(record for record in unchanged if record["id"] == progress["id"])
    assert project_approval["status"] == "not_started"
    assert project_approval["submitted_at"] is None

    approved_field = next(field for field in field_rows if field["field_key"] == "approved_at")
    fixed = client.patch(
        f"/api/files/{file_record['id']}/extracted-fields/{approved_field['id']}",
        headers=admin_headers,
        json={"raw_value": "同意日期：2026年02月06日"},
    )
    assert fixed.status_code == 200
    apply_response = client.post(
        f"/api/clinical-datasets/ssu-progress/{progress['id']}/apply-extracted-fields",
        headers=admin_headers,
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "completed"
    assert apply_response.json()["submitted_at"] == "2026-02-01"
    assert apply_response.json()["approved_at"] == "2026-02-06"
    assert apply_response.json()["file_checklist"] == "立项申请表、研究方案"


def test_ssu_extracted_fields_write_actions_require_permission(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    progress = create_ssu_progress(
        client, admin_headers, project_id, center_id, "SSU_STARTUP_MEETING"
    )
    monkeypatch.setattr(
        "app.services.document_fields.extract_page_texts",
        lambda *_: ["启动会会议纪要\n会议日期：2026年03月01日"],
    )
    file_record = upload_ssu_pdf(client, admin_headers, progress["id"], "启动会会议纪要.pdf")
    field = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=admin_headers,
    ).json()[0]

    readonly_role_id = role_id_by_name(client, admin_headers, "readonly")
    create_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "ssu_field_readonly",
            "password": "Readonly@123",
            "full_name": "SSU字段只读",
            "email": None,
            "is_active": True,
            "role_ids": [readonly_role_id],
            "project_ids": [project_id],
            "center_ids": [],
        },
    )
    assert create_user.status_code == 201
    readonly_headers = login_headers(client, "ssu_field_readonly", "Readonly@123")

    readable = client.get(
        f"/api/files/{file_record['id']}/extracted-fields",
        headers=readonly_headers,
    )
    assert readable.status_code == 200
    denied_analyze = client.post(
        f"/api/files/{file_record['id']}/extracted-fields/analyze",
        headers=readonly_headers,
    )
    assert denied_analyze.status_code == 403
    denied_edit = client.patch(
        f"/api/files/{file_record['id']}/extracted-fields/{field['id']}",
        headers=readonly_headers,
        json={"raw_value": "会议日期：2026年03月02日"},
    )
    assert denied_edit.status_code == 403
    denied_apply = client.post(
        f"/api/clinical-datasets/ssu-progress/{progress['id']}/apply-extracted-fields",
        headers=readonly_headers,
    )
    assert denied_apply.status_code == 403
