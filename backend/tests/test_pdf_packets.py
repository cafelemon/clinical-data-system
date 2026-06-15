import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.page_text_normalizer import normalize_page_text
from app.services.pdf_packet_classifier import classify_page
from app.services.pdf_packets import SubjectItemCandidate, pdf_page_count

SAMPLE_010005_OCR_TEXTS = [
    "知情同意书 受试者知情同意 同意参加临床试验 签署知情",
    "知情同意书交接记录表 交接 接收 知情同意书份数 研究者交接",
    "医学影像检查报告单 CT 检查所见 放射科 报告医师",
    "门诊病历 第1页 门诊号 主诉 现病史 诊断 处方",
    "门诊病历 第2页 主诉 现病史 既往史 诊断",
    "门诊病历 第3页 就诊时间 现病史 处方",
    "门诊病历 第4页 主诉 诊断 处方",
    "门诊病历 第5页 既往史 诊断",
    "门诊病历 第6页 就诊时间 主诉 现病史",
    "门诊病历 第7页 门诊号 诊断 处方",
    "门诊病历 第8页 主诉 既往史 诊断",
    "门诊病历 第9页 就诊时间 现病史 处方",
    "入组审核记录表 入组审核 是否符合 研究者签名",
    "入选标准 入组 是否符合 研究者签名",
    "排除标准 入组 是否符合 研究者签名",
    "生命体征记录表 体温 脉搏 呼吸 血压 收缩压 舒张压",
    "舒适度评价表 舒适 疼痛 VAS 不适 评价",
    "图像质量评价表 图像质量 清晰度 完整性 评价结果",
    "图像质量评价表 图片质量 清晰度 完整性",
    "图像质量评价表 图像质量 清晰度 完整性",
    "图像质量评价表 图片质量 清晰度 完整性",
    "设备常用功能评价表 设备常用功能 胶囊定位 下载 传输",
    "设备稳定性评价表 设备稳定性 电池 下载 传输",
    "其他次要标准评价表 胶囊内镜报告信息 胃通过时间 小肠通过时间",
    "独立评估人检查图像质量评估表 独立评估人 阅片 图像质量评估",
    "独立评估人检查图像质量评估表 独立评估人 阅片 评估人签名",
    "胶囊内镜报告 检查所见 诊断意见 胃通过时间 小肠通过时间",
]


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
    return next(stage["id"] for stage in response.json() if stage["code"] == "V1_SCREENING_VISIT")


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
        json={
            "project_id": project_id,
            "center_id": center_id,
            "screening_no": "010001",
            "subject_arm": "experimental",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_page_text_normalizer_cleans_ocr_noise_and_keeps_structured_lines() -> None:
    page = normalize_page_text(
        "  医学影像检査　报告：  \n\n"
        "二维码 请扫描查看原件\n"
        "检查日期：2026年5月13日\n"
        "第 1 页 / 2\n"
        "图象质景  良好\n"
    )

    assert page.raw_text.startswith("  医学影像")
    assert "医学影像检查 报告:" in page.normalized_text
    assert "检查日期:2026-5-13" in page.normalized_text
    assert "图像质量 良好" in page.normalized_text
    assert "二维码" not in page.normalized_text
    assert "第 1 页" not in page.normalized_text
    assert page.head_lines == page.lines[:20]
    assert page.tail_lines == page.lines[-10:]


def test_title_strong_recognition_prefers_long_handover_title() -> None:
    classification = classify_page(
        1,
        "知情同意书交接记录表\n知情同意书\n交接 接收 知情同意书份数",
        [],
    )

    assert classification.doc_type == "consent_transfer"
    assert classification.target_code == "知情同意书交接表"
    assert classification.strong_title is True
    assert classification.title_locations == ("head",)
    assert "知情同意书交接记录表" in classification.matched_title


def test_title_position_in_head_has_higher_confidence_than_body() -> None:
    head_classification = classify_page(1, "知情同意书\n受试者知情同意", [])
    before_title = "\n".join([f"普通正文行 {index}" for index in range(1, 22)])
    after_title = "\n".join([f"后续正文行 {index}" for index in range(1, 12)])
    body_classification = classify_page(
        2,
        f"{before_title}\n知情同意书\n受试者知情同意\n{after_title}",
        [],
    )

    assert head_classification.doc_type == "consent"
    assert body_classification.doc_type == "consent"
    assert head_classification.title_locations == ("head",)
    assert body_classification.title_locations == ("body",)
    assert head_classification.confidence > body_classification.confidence


def test_rule_hits_remap_to_current_colon_subject_items() -> None:
    candidates = [
        SubjectItemCandidate(1, "结肠胶囊检查", "COLON_CAPSULE", ()),
        SubjectItemCandidate(2, "结肠镜检查", "COLONOSCOPY", ()),
        SubjectItemCandidate(3, "阅片", "READING", ()),
        SubjectItemCandidate(4, "性能评价", "PERFORMANCE", ()),
    ]

    capsule = classify_page(
        1,
        "胶囊内镜检查报告\n检查所见 诊断意见 诊疗建议 报告医生",
        candidates,
    )
    colonoscopy = classify_page(
        2,
        "电子结肠镜检查报告\n肠镜 检查所见 报告医师 退镜 息肉",
        candidates,
    )
    reading = classify_page(
        3,
        "独立评估人检查图像质量评估表\n独立评估人 阅片 图像质量评估 评估人签名",
        candidates,
    )
    performance = classify_page(
        4,
        "设备常用功能评价表\n设备常用功能 设备稳定性 胶囊定位 下载 传输",
        candidates,
    )

    assert (capsule.display_name, capsule.target_code, capsule.subject_item_id) == (
        "结肠胶囊检查",
        "COLON_CAPSULE",
        1,
    )
    assert (colonoscopy.display_name, colonoscopy.target_code, colonoscopy.subject_item_id) == (
        "结肠镜检查",
        "COLONOSCOPY",
        2,
    )
    assert (reading.display_name, reading.target_code, reading.subject_item_id) == (
        "阅片",
        "READING",
        3,
    )
    assert (performance.display_name, performance.target_code, performance.subject_item_id) == (
        "性能评价",
        "PERFORMANCE",
        4,
    )
    assert "mapped_to_subject_item=结肠胶囊检查(COLON_CAPSULE)" in capsule.reason
    assert "mapped_to_subject_item=阅片(READING)" in reading.reason


def test_rule_hit_without_current_subject_item_does_not_suggest_legacy_item() -> None:
    classification = classify_page(
        1,
        "胶囊内镜检查报告\n检查所见 诊断意见 诊疗建议 报告医生",
        [SubjectItemCandidate(10, "知情同意书", "CONSENT", ())],
    )

    assert classification.doc_type == "capsule_endoscopy_report"
    assert classification.display_name is None
    assert classification.target_code is None
    assert classification.subject_item_id is None
    assert "unmapped_rule=胶囊内镜报告" in classification.reason


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
    assert packet["status"] == "ready", packet["error_message"]

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
    removed_baseline_segment = client.delete(
        f"/api/pdf-packet-segments/{baseline_segment['id']}",
        headers=admin_headers,
    )
    assert removed_baseline_segment.status_code == 204

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


def test_pdf_packet_uses_ocr_text_when_pdf_has_no_text_layer(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pypdf", lambda *_: ["", ""])
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pdftotext", lambda *_: ["", ""])
    monkeypatch.setattr(
        "app.services.pdf_packets.extract_text_with_ocr_api",
        lambda *_: ["知情同意书", "CT检查报告"],
    )
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers).json()
    consent_item = next(item for item in items if item["item_code"] == "V1_INFORMED_CONSENT")

    upload = client.post(
        "/api/pdf-packets/upload",
        headers=admin_headers,
        data={
            "project_id": str(project_id),
            "center_id": str(center_id),
            "subject_id": str(subject["id"]),
        },
        files={"file": ("010001.pdf", create_pdf(["", ""]), "application/pdf")},
    )

    assert upload.status_code == 201
    segments = client.get(
        f"/api/pdf-packets/{upload.json()['id']}/segments",
        headers=admin_headers,
    )
    assert segments.status_code == 200
    suggested_ids = {segment["suggested_subject_item_id"] for segment in segments.json()}
    assert consent_item["id"] in suggested_ids
    assert {segment["detected_name"] for segment in segments.json()} == {"知情同意书", "CT检查报告"}


def test_pdf_packet_defaults_to_current_colon_subject_items(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    colon_ocr_texts = [
        "胶囊内镜检查报告\n检查所见 诊断意见 诊疗建议 报告医生",
        "电子结肠镜检查报告\n肠镜 检查所见 报告医师 退镜 息肉",
        "独立评估人检查图像质量评估表\n独立评估人 阅片 图像质量评估",
        "设备常用功能评价表\n设备常用功能 设备稳定性 胶囊定位 下载 传输",
    ]
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pypdf", lambda *_: [""] * 4)
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pdftotext", lambda *_: [""] * 4)
    monkeypatch.setattr(
        "app.services.pdf_packets.extract_text_with_ocr_api",
        lambda *_: colon_ocr_texts,
    )
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    stage_id = first_trial_stage_id(client, admin_headers, project_id)
    for index, (name, code, keyword) in enumerate(
        [
            ("结肠胶囊检查", "COLON_CAPSULE", "胶囊检查"),
            ("结肠镜检查", "COLONOSCOPY", "结肠镜检查"),
            ("阅片", "READING", "独立评估人\n阅片"),
            ("性能评价", "PERFORMANCE", "设备常用功能\n设备稳定性"),
        ],
        start=1,
    ):
        create_subject_template(
            client,
            admin_headers,
            project_id,
            stage_id,
            name,
            code,
            keyword,
            200 + index,
        )
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers).json()
    item_by_code = {item["item_code"]: item for item in items}

    upload = client.post(
        "/api/pdf-packets/upload",
        headers=admin_headers,
        data={
            "project_id": str(project_id),
            "center_id": str(center_id),
            "subject_id": str(subject["id"]),
        },
        files={"file": ("06012受试者文件夹.pdf", create_pdf(["", "", "", ""]), "application/pdf")},
    )

    assert upload.status_code == 201
    segments = client.get(
        f"/api/pdf-packets/{upload.json()['id']}/segments",
        headers=admin_headers,
    )
    assert segments.status_code == 200
    actual = [
        (segment["detected_name"], segment["detected_code"], segment["suggested_subject_item_id"])
        for segment in segments.json()
    ]
    assert actual == [
        ("结肠胶囊检查", "COLON_CAPSULE", item_by_code["COLON_CAPSULE"]["id"]),
        ("结肠镜检查", "COLONOSCOPY", item_by_code["COLONOSCOPY"]["id"]),
        ("阅片", "READING", item_by_code["READING"]["id"]),
        ("性能评价", "PERFORMANCE", item_by_code["PERFORMANCE"]["id"]),
    ]


def test_pdf_packet_splits_010005_full_27_pages_by_v3_p0_baseline(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pypdf", lambda *_: [""] * 27)
    monkeypatch.setattr(
        "app.services.pdf_packets.extract_text_with_pdftotext",
        lambda *_: [""] * 27,
    )
    monkeypatch.setattr(
        "app.services.pdf_packets.extract_text_with_ocr_api",
        lambda *_: SAMPLE_010005_OCR_TEXTS,
    )
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    sample_path = Path(__file__).resolve().parents[2] / "010005.pdf"

    upload = client.post(
        "/api/pdf-packets/upload",
        headers=admin_headers,
        data={
            "project_id": str(project_id),
            "center_id": str(center_id),
            "subject_id": str(subject["id"]),
        },
        files={"file": ("010005.pdf", sample_path.read_bytes(), "application/pdf")},
    )

    assert upload.status_code == 201
    packet = upload.json()
    assert packet["page_count"] == 27
    assert packet["status"] == "ready"
    assert packet["analysis_summary"] == "12 segments, 27 text/OCR pages"

    response = client.get(f"/api/pdf-packets/{packet['id']}/segments", headers=admin_headers)
    assert response.status_code == 200
    segments = response.json()
    actual_ranges = [
        (segment["page_start"], segment["page_end"], segment["detected_code"])
        for segment in segments
    ]
    assert actual_ranges == [
        (1, 1, "V1_INFORMED_CONSENT"),
        (2, 2, "V1_INFORMED_CONSENT_HANDOVER"),
        (3, 3, "V1_CT_REPORT"),
        (4, 12, "V4_HIS_RECORD"),
        (13, 15, "V1_ENROLLMENT_REVIEW"),
        (16, 16, "V1_VITAL_SIGNS"),
        (17, 17, None),
        (18, 21, None),
        (22, 23, None),
        (24, 24, None),
        (25, 26, None),
        (27, 27, "V2_CAPSULE_ENDOSCOPY_REPORT"),
    ]

    by_page = {
        page: segment["detected_code"]
        for segment in segments
        for page in range(segment["page_start"], segment["page_end"] + 1)
    }
    for boundary_page in (1, 2, 3, 4, 13, 16, 17, 18, 22, 24, 25, 27):
        assert boundary_page in by_page
    assert {by_page[page] for page in range(1, 13)} == {
        "V1_INFORMED_CONSENT",
        "V1_INFORMED_CONSENT_HANDOVER",
        "V1_CT_REPORT",
        "V4_HIS_RECORD",
    }
    assert {by_page[page] for page in range(13, 16)} == {"V1_ENROLLMENT_REVIEW"}
    assert all(by_page[page] != "V1_INFORMED_CONSENT" for page in range(13, 16))
    assert all(by_page[page] != "肠道准备情况" for page in range(20, 24))
    assert all(by_page[page] != "肠道准备情况" for page in range(25, 27))

    debug_report = tmp_path / "file-storage" / "_debug" / "pdf-packet-analysis" / "latest.json"
    assert debug_report.exists()
    debug_payload = json.loads(debug_report.read_text(encoding="utf-8"))
    first_page = debug_payload["pages"][0]
    assert first_page["raw_text"] == SAMPLE_010005_OCR_TEXTS[0]
    assert "normalized_text" in first_page
    assert first_page["head_lines"]
    assert first_page["tail_lines"]
    assert first_page["title_locations"] == ["head"]
    assert debug_payload["segments"][0]["reason"] == "first page"


def test_pdf_packet_manual_split_merge_confirm_and_reanalyze_locking(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pypdf", lambda *_: [""] * 4)
    monkeypatch.setattr("app.services.pdf_packets.extract_text_with_pdftotext", lambda *_: [""] * 4)
    monkeypatch.setattr(
        "app.services.pdf_packets.extract_text_with_ocr_api",
        lambda *_: [
            "知情同意书 受试者知情同意 同意参加",
            "医学影像检查报告单 CT 检查所见 报告医师",
            "门诊病历 主诉 诊断",
            "门诊病历 现病史 处方",
        ],
    )
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers).json()
    consent_item = next(item for item in items if item["item_code"] == "V1_INFORMED_CONSENT")
    his_item = next(item for item in items if item["item_code"] == "V1_HIS_DESCRIPTION")

    upload = client.post(
        "/api/pdf-packets/upload",
        headers=admin_headers,
        data={
            "project_id": str(project_id),
            "center_id": str(center_id),
            "subject_id": str(subject["id"]),
        },
        files={"file": ("010005.pdf", create_pdf(["", "", "", ""]), "application/pdf")},
    )
    assert upload.status_code == 201
    packet_id = upload.json()["id"]
    segments = client.get(f"/api/pdf-packets/{packet_id}/segments", headers=admin_headers).json()
    assert [(segment["page_start"], segment["page_end"]) for segment in segments] == [
        (1, 1),
        (2, 2),
        (3, 4),
    ]

    overlap = client.put(
        f"/api/pdf-packet-segments/{segments[1]['id']}",
        headers=admin_headers,
        json={"page_start": 1, "page_end": 2},
    )
    assert overlap.status_code == 400

    broken_split = client.post(
        f"/api/pdf-packets/{packet_id}/segments/{segments[2]['id']}/split",
        headers=admin_headers,
        json={
            "splits": [
                {"page_start": 3, "page_end": 3, "subject_item_id": his_item["id"]},
                {"page_start": 3, "page_end": 4, "subject_item_id": his_item["id"]},
            ]
        },
    )
    assert broken_split.status_code == 400

    split = client.post(
        f"/api/pdf-packets/{packet_id}/segments/{segments[2]['id']}/split",
        headers=admin_headers,
        json={
            "splits": [
                {"page_start": 3, "page_end": 3, "subject_item_id": his_item["id"]},
                {"page_start": 4, "page_end": 4, "subject_item_id": his_item["id"]},
            ]
        },
    )
    assert split.status_code == 200
    split_segments = split.json()
    assert [(segment["page_start"], segment["page_end"]) for segment in split_segments] == [
        (3, 3),
        (4, 4),
    ]
    assert {segment["status"] for segment in split_segments} == {"manually_modified"}

    non_contiguous_merge = client.post(
        f"/api/pdf-packets/{packet_id}/segments/merge",
        headers=admin_headers,
        json={
            "segment_ids": [segments[0]["id"], split_segments[1]["id"]],
            "subject_item_id": his_item["id"],
        },
    )
    assert non_contiguous_merge.status_code == 400

    merge = client.post(
        f"/api/pdf-packets/{packet_id}/segments/merge",
        headers=admin_headers,
        json={
            "segment_ids": [segment["id"] for segment in split_segments],
            "subject_item_id": his_item["id"],
        },
    )
    assert merge.status_code == 200
    assert (merge.json()["page_start"], merge.json()["page_end"]) == (3, 4)
    assert merge.json()["status"] == "manually_modified"

    confirm = client.post(
        f"/api/pdf-packets/{packet_id}/segments/{segments[0]['id']}/confirm",
        headers=admin_headers,
        json={"subject_item_id": consent_item["id"]},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "manually_confirmed"

    reanalyze = client.post(
        f"/api/pdf-packets/{packet_id}/reanalyze",
        headers=admin_headers,
    )
    assert reanalyze.status_code == 200
    after_reanalyze = client.get(
        f"/api/pdf-packets/{packet_id}/segments",
        headers=admin_headers,
    ).json()
    confirmed = next(segment for segment in after_reanalyze if segment["page_start"] == 1)
    assert confirmed["status"] == "manually_confirmed"

    report = client.get(f"/api/pdf-packets/{packet_id}/analysis-report", headers=admin_headers)
    assert report.status_code == 200
    assert report.json()["pages"][0]["normalized_text"]
    assert report.json()["segments"][0]["reason"]

    unlock_target = confirmed["id"]
    unlock = client.post(
        f"/api/pdf-packets/{packet_id}/segments/{unlock_target}/unlock",
        headers=admin_headers,
    )
    assert unlock.status_code == 200
    assert unlock.json()["status"] == "pending_review"

    confirm_again = client.post(
        f"/api/pdf-packets/{packet_id}/segments/{unlock_target}/confirm",
        headers=admin_headers,
        json={"subject_item_id": consent_item["id"]},
    )
    assert confirm_again.status_code == 200
    force_reanalyze = client.post(
        f"/api/pdf-packets/{packet_id}/reanalyze?force=true",
        headers=admin_headers,
    )
    assert force_reanalyze.status_code == 200
    after_force = client.get(f"/api/pdf-packets/{packet_id}/segments", headers=admin_headers).json()
    assert next(segment for segment in after_force if segment["page_start"] == 1)["status"] != (
        "manually_confirmed"
    )

    uploaded = client.post(
        f"/api/pdf-packet-segments/{after_force[0]['id']}/upload",
        headers=admin_headers,
        json={"subject_item_id": consent_item["id"]},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["segment"]["status"] == "uploaded"

    uploaded_merge = client.post(
        f"/api/pdf-packets/{packet_id}/segments/merge",
        headers=admin_headers,
        json={
            "segment_ids": [after_force[0]["id"], after_force[1]["id"]],
            "subject_item_id": consent_item["id"],
        },
    )
    assert uploaded_merge.status_code == 400


def test_generate_stage_template_keywords_from_subject_files(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "file_storage_root", tmp_path / "file-storage")
    project_id = create_project(client, admin_headers)
    center_id = create_center(client, admin_headers, project_id)
    subject = create_subject(client, admin_headers, project_id, center_id)
    items = client.get(f"/api/subjects/{subject['id']}/items", headers=admin_headers).json()
    consent_item = next(item for item in items if item["item_code"] == "V1_INFORMED_CONSENT")
    upload = client.post(
        "/api/files/upload",
        headers=admin_headers,
        data={"file_category": "clinical_document", "subject_item_id": str(consent_item["id"])},
        files={
            "file": (
                "010001-知情同意书.pdf",
                create_pdf(["受试者知情同意声明"]),
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201
    monkeypatch.setattr(
        "app.services.template_keywords.extract_page_texts",
        lambda *_: ["受试者知情同意声明"],
    )

    generated = client.post(
        "/api/stage-templates/recognition-keywords/from-subject",
        headers=admin_headers,
        json={"subject_id": subject["id"], "mode": "replace"},
    )

    assert generated.status_code == 200
    assert generated.json()["updated_count"] == len(items)
    templates = client.get(
        f"/api/stage-templates?project_id={project_id}&template_scope=subject_item",
        headers=admin_headers,
    )
    assert templates.status_code == 200
    consent_template = next(
        template for template in templates.json() if template["item_code"] == "V1_INFORMED_CONSENT"
    )
    assert "知情同意书" in consent_template["recognition_keywords"]
    assert "受试者知情同意声明" in consent_template["recognition_keywords"]


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
