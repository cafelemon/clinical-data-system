from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.services.trial_protocols import parse_centers, parse_visits

FLOW_PAGE_TEXT = """
（五）试验流程
                                         检查期                     非预期随访
      随访               筛选期 1       胶囊检查    结肠镜检          胶囊排出       胶囊滞留处
                                     日      查日            确认*          理*
     窗口期               -14~ -1 天    第0天    第 0-1 天       第 2-14 天   第 14+1 天
      访视                  V1        V2         V3          V410        V4.111
  签署知情同意书                 √
    人口学资料                 √
    生命体征 3                √         √          √             √           √
   影像学检查 5                √*        √*         √*           √*          √*
   判断入排标准                 √*        √*
   首次肠道准备                 √
   结肠胶囊检查                           √
     二次清肠                           √
     三次清肠                                      √            √*          √*
  备注：带*访视或检查，根据实际情况进行。
"""


CENTER_PAGE_TEXT = """
附件 1：临床试验机构和主要研究者信息

临床试验
              临床试验机构名称         备案号              研究者
机构代号

       首都医科大学附属北京友谊医          械临机构备
 01                                              李鹏
             院                201800254

                              械临机构备
 02     陆军军医大学第二附属医院                             谢霞
                              201800305

       中国人民解放军总医院第二医          械临机构备
 03                                              石卉
            学中心               201900011
"""

APPLE_VISION_CENTER_TEXT = """
附件 1：临床试验机构和主要研究者信息
临床试验机构名称
备案号
研究者
机构代号
首都医科大学附属北京友谊医
01
李鹏
院
201800254
陆军军医大学第二附属医院
02
谢霞
201800305
"""

MIXED_CENTER_TEXT = """
附件 1：临床试验机构和主要研究者信息
机构代号 临床试验机构名称 备案号 研究者
01 李鹏首都医科大学附属北京友谊医院 201800254
"""

RISKY_CENTER_TEXT = """
附件 1：临床试验机构和主要研究者信息
机构代号 临床试验机构名称 备案号 研究者
01 李鹏
"""


def login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def role_id_by_name(client: TestClient, headers: dict[str, str], name: str) -> int:
    response = client.get("/api/roles", headers=headers)
    assert response.status_code == 200
    return next(role["id"] for role in response.json() if role["name"] == name)


def create_project(client: TestClient, headers: dict[str, str], code: str = "PROTOCOL") -> dict:
    response = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": f"{code}项目",
            "code": code,
            "description": "",
            "status": "active",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_user(
    client: TestClient,
    admin_headers: dict[str, str],
    username: str,
    role: str,
    project_ids: list[int] | None = None,
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
            "center_ids": [],
        },
    )
    assert response.status_code == 201
    return login_headers(client, username, "User@12345")


def parsed_draft() -> dict[str, Any]:
    return {
        "visits": [
            {
                "ordinal": 1,
                "source_visit_code": "V1",
                "name": "筛选期",
                "window": "-14~ -1 天",
                "enabled": True,
                "items": [
                    {"ordinal": 1, "name": "签署知情同意书", "required": True, "enabled": True},
                    {"ordinal": 2, "name": "影像学检查", "required": False, "enabled": True},
                ],
            },
            {
                "ordinal": 2,
                "source_visit_code": "V2",
                "name": "检查期-胶囊检查日",
                "window": "第0天",
                "enabled": True,
                "items": [
                    {"ordinal": 1, "name": "结肠胶囊检查", "required": True, "enabled": True},
                ],
            },
        ],
        "centers": [
            {
                "code": "01",
                "name": "首都医科大学附属北京友谊医院",
                "filing_no": "201800254",
                "principal_investigator": "李鹏",
                "enabled": True,
            }
        ],
        "deactivate_missing": {"visits": False, "items": False, "centers": False},
    }


def test_trial_protocol_parser_extracts_visits_and_centers() -> None:
    visits = parse_visits([FLOW_PAGE_TEXT])
    centers = parse_centers([CENTER_PAGE_TEXT])

    assert [visit["name"] for visit in visits] == [
        "筛选期",
        "检查期-胶囊检查日",
        "检查期-结肠镜检查日",
        "非预期随访-胶囊排出确认",
        "非预期随访-胶囊滞留处理",
    ]
    assert visits[0]["items"][0]["name"] == "签署知情同意书"
    optional_items = [item for item in visits[0]["items"] if item["name"] == "判断入排标准"]
    assert optional_items[0]["required"] is False
    assert len(centers) == 3
    assert centers[0]["name"] == "首都医科大学附属北京友谊医院"
    assert centers[0]["principal_investigator"] == "李鹏"
    assert centers[0]["requires_confirmation"] is False
    assert centers[0]["confirmed"] is True
    assert centers[0]["evidence"]["page_no"] == 1
    assert centers[1]["code"] == "02"


