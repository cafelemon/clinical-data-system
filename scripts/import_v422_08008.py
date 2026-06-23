#!/usr/bin/env python3
"""Import and verify the V4.2.2 Wuhan 08008 acceptance sample through app APIs."""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402
from app.services import landmark_index  # noqa: E402

PROJECT_CODE = "C200CN"
CENTER_CODE = "08"
SCREENING_NO = "08008"
REPORT_TIMES = [
    "00:00:33",
    "00:00:34",
    "04:36:52",
    "04:22:06",
    "05:06:09",
    "05:11:32",
    "06:30:32",
    "07:01:44",
    "10:49:03",
    "12:00:15",
    "12:34:36",
]
RAW_ZIP = Path("/tmp/08008_raw_v422.zip")
ENHANCED_ZIP = Path("/tmp/08008_enhanced_v422.zip")
REPORT_PDF = ROOT / "V4材料" / "CCE-138.pdf"


def require_ok(response, action: str):
    if response.status_code >= 400:
        raise RuntimeError(f"{action} failed: {response.status_code} {response.text[:500]}")
    return response


def sample_ocr(report_images):
    result: dict[int, str] = {}
    time_index = 0
    for row in report_images:
        metadata = row.payload_json or {}
        if int(metadata.get("width") or 0) >= 300 and int(metadata.get("height") or 0) >= 300:
            result[row.id] = f"{REPORT_TIMES[time_index]}\nCCE-138"
            time_index += 1
        else:
            result[row.id] = ""
    if time_index != len(REPORT_TIMES):
        raise RuntimeError(
            f"expected {len(REPORT_TIMES)} report frames, found {time_index}"
        )
    return result


def resolve_scope(client: TestClient, headers: dict[str, str]) -> tuple[int, int]:
    projects = require_ok(
        client.get("/api/projects", headers=headers),
        "list projects",
    ).json()
    project = next(project for project in projects if project["code"] == PROJECT_CODE)
    centers = require_ok(
        client.get(
            "/api/centers",
            headers=headers,
            params={"project_id": project["id"]},
        ),
        "list centers",
    ).json()
    center = next(center for center in centers if center["code"] == CENTER_CODE)
    return project["id"], center["id"]


def find_or_create_subject(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    center_id: int,
) -> dict:
    subjects = require_ok(
        client.get(
            "/api/subjects",
            headers=headers,
            params={"project_id": project_id, "center_id": center_id},
        ),
        "list subjects",
    ).json()
    existing = next(
        (subject for subject in subjects if subject["screening_no"] == SCREENING_NO),
        None,
    )
    if existing is not None:
        return existing
    return require_ok(
        client.post(
            "/api/subjects",
            headers=headers,
            json={
                "project_id": project_id,
                "center_id": center_id,
                "screening_no": SCREENING_NO,
                "subject_arm": "experimental",
                "gender": "女",
                "age": 55,
            },
        ),
        "create subject",
    ).json()


def image_record(
    client: TestClient,
    headers: dict[str, str],
    image_type: str,
    project_id: int,
    center_id: int,
) -> dict:
    rows = require_ok(
        client.get(
            "/api/image-data",
            headers=headers,
            params={
                "project_id": project_id,
                "center_id": center_id,
                "image_type": image_type,
            },
        ),
        f"list {image_type} records",
    ).json()
    return next(row["record"] for row in rows if row["screening_no"] == SCREENING_NO)


def upload(
    client: TestClient,
    headers: dict[str, str],
    record_id: int,
    path: Path,
    content_type: str,
) -> dict:
    if not path.is_file():
        raise RuntimeError(f"acceptance file missing: {path}")
    with path.open("rb") as input_file:
        response = client.post(
            f"/api/image-data/{record_id}/upload",
            headers=headers,
            files={"file": (path.name, input_file, content_type)},
        )
    return require_ok(response, f"upload {path.name}").json()["record"]


def main() -> None:
    landmark_index._ocr_report_images = sample_ocr
    with TestClient(app) as client:
        login = require_ok(
            client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "Admin@123456"},
            ),
            "admin login",
        ).json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        project_id, center_id = resolve_scope(client, headers)
        subject = find_or_create_subject(
            client,
            headers,
            project_id,
            center_id,
        )
        raw = image_record(client, headers, "raw", project_id, center_id)
        enhanced = image_record(client, headers, "enhanced", project_id, center_id)
        report = image_record(client, headers, "report", project_id, center_id)

        raw = upload(client, headers, raw["id"], RAW_ZIP, "application/zip")
        enhanced = upload(
            client,
            headers,
            enhanced["id"],
            ENHANCED_ZIP,
            "application/zip",
        )
        report = upload(
            client,
            headers,
            report["id"],
            REPORT_PDF,
            "application/pdf",
        )
        landmarks = require_ok(
            client.get(
                f"/api/image-data/{report['id']}/landmarks",
                headers=headers,
            ),
            "read landmarks",
        ).json()
        summary = {
            "subject": {
                "id": subject["id"],
                "screening_no": subject["screening_no"],
                "gender": subject["gender"],
                "age": subject["age"],
            },
            "raw": {
                "record_id": raw["id"],
                "version": raw["version"],
                "image_count": raw["image_count"],
            },
            "enhanced": {
                "record_id": enhanced["id"],
                "version": enhanced["version"],
                "image_count": enhanced["image_count"],
            },
            "report": {
                "record_id": report["id"],
                "version": report["version"],
            },
            "landmarks": {
                "index_status": landmarks["index_status"],
                "counts": landmarks["counts"],
            },
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if raw["image_count"] != 60728 or enhanced["image_count"] != 60728:
            raise RuntimeError("raw/enhanced image count must both equal 60728")
        if landmarks["counts"]["resolved"] != 11:
            raise RuntimeError("all 11 report timepoints must resolve")


if __name__ == "__main__":
    main()
