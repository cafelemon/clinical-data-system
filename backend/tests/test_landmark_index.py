from io import BytesIO

import fitz
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.services import landmark_index
from tests.test_dashboard import create_center, create_project, create_subject, create_user
from tests.test_image_data import image_rows, make_zip, upload_file


def make_frame(
    color: tuple[int, int, int],
    *,
    marked: bool = False,
) -> bytes:
    image = Image.new("RGB", (480, 480), color)
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 60, 410, 420), fill=(color[0] + 5, color[1] + 5, color[2] + 5))
    if marked:
        draw.ellipse((250, 180, 390, 320), outline=(0, 255, 0), width=7)
        draw.text((270, 160), "lesion", fill=(0, 255, 0))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def make_report(image_bytes: bytes) -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((80, 180), "Cecum")
    page.insert_image(fitz.Rect(70, 190, 550, 670), stream=image_bytes)
    payload = document.tobytes()
    document.close()
    return payload


def setup_landmark_subject(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> tuple[int, int, dict[str, dict]]:
    project_id = create_project(client, admin_headers, "LANDMARK")
    center_id = create_center(client, admin_headers, project_id, "LANDMARK")
    create_subject(client, admin_headers, project_id, center_id, "08008")
    records = {
        image_type: image_rows(
            client,
            admin_headers,
            project_id,
            center_id,
            image_type,
        )[0]["record"]
        for image_type in ("raw", "enhanced", "report")
    }
    candidate = make_frame((70, 95, 80))
    marked_report = make_frame((70, 95, 80), marked=True)
    different = make_frame((150, 70, 60))
    raw_files = {
        "08008/PCB250601027/00/000002-0000000-084949.jpeg": candidate,
        "08008/PCB250601027/00/000002-0000020-085021.jpeg": different,
        "08008/PCB250601027/00/000001-0000021-085022.jpeg": candidate,
        "08008/PCB250601027/ispLog.txt": (
            b"[ISP] 000002-0000000-084949.jpeg camid:1-Fset:10\n"
        ),
    }
    enhanced_files = {
        "08008/000002-0000000-084949.jpeg": candidate,
        "08008/000002-0000020-085021.jpeg": different,
        "08008/000001-0000021-085022.jpeg": candidate,
    }

    monkeypatch.setattr(
        landmark_index,
        "_ocr_report_images",
        lambda rows: {rows[0].id: "00:00:33\nCCE-138"},
    )
    assert (
        upload_file(
            client,
            admin_headers,
            records["raw"]["id"],
            "08008_raw.zip",
            make_zip(raw_files),
            "application/zip",
        ).status_code
        == 200
    )
    assert (
        upload_file(
            client,
            admin_headers,
            records["enhanced"]["id"],
            "08008_enhanced.zip",
            make_zip(enhanced_files),
            "application/zip",
        ).status_code
        == 200
    )
    assert (
        upload_file(
            client,
            admin_headers,
            records["report"]["id"],
            "CCE-138.pdf",
            make_report(marked_report),
            "application/pdf",
        ).status_code
        == 200
    )
    return project_id, center_id, records


def test_frame_parsing_elapsed_and_similarity(tmp_path) -> None:
    assert landmark_index.elapsed_seconds("00:00:33 CCE-138") == 33
    assert landmark_index.elapsed_seconds("12:34:56") == 45296
    assert landmark_index.elapsed_seconds("not-a-time") is None

    report = tmp_path / "report.jpg"
    candidate = tmp_path / "candidate.jpg"
    report.write_bytes(make_frame((70, 95, 80), marked=True))
    candidate.write_bytes(make_frame((70, 95, 80)))
    assert landmark_index.image_similarity(report, candidate) > 0.97
    metrics = landmark_index.green_annotation_metrics(report)
    assert metrics["detected"] is True

    natural_green = tmp_path / "natural-green.jpg"
    natural_green.write_bytes(make_frame((70, 130, 95)))
    natural_metrics = landmark_index.green_annotation_metrics(natural_green)
    assert natural_metrics["detected"] is False


def test_landmark_index_resolves_marks_previews_and_confirms(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    _, _, records = setup_landmark_subject(client, admin_headers, monkeypatch)

    response = client.get(
        f"/api/image-data/{records['report']['id']}/landmarks",
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["index_status"] == "indexed"
    assert payload["counts"] == {
        "resolved": 1,
        "approx_matched": 0,
        "unresolved": 0,
        "marked": 1,
    }
    landmark = next(
        row for row in payload["evidence"] if row["evidence_type"] == "landmark_image"
    )
    assert landmark["relative_path"].endswith("000001-0000021-085022.jpeg")
    assert landmark["payload_json"]["elapsed_seconds"] == 33
    assert landmark["payload_json"]["selected_candidate"]["score"] > 0.97

    for variant in ("report", "enhanced", "raw"):
        preview = client.get(
            f"/api/image-evidence/{landmark['id']}/preview",
            headers=admin_headers,
            params={"variant": variant},
        )
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/")

    candidate_key = landmark["payload_json"]["selected_candidate_key"]
    confirmed = client.post(
        f"/api/image-evidence/{landmark['id']}/confirm",
        headers=admin_headers,
        json={"candidate_key": candidate_key},
    )
    assert confirmed.status_code == 200
    confirmed_landmark = next(
        row
        for row in confirmed.json()["evidence"]
        if row["evidence_type"] == "landmark_image"
    )
    assert confirmed_landmark["payload_json"]["manually_confirmed"] is True


def test_landmark_api_waiting_permission_and_rebuild_idempotency(
    client: TestClient,
    admin_headers: dict[str, str],
    monkeypatch,
) -> None:
    project_id = create_project(client, admin_headers, "LANDMARK_WAIT")
    center_id = create_center(client, admin_headers, project_id, "LANDMARK_WAIT")
    create_subject(client, admin_headers, project_id, center_id, "WAIT-001")
    report_record = image_rows(
        client,
        admin_headers,
        project_id,
        center_id,
        "report",
    )[0]["record"]
    waiting = client.get(
        f"/api/image-data/{report_record['id']}/landmarks",
        headers=admin_headers,
    )
    assert waiting.status_code == 200
    assert waiting.json()["index_status"] == "waiting_for_assets"

    readonly_headers = create_user(
        client,
        admin_headers,
        "landmark_readonly",
        "readonly",
        project_ids=[project_id],
    )
    forbidden = client.post(
        f"/api/image-data/{report_record['id']}/landmarks/index",
        headers=readonly_headers,
    )
    assert forbidden.status_code == 403

    _, _, records = setup_landmark_subject(client, admin_headers, monkeypatch)
    first = client.post(
        f"/api/image-data/{records['report']['id']}/landmarks/index",
        headers=admin_headers,
    )
    second = client.post(
        f"/api/image-data/{records['report']['id']}/landmarks/index",
        headers=admin_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["counts"] == second.json()["counts"]