def test_trial_protocol_center_parser_handles_apple_vision_line_order() -> None:
    centers = parse_centers([APPLE_VISION_CENTER_TEXT])

    assert len(centers) == 2
    assert centers[0]["name"] == "首都医科大学附属北京友谊医院"
    assert centers[0]["filing_no"] == "201800254"
    assert centers[0]["principal_investigator"] == "李鹏"
    assert centers[0]["requires_confirmation"] is False
    assert centers[1]["name"] == "陆军军医大学第二附属医院"


def test_trial_protocol_center_parser_flags_mixed_or_missing_fields() -> None:
    mixed = parse_centers([MIXED_CENTER_TEXT])
    risky = parse_centers([RISKY_CENTER_TEXT])

    assert mixed[0]["name"] == "首都医科大学附属北京友谊医院"
    assert mixed[0]["principal_investigator"] == "李鹏"
    assert mixed[0]["requires_confirmation"] is True
    assert "OCR行疑似混合机构名称和研究者" in mixed[0]["evidence"]["risk_reasons"]
    assert risky[0]["requires_confirmation"] is True
    assert "备案号缺失或格式异常" in risky[0]["evidence"]["risk_reasons"]


def test_trial_protocol_uses_ocr_text_fallback(monkeypatch, tmp_path: Path) -> None:
    from app.services import trial_protocols
    from app.services.protocol_text_parser import ProtocolTextExtraction, lines_from_page_texts

    protocol_path = tmp_path / "protocol.pdf"
    protocol_path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(trial_protocols, "pdf_page_count", lambda _: 2)
    monkeypatch.setattr(
        trial_protocols,
        "extract_protocol_text",
        lambda *_: ProtocolTextExtraction(
            source="ocr_api",
            page_texts=[FLOW_PAGE_TEXT, CENTER_PAGE_TEXT],
            lines=lines_from_page_texts([FLOW_PAGE_TEXT, CENTER_PAGE_TEXT], "ocr_api"),
        ),
    )

    page_count, draft, *_ = trial_protocols.parse_protocol_file(protocol_path)

    assert page_count == 2
    assert len(draft["visits"]) == 5
    assert len(draft["centers"]) == 3
    assert draft["parse_meta"]["text_source"] == "ocr_api"


