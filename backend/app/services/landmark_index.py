import hashlib
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path
from app.models import ImageEvidenceIndex, SubjectImageRecord
from app.models.image_evidence import (
    IMAGE_EVIDENCE_LANDMARK_IMAGE,
    IMAGE_EVIDENCE_MARKED_IMAGE,
    IMAGE_EVIDENCE_MATCH_APPROX,
    IMAGE_EVIDENCE_MATCH_RESOLVED,
    IMAGE_EVIDENCE_MATCH_UNRESOLVED,
    IMAGE_EVIDENCE_REPORT_IMAGE,
    IMAGE_EVIDENCE_REPORT_PACKAGE,
)
from app.services.ocr_client import OcrClientError, PaddleOcrClient

LANDMARK_SOURCE = "report_timepoint"
MARKED_SOURCE = "report_green_annotation"
LANDMARK_TYPES = (IMAGE_EVIDENCE_LANDMARK_IMAGE, IMAGE_EVIDENCE_MARKED_IMAGE)
TIME_PATTERN = re.compile(r"(?<!\d)(\d{1,2}):(\d{2}):(\d{2})(?!\d)")
FRAME_PATTERN = re.compile(
    r"(?P<camera>\d{6})-(?P<frame>\d{7})-(?P<clock>\d{6})\.(?:jpe?g|png)$",
    re.IGNORECASE,
)
ISP_LINE_PATTERN = re.compile(
    r"\[ISP\]\s+(?P<filename>\d{6}-\d{7}-\d{6}\.(?:jpe?g|png))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FrameFile:
    path: Path
    relative_path: str
    filename: str
    camera: str
    frame_no: int
    clock_seconds: int


@dataclass(frozen=True)
class LandmarkBuildResult:
    report_record_id: int
    raw_record_id: int | None
    enhanced_record_id: int | None
    index_status: str
    warning: str | None
    evidence: list[ImageEvidenceIndex]


def _record_map(db: Session, subject_id: int) -> dict[str, SubjectImageRecord]:
    records = list(
        db.scalars(
            select(SubjectImageRecord).where(SubjectImageRecord.subject_id == subject_id)
        )
    )
    return {record.image_type: record for record in records}


def _report_package(db: Session, report_record_id: int) -> ImageEvidenceIndex | None:
    return db.scalar(
        select(ImageEvidenceIndex)
        .where(
            ImageEvidenceIndex.subject_image_record_id == report_record_id,
            ImageEvidenceIndex.evidence_type == IMAGE_EVIDENCE_REPORT_PACKAGE,
        )
        .order_by(ImageEvidenceIndex.id.desc())
    )


def _set_report_summary(
    db: Session,
    report_record: SubjectImageRecord,
    *,
    index_status: str,
    warning: str | None,
    counts: dict[str, int],
    raw_record: SubjectImageRecord | None,
    enhanced_record: SubjectImageRecord | None,
    indexed_at: datetime,
) -> None:
    package = _report_package(db, report_record.id)
    if package is None:
        return
    payload = dict(package.payload_json or {})
    payload["landmark_index"] = {
        "index_status": index_status,
        "warning": warning,
        "counts": counts,
        "versions": {
            "report": report_record.version,
            "raw": raw_record.version if raw_record else None,
            "enhanced": enhanced_record.version if enhanced_record else None,
        },
        "indexed_at": indexed_at.isoformat(),
    }
    package.payload_json = payload
    package.updated_at = indexed_at


def _summary_from_report_package(
    package: ImageEvidenceIndex | None,
) -> tuple[str | None, str | None]:
    if package is None:
        return None, None
    summary = (package.payload_json or {}).get("landmark_index")
    if not isinstance(summary, dict):
        return None, None
    status = summary.get("index_status")
    warning = summary.get("warning")
    return (
        status if isinstance(status, str) else None,
        warning if isinstance(warning, str) else None,
    )


def _clear_landmark_rows(db: Session, subject_id: int) -> None:
    rows = list(
        db.scalars(
            select(ImageEvidenceIndex).where(
                ImageEvidenceIndex.subject_id == subject_id,
                ImageEvidenceIndex.evidence_type.in_(LANDMARK_TYPES),
            )
        )
    )
    for row in rows:
        db.delete(row)
    db.flush()


def clear_landmark_index(db: Session, subject_id: int) -> None:
    _clear_landmark_rows(db, subject_id)


def _confirmed_candidates(
    db: Session,
    subject_id: int,
    versions: dict[str, int],
) -> dict[str, str]:
    confirmed: dict[str, str] = {}
    rows = list(
        db.scalars(
            select(ImageEvidenceIndex).where(
                ImageEvidenceIndex.subject_id == subject_id,
                ImageEvidenceIndex.evidence_type == IMAGE_EVIDENCE_LANDMARK_IMAGE,
            )
        )
    )
    for row in rows:
        payload = row.payload_json or {}
        if payload.get("versions") != versions or not payload.get("manually_confirmed"):
            continue
        report_hash = payload.get("report_image_hash")
        candidate_key = payload.get("selected_candidate_key")
        if isinstance(report_hash, str) and isinstance(candidate_key, str):
            confirmed[report_hash] = candidate_key
    return confirmed


def _clock_seconds(value: str) -> int:
    return int(value[:2]) * 3600 + int(value[2:4]) * 60 + int(value[4:6])


def parse_frame_filename(path: Path, root: Path, record: SubjectImageRecord) -> FrameFile | None:
    match = FRAME_PATTERN.search(path.name)
    if match is None:
        return None
    relative = (Path(record.extracted_dir or "") / path.relative_to(root)).as_posix()
    return FrameFile(
        path=path,
        relative_path=relative,
        filename=path.name,
        camera=match.group("camera"),
        frame_no=int(match.group("frame")),
        clock_seconds=_clock_seconds(match.group("clock")),
    )


def scan_frame_files(record: SubjectImageRecord) -> list[FrameFile]:
    if not record.extracted_dir:
        return []
    root = ensure_relative_path(settings.file_storage_root, record.extracted_dir)
    if not root.exists():
        return []
    frames: list[FrameFile] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parsed = parse_frame_filename(path, root, record)
        if parsed is not None:
            frames.append(parsed)
    return sorted(frames, key=lambda item: (item.frame_no, item.camera, item.filename))


def _first_frame_from_isp_log(raw_record: SubjectImageRecord) -> str | None:
    if not raw_record.storage_path:
        return None
    archive_path = ensure_relative_path(settings.file_storage_root, raw_record.storage_path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            log_name = next(
                (
                    name
                    for name in archive.namelist()
                    if Path(name).name.lower() == "isplog.txt"
                ),
                None,
            )
            if log_name is None:
                return None
            with archive.open(log_name) as log:
                for raw_line in log:
                    line = raw_line.decode("utf-8", errors="ignore")
                    match = ISP_LINE_PATTERN.search(line)
                    if match is not None:
                        return match.group("filename")
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def determine_first_frame_seconds(
    raw_record: SubjectImageRecord,
    raw_frames: list[FrameFile],
) -> int | None:
    first_filename = _first_frame_from_isp_log(raw_record)
    if first_filename:
        match = FRAME_PATTERN.search(first_filename)
        if match is not None:
            return _clock_seconds(match.group("clock"))
    if not raw_frames:
        return None
    return min(raw_frames, key=lambda item: item.frame_no).clock_seconds


def elapsed_seconds(value: str) -> int | None:
    match = TIME_PATTERN.search(value)
    if match is None:
        return None
    hours, minutes, seconds = (int(part) for part in match.groups())
    if minutes > 59 or seconds > 59:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _decode_image(path: Path) -> np.ndarray | None:
    try:
        payload = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    return cv2.imdecode(payload, cv2.IMREAD_COLOR)


def _green_annotation_mask(image: np.ndarray) -> np.ndarray:
    """Return marker-like green pixels, not the capsule image's natural green tint."""

    blue, green, red = cv2.split(image)
    return (
        (green >= 130)
        & (green.astype(np.int16) - red.astype(np.int16) >= 60)
        & (green.astype(np.int16) - blue.astype(np.int16) >= 40)
        & (red <= 100)
        & (blue <= 140)
    ).astype(np.uint8) * 255


def green_annotation_metrics(path: Path) -> dict[str, float | int | bool]:
    image = _decode_image(path)
    if image is None:
        return {"detected": False, "green_ratio": 0.0, "largest_area": 0}
    mask = _green_annotation_mask(image)
    green_pixels = int(cv2.countNonZero(mask))
    ratio = green_pixels / float(mask.shape[0] * mask.shape[1])
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = int(max((cv2.contourArea(contour) for contour in contours), default=0))
    return {
        "detected": bool(ratio >= 0.0015 and largest >= 80),
        "green_ratio": round(ratio, 6),
        "largest_area": largest,
    }


def image_similarity(report_path: Path, candidate_path: Path) -> float:
    report = _decode_image(report_path)
    candidate = _decode_image(candidate_path)
    if report is None or candidate is None:
        return 0.0
    if candidate.shape[:2] != report.shape[:2]:
        candidate = cv2.resize(
            candidate,
            (report.shape[1], report.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
    height, width = report.shape[:2]
    mask = np.full((height, width), 255, dtype=np.uint8)
    mask[: max(48, height // 9), : max(170, width // 2)] = 0
    green_mask = _green_annotation_mask(report)
    mask[green_mask > 0] = 0
    report_gray = cv2.cvtColor(report, cv2.COLOR_BGR2GRAY)
    candidate_gray = cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY)
    mask[(report_gray < 4) & (candidate_gray < 4)] = 0
    valid = mask > 0
    if int(valid.sum()) < height * width * 0.25:
        return 0.0
    diff = cv2.absdiff(report, candidate).astype(np.float32)
    mean_diff = float(diff[valid].mean()) / 255.0
    return round(max(0.0, min(1.0, 1.0 - mean_diff)), 6)


def _file_digest(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as input_file:
        while chunk := input_file.read(1024 * 1024):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _report_image_path(row: ImageEvidenceIndex) -> Path:
    return ensure_relative_path(settings.file_storage_root, row.relative_path or "")


def _ocr_report_images(report_images: list[ImageEvidenceIndex]) -> dict[int, str]:
    if not settings.pdf_packet_ocr_api_url:
        raise OcrClientError("OCR API is not configured")
    document = fitz.open()
    ordered: list[int] = []
    try:
        for row in report_images:
            image_path = _report_image_path(row)
            metadata = row.payload_json or {}
            width = float(metadata.get("width") or 480)
            height = float(metadata.get("height") or 480)
            page = document.new_page(width=width, height=height)
            page.insert_image(page.rect, filename=str(image_path))
            ordered.append(row.id)
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            document.save(temp_file.name)
            client = PaddleOcrClient(
                settings.pdf_packet_ocr_api_url,
                timeout_seconds=settings.pdf_packet_ocr_timeout_seconds,
            )
            payload = client.ocr_pdf_payload(
                Path(temp_file.name),
                page_count=len(ordered),
                dpi=settings.pdf_packet_ocr_dpi,
                include_blocks=True,
            )
    finally:
        document.close()
    result: dict[int, str] = {}
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise OcrClientError("OCR response missing pages")
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_no = page.get("page_no")
        if not isinstance(page_no, int) or not 1 <= page_no <= len(ordered):
            continue
        texts: list[str] = []
        blocks = page.get("blocks")
        if isinstance(blocks, list):
            texts.extend(
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            )
        if not texts and isinstance(page.get("text"), str):
            texts.append(page["text"])
        result[ordered[page_no - 1]] = "\n".join(texts)
    return result


def _title_for_image(
    report_path: Path,
    row: ImageEvidenceIndex,
) -> str | None:
    metadata = row.payload_json or {}
    occurrences = metadata.get("occurrences")
    if not isinstance(occurrences, list) or not occurrences:
        return None
    occurrence = occurrences[0]
    if not isinstance(occurrence, dict):
        return None
    page_no = occurrence.get("page")
    rects = occurrence.get("rects")
    if not isinstance(page_no, int) or not isinstance(rects, list) or not rects:
        return None
    image_rect = rects[0]
    if not isinstance(image_rect, dict):
        return None
    try:
        x0 = float(image_rect["x0"])
        y0 = float(image_rect["y0"])
        x1 = float(image_rect["x1"])
    except (KeyError, TypeError, ValueError):
        return None
    with fitz.open(report_path) as document:
        if not 1 <= page_no <= document.page_count:
            return None
        blocks = document.load_page(page_no - 1).get_text("blocks")
    candidates: list[tuple[float, str]] = []
    for block in blocks:
        bx0, by0, bx1, by1, text = block[:5]
        overlap = min(x1, bx1) - max(x0, bx0)
        distance = y0 - by1
        cleaned = " ".join(str(text).split())
        if overlap > 0 and -3 <= distance <= 55 and cleaned:
            candidates.append((abs(distance), cleaned))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1][:120]


def _candidate_status(scored: list[dict[str, Any]]) -> str:
    if not scored:
        return IMAGE_EVIDENCE_MATCH_UNRESOLVED
    best = float(scored[0]["score"])
    runner_up = float(scored[1]["score"]) if len(scored) > 1 else 0.0
    if best >= 0.93 and (len(scored) == 1 or best - runner_up >= 0.003):
        return IMAGE_EVIDENCE_MATCH_RESOLVED
    return IMAGE_EVIDENCE_MATCH_APPROX


def _index_status(counts: dict[str, int]) -> str:
    total = counts["resolved"] + counts["approx_matched"] + counts["unresolved"]
    if total == 0:
        return "unresolved"
    if counts["resolved"] == total:
        return "indexed"
    if counts["resolved"] or counts["approx_matched"]:
        return "partial"
    return "unresolved"


def rebuild_landmark_index(
    db: Session,
    report_record: SubjectImageRecord,
    *,
    indexed_by: int | None,
) -> LandmarkBuildResult:
    records = _record_map(db, report_record.subject_id)
    raw_record = records.get("raw")
    enhanced_record = records.get("enhanced")
    indexed_at = datetime.now(UTC)
    if (
        report_record.image_type != "report"
        or report_record.upload_status != "uploaded"
        or raw_record is None
        or enhanced_record is None
        or raw_record.upload_status != "uploaded"
        or enhanced_record.upload_status != "uploaded"
    ):
        return LandmarkBuildResult(
            report_record_id=report_record.id,
            raw_record_id=raw_record.id if raw_record else None,
            enhanced_record_id=enhanced_record.id if enhanced_record else None,
            index_status="waiting_for_assets",
            warning="原始图像、增强图像和 PDF 电子报告齐全后才能反查 Landmark",
            evidence=[],
        )
    if (report_record.file_ext or "").lower() != "pdf":
        _clear_landmark_rows(db, report_record.subject_id)
        _set_report_summary(
            db,
            report_record,
            index_status="not_supported",
            warning="Landmark 反查当前仅支持 PDF 电子报告",
            counts={"resolved": 0, "approx_matched": 0, "unresolved": 0, "marked": 0},
            raw_record=raw_record,
            enhanced_record=enhanced_record,
            indexed_at=indexed_at,
        )
        return LandmarkBuildResult(
            report_record_id=report_record.id,
            raw_record_id=raw_record.id,
            enhanced_record_id=enhanced_record.id,
            index_status="not_supported",
            warning="Landmark 反查当前仅支持 PDF 电子报告",
            evidence=[],
        )

    versions = {
        "report": report_record.version,
        "raw": raw_record.version,
        "enhanced": enhanced_record.version,
    }
    confirmations = _confirmed_candidates(db, report_record.subject_id, versions)
    _clear_landmark_rows(db, report_record.subject_id)
    report_images = list(
        db.scalars(
            select(ImageEvidenceIndex)
            .where(
                ImageEvidenceIndex.subject_image_record_id == report_record.id,
                ImageEvidenceIndex.evidence_type == IMAGE_EVIDENCE_REPORT_IMAGE,
            )
            .order_by(ImageEvidenceIndex.id)
        )
    )
    if not report_images:
        warning = "电子报告尚未建立可用的报告图片索引"
        _set_report_summary(
            db,
            report_record,
            index_status="unresolved",
            warning=warning,
            counts={"resolved": 0, "approx_matched": 0, "unresolved": 0, "marked": 0},
            raw_record=raw_record,
            enhanced_record=enhanced_record,
            indexed_at=indexed_at,
        )
        return LandmarkBuildResult(
            report_record_id=report_record.id,
            raw_record_id=raw_record.id,
            enhanced_record_id=enhanced_record.id,
            index_status="unresolved",
            warning=warning,
            evidence=[],
        )

    report_path = ensure_relative_path(settings.file_storage_root, report_record.storage_path or "")
    ocr_texts = _ocr_report_images(report_images)
    raw_frames = scan_frame_files(raw_record)
    enhanced_frames = scan_frame_files(enhanced_record)
    first_frame = determine_first_frame_seconds(raw_record, raw_frames)
    raw_by_name = {frame.filename: frame for frame in raw_frames}
    enhanced_by_second: dict[int, list[FrameFile]] = {}
    for frame in enhanced_frames:
        enhanced_by_second.setdefault(frame.clock_seconds, []).append(frame)
    counts = {"resolved": 0, "approx_matched": 0, "unresolved": 0, "marked": 0}
    created: list[ImageEvidenceIndex] = []

    for report_image in report_images:
        metadata = report_image.payload_json or {}
        if int(metadata.get("width") or 0) < 300 or int(metadata.get("height") or 0) < 300:
            continue
        report_image_path = _report_image_path(report_image)
        report_text = ocr_texts.get(report_image.id, "")
        elapsed = elapsed_seconds(report_text)
        if elapsed is None:
            continue
        title = _title_for_image(report_path, report_image)
        annotation = green_annotation_metrics(report_image_path)
        if annotation["detected"]:
            marked = ImageEvidenceIndex(
                project_id=report_record.project_id,
                center_id=report_record.center_id,
                subject_id=report_record.subject_id,
                subject_image_record_id=report_record.id,
                evidence_type=IMAGE_EVIDENCE_MARKED_IMAGE,
                evidence_source=MARKED_SOURCE,
                relative_path=report_image.relative_path,
                match_status=None,
                file_hash=report_image.file_hash,
                file_size=report_image.file_size,
                gastrointestinal_location=title,
                payload_json={
                    "report_image_id": report_image.id,
                    "report_image_hash": report_image.file_hash,
                    "elapsed_time": TIME_PATTERN.search(report_text).group(0),
                    "annotation": annotation,
                    "versions": versions,
                },
                indexed_by=indexed_by,
                indexed_at=indexed_at,
            )
            db.add(marked)
            created.append(marked)
            counts["marked"] += 1

        candidates: list[FrameFile] = []
        target_second = None
        if first_frame is not None:
            target_second = (first_frame + elapsed) % (24 * 3600)
            for delta in (-1, 0, 1):
                candidates.extend(
                    enhanced_by_second.get((target_second + delta) % (24 * 3600), [])
                )
        scored: list[dict[str, Any]] = []
        for candidate in candidates:
            raw_candidate = raw_by_name.get(candidate.filename)
            if raw_candidate is None:
                continue
            scored.append(
                {
                    "candidate_key": candidate.relative_path,
                    "score": image_similarity(report_image_path, candidate.path),
                    "enhanced_relative_path": candidate.relative_path,
                    "raw_relative_path": raw_candidate.relative_path,
                    "filename": candidate.filename,
                    "camera": candidate.camera,
                    "frame_no": candidate.frame_no,
                    "clock_seconds": candidate.clock_seconds,
                }
            )
        scored.sort(key=lambda item: (-float(item["score"]), int(item["frame_no"])))
        scored = scored[:8]
        status = _candidate_status(scored)
        selected = scored[0] if scored else None
        manually_confirmed = False
        confirmed_key = confirmations.get(report_image.file_hash or "")
        if confirmed_key:
            confirmed = next(
                (item for item in scored if item["candidate_key"] == confirmed_key),
                None,
            )
            if confirmed is not None:
                selected = confirmed
                status = IMAGE_EVIDENCE_MATCH_RESOLVED
                manually_confirmed = True
        file_hash = None
        file_size = None
        relative_path = None
        if selected is not None:
            raw_path = ensure_relative_path(
                settings.file_storage_root,
                selected["raw_relative_path"],
            )
            file_hash, file_size = _file_digest(raw_path)
            relative_path = selected["raw_relative_path"]
        counts[status] += 1
        landmark = ImageEvidenceIndex(
            project_id=raw_record.project_id,
            center_id=raw_record.center_id,
            subject_id=raw_record.subject_id,
            subject_image_record_id=raw_record.id,
            evidence_type=IMAGE_EVIDENCE_LANDMARK_IMAGE,
            evidence_source=LANDMARK_SOURCE,
            relative_path=relative_path,
            match_status=status,
            file_hash=file_hash,
            file_size=file_size,
            gastrointestinal_location=title,
            payload_json={
                "report_record_id": report_record.id,
                "report_image_id": report_image.id,
                "report_relative_path": report_image.relative_path,
                "report_image_hash": report_image.file_hash,
                "elapsed_time": TIME_PATTERN.search(report_text).group(0),
                "elapsed_seconds": elapsed,
                "first_frame_seconds": first_frame,
                "target_clock_seconds": target_second,
                "selected_candidate_key": selected["candidate_key"] if selected else None,
                "selected_candidate": selected,
                "candidates": scored,
                "marked": bool(annotation["detected"]),
                "annotation": annotation,
                "manually_confirmed": manually_confirmed,
                "confirmed_by": indexed_by if manually_confirmed else None,
                "versions": versions,
            },
            indexed_by=indexed_by,
            indexed_at=indexed_at,
        )
        db.add(landmark)
        created.append(landmark)

    index_status = _index_status(counts)
    warning = None if index_status == "indexed" else "部分报告图未能唯一定位，需要人工复核"
    _set_report_summary(
        db,
        report_record,
        index_status=index_status,
        warning=warning,
        counts=counts,
        raw_record=raw_record,
        enhanced_record=enhanced_record,
        indexed_at=indexed_at,
    )
    db.flush()
    return LandmarkBuildResult(
        report_record_id=report_record.id,
        raw_record_id=raw_record.id,
        enhanced_record_id=enhanced_record.id,
        index_status=index_status,
        warning=warning,
        evidence=created,
    )


def maybe_rebuild_landmark_index(
    db: Session,
    subject_id: int,
    *,
    indexed_by: int | None,
) -> LandmarkBuildResult | None:
    records = _record_map(db, subject_id)
    report_record = records.get("report")
    if report_record is None:
        return None
    if any(
        records.get(image_type) is None
        or records[image_type].upload_status != "uploaded"
        for image_type in ("raw", "enhanced", "report")
    ):
        return None
    try:
        return rebuild_landmark_index(db, report_record, indexed_by=indexed_by)
    except Exception as exc:
        indexed_at = datetime.now(UTC)
        raw_record = records.get("raw")
        enhanced_record = records.get("enhanced")
        _set_report_summary(
            db,
            report_record,
            index_status="failed",
            warning=f"Landmark 反查失败：{exc}",
            counts={"resolved": 0, "approx_matched": 0, "unresolved": 0, "marked": 0},
            raw_record=raw_record,
            enhanced_record=enhanced_record,
            indexed_at=indexed_at,
        )
        return LandmarkBuildResult(
            report_record_id=report_record.id,
            raw_record_id=raw_record.id if raw_record else None,
            enhanced_record_id=enhanced_record.id if enhanced_record else None,
            index_status="failed",
            warning=f"Landmark 反查失败：{exc}",
            evidence=[],
        )


def landmark_index_state(
    db: Session,
    report_record: SubjectImageRecord,
) -> LandmarkBuildResult:
    records = _record_map(db, report_record.subject_id)
    raw_record = records.get("raw")
    enhanced_record = records.get("enhanced")
    if (
        report_record.upload_status != "uploaded"
        or raw_record is None
        or enhanced_record is None
        or raw_record.upload_status != "uploaded"
        or enhanced_record.upload_status != "uploaded"
    ):
        return LandmarkBuildResult(
            report_record_id=report_record.id,
            raw_record_id=raw_record.id if raw_record else None,
            enhanced_record_id=enhanced_record.id if enhanced_record else None,
            index_status="waiting_for_assets",
            warning="原始图像、增强图像和 PDF 电子报告齐全后才能反查 Landmark",
            evidence=[],
        )
    evidence = list(
        db.scalars(
            select(ImageEvidenceIndex)
            .where(
                ImageEvidenceIndex.subject_id == report_record.subject_id,
                ImageEvidenceIndex.evidence_type.in_(LANDMARK_TYPES),
            )
            .order_by(ImageEvidenceIndex.evidence_type, ImageEvidenceIndex.id)
        )
    )
    package_status, package_warning = _summary_from_report_package(
        _report_package(db, report_record.id)
    )
    counts = landmark_counts(evidence)
    status = (
        package_status
        if package_status in {"failed", "not_supported"}
        else _index_status(counts)
    )
    return LandmarkBuildResult(
        report_record_id=report_record.id,
        raw_record_id=raw_record.id,
        enhanced_record_id=enhanced_record.id,
        index_status=status,
        warning=package_warning,
        evidence=evidence,
    )


def landmark_counts(evidence: list[ImageEvidenceIndex]) -> dict[str, int]:
    counts = {"resolved": 0, "approx_matched": 0, "unresolved": 0, "marked": 0}
    for row in evidence:
        if row.evidence_type == IMAGE_EVIDENCE_MARKED_IMAGE:
            counts["marked"] += 1
        elif row.match_status in counts:
            counts[row.match_status] += 1
    return counts


def confirm_landmark_candidate(
    evidence: ImageEvidenceIndex,
    candidate_key: str,
    *,
    confirmed_by: int | None,
) -> None:
    if evidence.evidence_type != IMAGE_EVIDENCE_LANDMARK_IMAGE:
        raise ValueError("evidence is not a landmark")
    payload = dict(evidence.payload_json or {})
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise KeyError(candidate_key)
    candidate = next(
        (
            item
            for item in candidates
            if isinstance(item, dict) and item.get("candidate_key") == candidate_key
        ),
        None,
    )
    if candidate is None:
        raise KeyError(candidate_key)
    raw_path = ensure_relative_path(settings.file_storage_root, candidate["raw_relative_path"])
    file_hash, file_size = _file_digest(raw_path)
    now = datetime.now(UTC)
    payload["selected_candidate_key"] = candidate_key
    payload["selected_candidate"] = candidate
    payload["manually_confirmed"] = True
    payload["confirmed_by"] = confirmed_by
    payload["confirmed_at"] = now.isoformat()
    evidence.relative_path = candidate["raw_relative_path"]
    evidence.file_hash = file_hash
    evidence.file_size = file_size
    evidence.match_status = IMAGE_EVIDENCE_MATCH_RESOLVED
    evidence.payload_json = payload
    evidence.indexed_by = confirmed_by
    evidence.indexed_at = now
