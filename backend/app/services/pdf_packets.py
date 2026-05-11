import hashlib
import mimetypes
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import CATEGORY_FOLDERS, StoredUpload, ensure_relative_path, safe_path_part
from app.models import Center, PdfPacket, PdfPacketSegment, Project, StageTemplate, Subject
from app.models.clinical_data import SubjectItem
from app.services.ocr_client import OcrClientError, PaddleOcrClient


class PdfPacketError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubjectItemCandidate:
    id: int
    item_name: str
    item_code: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class PageMatch:
    subject_item_id: int | None
    detected_name: str | None
    detected_code: str | None
    confidence: float


def packet_relative_directory(project: Project, center: Center, subject: Subject) -> Path:
    return (
        Path("projects")
        / safe_path_part(project.code)
        / "centers"
        / safe_path_part(center.code)
        / "subjects"
        / safe_path_part(subject.screening_no)
        / "pdf_packets"
        / f"v{uuid4().hex[:8]}"
    )


def derived_relative_directory(
    project: Project,
    center: Center,
    subject: Subject,
    subject_item: SubjectItem,
    version: int = 1,
) -> Path:
    return (
        Path("projects")
        / safe_path_part(project.code)
        / "centers"
        / safe_path_part(center.code)
        / "subjects"
        / safe_path_part(subject.screening_no)
        / CATEGORY_FOLDERS["clinical_document"]
        / safe_path_part(subject_item.item_code)
        / f"v{version}"
    )


def write_upload_file(upload_file: UploadFile, target_dir: Path) -> StoredUpload:
    original_name = Path(upload_file.filename or "upload.pdf").name
    suffix = Path(original_name).suffix.lower()
    file_ext = suffix.lstrip(".") or None
    stored_name = f"{uuid4().hex}{suffix or '.pdf'}"
    relative_path = target_dir / stored_name
    destination = ensure_relative_path(settings.file_storage_root, relative_path.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)

    max_size = settings.max_upload_size_mb * 1024 * 1024
    hasher = hashlib.sha256()
    size = 0
    try:
        upload_file.file.seek(0)
        with destination.open("wb") as output:
            while chunk := upload_file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="file too large")
                hasher.update(chunk)
                output.write(chunk)
    finally:
        upload_file.file.close()

    mime_type = (
        upload_file.content_type
        or mimetypes.guess_type(original_name)[0]
        or "application/octet-stream"
    )
    return StoredUpload(
        original_name=original_name,
        stored_name=stored_name,
        file_ext=file_ext,
        mime_type=mime_type,
        file_size=size,
        file_hash=hasher.hexdigest(),
        storage_path=relative_path.as_posix(),
    )


def hash_file(path: Path) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as input_file:
        while chunk := input_file.read(1024 * 1024):
            size += len(chunk)
            hasher.update(chunk)
    return size, hasher.hexdigest()


def pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        pass

    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        raise PdfPacketError("PDF page counting requires pypdf or pdfinfo")
    result = subprocess.run(
        [pdfinfo, str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise PdfPacketError(result.stderr.strip() or "failed to read PDF metadata")
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if match is None:
        raise PdfPacketError("failed to read PDF page count")
    return int(match.group(1))


def extract_pdf_pages(source_path: Path, target_path: Path, page_start: int, page_end: int) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(source_path))
        writer = PdfWriter()
        for page_number in range(page_start, page_end + 1):
            writer.add_page(reader.pages[page_number - 1])
        with target_path.open("wb") as output:
            writer.write(output)
        return
    except Exception:
        pass

    pdfseparate = shutil.which("pdfseparate")
    pdfunite = shutil.which("pdfunite")
    if pdfseparate is None or pdfunite is None:
        raise PdfPacketError("PDF splitting requires pypdf or Poppler pdfseparate/pdfunite")
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        pattern = tmp_dir / "page-%d.pdf"
        separate = subprocess.run(
            [
                pdfseparate,
                "-f",
                str(page_start),
                "-l",
                str(page_end),
                str(source_path),
                str(pattern),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if separate.returncode != 0:
            raise PdfPacketError(separate.stderr.strip() or "failed to split PDF pages")
        page_paths = [tmp_dir / f"page-{page}.pdf" for page in range(page_start, page_end + 1)]
        unite = subprocess.run(
            [pdfunite, *[str(path) for path in page_paths], str(target_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if unite.returncode != 0:
            raise PdfPacketError(unite.stderr.strip() or "failed to assemble PDF pages")


def extract_text_with_pypdf(path: Path, page_count: int) -> list[str] | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(reader.pages[index].extract_text() or "") for index in range(page_count)]
    except Exception:
        return None


def extract_text_with_pdftotext(path: Path, page_count: int) -> list[str] | None:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        return None
    texts: list[str] = []
    for page_number in range(1, page_count + 1):
        result = subprocess.run(
            [
                pdftotext,
                "-layout",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                str(path),
                "-",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        texts.append(result.stdout if result.returncode == 0 else "")
    return texts


def extract_text_with_ocr_command(path: Path, page_count: int) -> list[str] | None:
    if not settings.pdf_packet_ocr_command:
        return None
    texts: list[str] = []
    for page_number in range(1, page_count + 1):
        command = settings.pdf_packet_ocr_command.format(
            pdf_path=str(path),
            page=page_number,
        )
        result = subprocess.run(
            shlex.split(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        texts.append(result.stdout if result.returncode == 0 else "")
    return texts


def extract_text_with_ocr_api(path: Path, page_count: int) -> list[str] | None:
    if not settings.pdf_packet_ocr_api_url:
        return None
    try:
        client = PaddleOcrClient(
            settings.pdf_packet_ocr_api_url,
            timeout_seconds=settings.pdf_packet_ocr_timeout_seconds,
        )
        return client.ocr_pdf(path, page_count=page_count, dpi=settings.pdf_packet_ocr_dpi)
    except OcrClientError as exc:
        raise PdfPacketError(f"OCR API failed: {exc}") from exc


def extract_page_texts(path: Path, page_count: int) -> list[str]:
    texts = extract_text_with_pypdf(path, page_count)
    if texts is None or not any(text.strip() for text in texts):
        texts = extract_text_with_pdftotext(path, page_count)
    if texts is None or not any(text.strip() for text in texts):
        ocr_api_texts = extract_text_with_ocr_api(path, page_count)
        if ocr_api_texts is not None:
            texts = ocr_api_texts
    if texts is None or not any(text.strip() for text in texts):
        ocr_texts = extract_text_with_ocr_command(path, page_count)
        if ocr_texts is not None:
            texts = ocr_texts
    if texts is None:
        texts = ["" for _ in range(page_count)]
    return texts[:page_count] + ["" for _ in range(max(0, page_count - len(texts)))]


def split_keywords(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(keyword.strip() for keyword in re.split(r"[,，;\n\r]+", value) if keyword.strip())


def subject_item_candidates(db: Session, subject_id: int) -> list[SubjectItemCandidate]:
    items = list(
        db.scalars(
            select(SubjectItem)
            .where(SubjectItem.subject_id == subject_id)
            .order_by(SubjectItem.id)
        )
    )
    template_ids = [item.stage_template_id for item in items if item.stage_template_id is not None]
    templates = {
        template.id: template
        for template in db.scalars(select(StageTemplate).where(StageTemplate.id.in_(template_ids)))
    }
    candidates: list[SubjectItemCandidate] = []
    for item in items:
        template = templates.get(item.stage_template_id or 0)
        keywords = split_keywords(template.recognition_keywords if template is not None else None)
        candidates.append(
            SubjectItemCandidate(
                id=item.id,
                item_name=item.item_name,
                item_code=item.item_code,
                keywords=keywords,
            )
        )
    return candidates


def normalize_for_match(value: str) -> str:
    return re.sub(r"[\s_：:，,。.;；（）()【】\[\]-]+", "", value).lower()


def best_page_match(text: str, candidates: list[SubjectItemCandidate]) -> PageMatch:
    normalized_text = normalize_for_match(text)
    if not normalized_text:
        return PageMatch(None, None, None, 0)
    best = PageMatch(None, None, None, 0)
    for candidate in candidates:
        checks = [
            (candidate.item_name, 0.95),
            (candidate.item_code, 0.9),
            *[(keyword, 0.85) for keyword in candidate.keywords],
        ]
        for keyword, confidence in checks:
            normalized_keyword = normalize_for_match(keyword)
            if normalized_keyword and normalized_keyword in normalized_text:
                if confidence > best.confidence:
                    best = PageMatch(
                        candidate.id,
                        candidate.item_name,
                        candidate.item_code,
                        confidence,
                    )
    return best


def compact_text(texts: list[str], max_length: int = 4000) -> str:
    value = "\n".join(text.strip() for text in texts if text.strip())
    return value[:max_length]


def build_detected_segments(
    page_texts: list[str],
    candidates: list[SubjectItemCandidate],
) -> list[dict[str, object]]:
    page_count = len(page_texts)
    if page_count == 0:
        return []
    raw_matches = [best_page_match(text, candidates) for text in page_texts]
    if not any(match.subject_item_id is not None for match in raw_matches):
        return [
            {
                "page_start": 1,
                "page_end": page_count,
                "detected_name": None,
                "detected_code": None,
                "confidence": 0,
                "suggested_subject_item_id": None,
                "ocr_text": compact_text(page_texts),
            }
        ]

    segments: list[dict[str, object]] = []
    start = 1
    current = raw_matches[0]
    for index, match in enumerate(raw_matches[1:], start=2):
        should_start_new = (
            match.subject_item_id is not None
            and match.subject_item_id != current.subject_item_id
        )
        if should_start_new:
            segments.append(
                {
                    "page_start": start,
                    "page_end": index - 1,
                    "detected_name": current.detected_name,
                    "detected_code": current.detected_code,
                    "confidence": current.confidence,
                    "suggested_subject_item_id": current.subject_item_id,
                    "ocr_text": compact_text(page_texts[start - 1 : index - 1]),
                }
            )
            start = index
            current = match
        elif current.subject_item_id is None and match.subject_item_id is not None:
            if index > start:
                segments.append(
                    {
                        "page_start": start,
                        "page_end": index - 1,
                        "detected_name": None,
                        "detected_code": None,
                        "confidence": 0,
                        "suggested_subject_item_id": None,
                        "ocr_text": compact_text(page_texts[start - 1 : index - 1]),
                    }
                )
            start = index
            current = match
    segments.append(
        {
            "page_start": start,
            "page_end": page_count,
            "detected_name": current.detected_name,
            "detected_code": current.detected_code,
            "confidence": current.confidence,
            "suggested_subject_item_id": current.subject_item_id,
            "ocr_text": compact_text(page_texts[start - 1 : page_count]),
        }
    )
    return segments


def analyze_packet(db: Session, packet: PdfPacket) -> PdfPacket:
    uploaded_segment = db.scalar(
        select(PdfPacketSegment.id)
        .where(
            PdfPacketSegment.packet_id == packet.id,
            PdfPacketSegment.file_asset_id.is_not(None),
        )
        .limit(1)
    )
    if uploaded_segment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="packet has uploaded segments and cannot be re-analyzed",
        )

    source_path = ensure_relative_path(settings.file_storage_root, packet.storage_path)
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="packet file not found")

    packet.status = "processing"
    packet.error_message = None
    for segment in list(
        db.scalars(select(PdfPacketSegment).where(PdfPacketSegment.packet_id == packet.id))
    ):
        db.delete(segment)
    db.flush()

    try:
        packet.page_count = packet.page_count or pdf_page_count(source_path)
        page_texts = extract_page_texts(source_path, packet.page_count)
        candidates = subject_item_candidates(db, packet.subject_id)
        segment_payloads = build_detected_segments(page_texts, candidates)
        for payload in segment_payloads:
            db.add(PdfPacketSegment(packet_id=packet.id, status="pending", **payload))
        text_pages = sum(1 for text in page_texts if text.strip())
        packet.status = "ready"
        packet.analysis_summary = f"{len(segment_payloads)} segments, {text_pages} text/OCR pages"
    except Exception as exc:
        packet.status = "failed"
        packet.error_message = str(exc)
    return packet


def remove_packet_physical_file(packet: PdfPacket) -> None:
    try:
        path = ensure_relative_path(settings.file_storage_root, packet.storage_path)
    except ValueError:
        return
    if not path.exists():
        return
    path.unlink()
    for parent in path.parents:
        if parent == settings.file_storage_root.resolve():
            break
        try:
            parent.rmdir()
        except OSError:
            break