def test_protocol_text_ocr_api_keeps_block_and_text_line_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from app.services import protocol_text_parser

    protocol_path = tmp_path / "protocol.pdf"
    protocol_path.write_bytes(b"%PDF-1.4")
    include_blocks_values: list[bool] = []

    class FakeOcrClient:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def ocr_pdf_payload(
            self,
            *_: Any,
            include_blocks: bool = False,
            **__: Any,
        ) -> dict[str, Any]:
            include_blocks_values.append(include_blocks)
            return {
                "pages": [
                    {
                        "page_no": 1,
                        "text": "第一页",
                        "blocks": [
                            {
                                "text": "第一页 block",
                                "confidence": 0.88,
                                "box": {"x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0},
                            }
                        ],
                    },
                    {"page_no": 2, "text": "第二页纯文本\n第二行"},
                ]
            }

    monkeypatch.setattr(protocol_text_parser, "PaddleOcrClient", FakeOcrClient)
    monkeypatch.setattr(protocol_text_parser.settings, "pdf_packet_ocr_api_url", "http://ocr")

    extraction = protocol_text_parser.extract_text_with_ocr_api(protocol_path, page_count=2)

    assert include_blocks_values == [True]
    assert extraction.lines[0].page_no == 1
    assert extraction.lines[0].confidence == 0.88
    assert [line.page_no for line in extraction.lines[1:]] == [2, 2]


def test_trial_protocol_upload_draft_apply_and_versioning(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    from app.api.v1.endpoints import trial_protocols as endpoint

    project = create_project(client, admin_headers)
    monkeypatch.setattr(
        endpoint,
        "parse_protocol_file",
        lambda _: (42, parsed_draft(), "XG2418", "1.1", "2025 年 4 月 11 日"),
    )

    upload = client.post(
        f"/api/projects/{project['id']}/protocol-versions",
        headers=admin_headers,
        files={"file": ("protocol.pdf", b"%PDF-1.4\nsource", "application/pdf")},
    )
    assert upload.status_code == 201
    version = upload.json()
    assert version["version_number"] == 1
    assert version["protocol_no"] == "XG2418"
    assert len(version["draft_json"]["visits"]) == 2

    draft = version["draft_json"]
    draft["visits"][0]["items"][0]["name"] = "知情同意书"
    save = client.patch(
        f"/api/projects/{project['id']}/protocol-versions/{version['id']}/draft",
        headers=admin_headers,
        json=draft,
    )
    assert save.status_code == 200
    assert save.json()["draft_json"]["visits"][0]["items"][0]["name"] == "知情同意书"

    first_apply = client.post(
        f"/api/projects/{project['id']}/protocol-versions/{version['id']}/apply",
        headers=admin_headers,
    )
    assert first_apply.status_code == 200
    assert first_apply.json()["result"]["created_stages"] == 2
    assert first_apply.json()["result"]["created_centers"] == 1

    second_apply = client.post(
        f"/api/projects/{project['id']}/protocol-versions/{version['id']}/apply",
        headers=admin_headers,
    )
    assert second_apply.status_code == 200
    assert second_apply.json()["result"]["created_stages"] == 0
    assert second_apply.json()["result"]["updated_stages"] == 2

    stages = client.get(
        f"/api/stages?project_id={project['id']}&phase_code=TRIAL&include_system=false",
        headers=admin_headers,
    )
    assert stages.status_code == 200
    assert any(stage["name"] == "访视1:筛选期" for stage in stages.json())
    centers = client.get(f"/api/centers?project_id={project['id']}", headers=admin_headers)
    assert centers.status_code == 200
    assert centers.json()[0]["contact_person"] == "李鹏"

    versions = client.get(f"/api/projects/{project['id']}/protocol-versions", headers=admin_headers)
    assert versions.status_code == 200
    assert versions.json()[0]["version_number"] == 1


def test_trial_protocol_apply_blocks_unconfirmed_risky_center(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    from app.api.v1.endpoints import trial_protocols as endpoint

    project = create_project(client, admin_headers, "RISKY_PROTOCOL")
    risky_draft = parsed_draft()
    risky_draft["centers"][0].update(
        {
            "requires_confirmation": True,
            "confirmed": False,
            "confidence": 0.58,
            "evidence": {"page_no": 9, "risk_reasons": ["研究者疑似混入机构名称"]},
        }
    )
    monkeypatch.setattr(
        endpoint,
        "parse_protocol_file",
        lambda _: (1, risky_draft, None, None, None),
    )

    upload = client.post(
        f"/api/projects/{project['id']}/protocol-versions",
        headers=admin_headers,
        files={"file": ("protocol.pdf", b"%PDF", "application/pdf")},
    )
    assert upload.status_code == 201
    version = upload.json()

    blocked = client.post(
        f"/api/projects/{project['id']}/protocol-versions/{version['id']}/apply",
        headers=admin_headers,
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "存在未确认的高风险中心字段，请确认后再应用"

    draft = version["draft_json"]
    draft["centers"][0]["confirmed"] = True
    save = client.patch(
        f"/api/projects/{project['id']}/protocol-versions/{version['id']}/draft",
        headers=admin_headers,
        json=draft,
    )
    assert save.status_code == 200
    allowed = client.post(
        f"/api/projects/{project['id']}/protocol-versions/{version['id']}/apply",
        headers=admin_headers,
    )
    assert allowed.status_code == 200
    assert allowed.json()["result"]["created_centers"] == 1


def test_trial_protocol_project_manager_scope(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    from app.api.v1.endpoints import trial_protocols as endpoint

    own_project = create_project(client, admin_headers, "OWN_PROTOCOL")
    other_project = create_project(client, admin_headers, "OTHER_PROTOCOL")
    manager_headers = create_user(
        client,
        admin_headers,
        "protocol_pm",
        "project_manager",
        [own_project["id"]],
    )
    monkeypatch.setattr(
        endpoint,
        "parse_protocol_file",
        lambda _: (1, parsed_draft(), None, None, None),
    )

    allowed = client.post(
        f"/api/projects/{own_project['id']}/protocol-versions",
        headers=manager_headers,
        files={"file": ("protocol.pdf", b"%PDF", "application/pdf")},
    )
    assert allowed.status_code == 201

    denied = client.post(
        f"/api/projects/{other_project['id']}/protocol-versions",
        headers=manager_headers,
        files={"file": ("protocol.pdf", b"%PDF", "application/pdf")},
    )
    assert denied.status_code == 403
