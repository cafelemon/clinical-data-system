from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import REVIEW_APPROVED, REVIEW_PENDING, REVIEW_UNREVIEWED, UPLOADED_STATUSES
from app.core.config import settings
from app.core.files import ensure_relative_path
from app.models import (
    DocumentExtractedField,
    FileAsset,
    FileVersion,
    PdfPacket,
    PdfPacketSegment,
    ReviewRecord,
    Subject,
    SubjectItem,
)
from app.services.clinical_status import recalculate_subject_status
from app.services.page_text_normalizer import normalize_page_text
from app.services.pdf_packets import extract_page_texts, pdf_page_count

FIELD_STATUS_EXTRACTED = "extracted"
FIELD_STATUS_NEEDS_INPUT = "needs_input"
FIELD_STATUS_CONFIRMED = "confirmed"
FIELD_STATUSES = {FIELD_STATUS_EXTRACTED, FIELD_STATUS_NEEDS_INPUT, FIELD_STATUS_CONFIRMED}

DOCUMENT_CONSENT = "informed_consent"
DOCUMENT_CONSENT_HANDOVER = "informed_consent_handover"
DOCUMENT_CT_REPORT = "ct_report"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    value_type: str
    required: bool = True


@dataclass(frozen=True)
class ExtractedValue:
    raw_value: str | None
    normalized_value: str | None
    source_page_no: int | None
    source_text: str | None
    confidence: float


FIELD_SPECS: dict[str, tuple[FieldSpec, ...]] = {
    DOCUMENT_CONSENT: (
        FieldSpec("icf_version_date", "版本及日期", "text"),
        FieldSpec("subject_signed_at", "受试者签署时间", "datetime"),
        FieldSpec("investigator_signed_at", "研究者签署时间", "datetime"),
    ),
    DOCUMENT_CONSENT_HANDOVER: (
        FieldSpec("icf_signed_date", "知情同意书签署时间", "date"),
        FieldSpec("subject_received_date", "受试者领用知情同意书时间", "date"),
    ),
    DOCUMENT_CT_REPORT: (
        FieldSpec("registration_no", "登记号", "text"),
        FieldSpec("exam_name", "检查名称", "text"),
        FieldSpec("exam_at", "检查时间", "datetime"),
        FieldSpec("impression", "印象内容", "long_text"),
    ),
}

DOCUMENT_LABELS = {
    DOCUMENT_CONSENT: "知情同意书",
    DOCUMENT_CONSENT_HANDOVER: "知情同意书交接表",
    DOCUMENT_CT_REPORT: "CT检查报告",
}

DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s*[年/\-.]\s*(?P<month>\d{1,2})\s*[月/\-.]\s*"
    r"(?P<day>\d{1,2})\s*(?:日)?"
    r"(?:\s*(?P<hour>\d{1,2})\s*(?:[:：时点])\s*(?P<minute>\d{1,2})\s*(?:分)?)?"
)

LABEL_SEPARATOR_PATTERN = re.compile(r"^[\s:：,，.。;；\-—_]+")
DATE_TAIL_PATTERN = re.compile(r"(?:日期|时间|签署|签名)\s*[:：,，.。;；\-—_]*\s*(?P<tail>.+)")


def now_utc() -> datetime:
    return datetime.now(UTC)


def compact_source(value: str | None, max_length: int = 500) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text[:max_length] or None


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s_：:，,。.;；、（）()【】\[\]《》<>/\\|·~\-—]+", "", value).lower()


def expanded_lines_for_matching(text: str | None) -> list[str]:
    normalized = normalize_page_text(text or "")
    source_lines: list[str] = []
    raw_lines = [line.strip() for line in re.split(r"\r\n|\r|\n", text or "") if line.strip()]
    for line in [*raw_lines, *normalized.lines]:
        if line and line not in source_lines:
            source_lines.append(line)

    expanded = list(source_lines)
    for index in range(len(source_lines) - 1):
        expanded.append(f"{source_lines[index]} {source_lines[index + 1]}")
    for index in range(len(source_lines) - 2):
        expanded.append(
            f"{source_lines[index]} {source_lines[index + 1]} {source_lines[index + 2]}"
        )
    return expanded


def expand_text_pages(page_texts: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [
        (page_no, "\n".join(expanded_lines_for_matching(text)))
        for page_no, text in page_texts
    ]


def keyword_matches(line: str, keyword: str) -> bool:
    return keyword in line or normalize_name(keyword) in normalize_name(line)


def all_keywords_match(line: str, keywords: tuple[str, ...]) -> bool:
    return all(keyword_matches(line, keyword) for keyword in keywords)


def any_keyword_matches(line: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword_matches(line, keyword) for keyword in keywords)


def document_type_for_values(*values: str | None) -> str | None:
    combined = normalize_name(" ".join(value for value in values if value))
    if not combined:
        return None
    if "交接" in combined:
        return DOCUMENT_CONSENT_HANDOVER
    if "ct" in combined or "检查报告" in combined or "医学影像" in combined or "影像报告" in combined:
        return DOCUMENT_CT_REPORT
    if "知情同意" in combined or "informedconsent" in combined:
        return DOCUMENT_CONSENT
    return None


def document_type_for_subject_item(subject_item: SubjectItem | None) -> str | None:
    if subject_item is None:
        return None
    return document_type_for_values(subject_item.item_code, subject_item.item_name)


def parse_date(value: str | None, *, require_time: bool) -> str | None:
    if not value:
        return None
    match = DATE_PATTERN.search(value)
    if match is None:
        return None
    hour = match.group("hour")
    minute = match.group("minute")
    if require_time and (hour is None or minute is None):
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        if hour is not None and minute is not None:
            parsed = datetime(year, month, day, int(hour), int(minute))
            return parsed.strftime("%Y-%m-%d %H:%M")
        parsed = datetime(year, month, day)
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_noisy_labeled_date(value: str | None, *, require_time: bool) -> str | None:
    if not value:
        return None
    normalized_line = normalize_page_text(value).normalized_text or value
    tail_match = DATE_TAIL_PATTERN.search(normalized_line)
    candidate = tail_match.group("tail") if tail_match is not None else normalized_line
    numbers = [int(number) for number in re.findall(r"\d+", candidate)]
    if len(numbers) < 3:
        return None
    year_index = next((index for index, number in enumerate(numbers) if 2000 <= number <= 2099), None)
    if year_index is None or len(numbers) <= year_index + 2:
        return None
    year, month, day = numbers[year_index : year_index + 3]
    hour = numbers[year_index + 3] if len(numbers) > year_index + 3 else None
    minute = numbers[year_index + 4] if len(numbers) > year_index + 4 else None
    if require_time and (hour is None or minute is None):
        return None
    try:
        if hour is not None and minute is not None:
            parsed = datetime(year, month, day, hour, minute)
            return parsed.strftime("%Y-%m-%d %H:%M")
        parsed = datetime(year, month, day)
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return None


def first_date_raw(value: str | None) -> str | None:
    match = DATE_PATTERN.search(value or "")
    return match.group(0).strip() if match is not None else None


def tail_after_first_keyword(value: str, keywords: tuple[str, ...]) -> str:
    positions = [value.find(keyword) for keyword in keywords if keyword and value.find(keyword) >= 0]
    if not positions:
        return value
    return value[min(positions) :]


def text_pages_from_text(text: str | None, page_start: int | None = None) -> list[tuple[int, str]]:
    if not text:
        return []
    return [(page_start or 1, text)]


def text_pages_for_file_version(file_version: FileVersion) -> list[tuple[int, str]]:
    path = ensure_relative_path(settings.file_storage_root, file_version.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    page_count = pdf_page_count(path)
    return [(index + 1, text) for index, text in enumerate(extract_page_texts(path, page_count))]


def find_line(page_texts: list[tuple[int, str]], *keywords: str, exclude: tuple[str, ...] = ()) -> tuple[int, str] | None:
    for page_no, text in page_texts:
        for line in text.splitlines():
            if all(keyword in line for keyword in keywords) and not any(
                keyword in line for keyword in exclude
            ):
                return page_no, line
    return None


def find_labeled_value(page_texts: list[tuple[int, str]], labels: tuple[str, ...]) -> ExtractedValue:
    for page_no, text in page_texts:
        for line in text.splitlines():
            for label in labels:
                if not keyword_matches(line, label):
                    continue
                value = ""
                pattern = re.compile(rf"{re.escape(label)}\s*[:：]?\s*(?P<value>.*)")
                match = pattern.search(line)
                if match is not None:
                    value = match.group("value").strip()
                elif label in line:
                    value = line.split(label, 1)[1].strip()
                else:
                    compact_line = normalize_name(line)
                    compact_label = normalize_name(label)
                    index = compact_line.find(compact_label)
                    if index >= 0:
                        value = line[index + len(label) :].strip()
                value = LABEL_SEPARATOR_PATTERN.sub("", value).strip()
                if not value:
                    continue
                return ExtractedValue(value, value, page_no, compact_source(line), 0.75)
    return ExtractedValue(None, None, None, None, 0)


def find_date_field(
    page_texts: list[tuple[int, str]],
    *,
    include: tuple[str, ...],
    exclude: tuple[str, ...] = (),
    require_time: bool,
) -> ExtractedValue:
    for page_no, text in page_texts:
        for line in text.splitlines():
            if not all_keywords_match(line, include):
                continue
            if any_keyword_matches(line, exclude):
                continue
            search_line = tail_after_first_keyword(line, include)
            raw = first_date_raw(search_line)
            normalized = parse_date(raw or search_line, require_time=require_time)
            if normalized is None:
                normalized = parse_noisy_labeled_date(search_line, require_time=require_time)
            if raw or normalized:
                return ExtractedValue(raw or line.strip(), normalized, page_no, compact_source(line), 0.78)
    return ExtractedValue(None, None, None, None, 0)


def find_impression(page_texts: list[tuple[int, str]]) -> ExtractedValue:
    labels = ("印象", "诊断意见", "检查结论")
    for page_no, text in page_texts:
        normalized = normalize_page_text(text.replace("\r", "\n")).normalized_text or text.replace("\r", "\n")
        for label in labels:
            index = normalized.find(label)
            if index < 0:
                continue
            tail = normalized[index + len(label) :]
            tail = re.sub(r"^[：:\s]+", "", tail)
            stop = re.search(r"\n\s*(报告医师|审核医师|检查医师|报告日期|打印时间)[:：\s]", tail)
            value = tail[: stop.start()] if stop else tail
            value = value.strip()[:800]
            return ExtractedValue(value or None, value or None, page_no, compact_source(value), 0.76 if value else 0)
    return ExtractedValue(None, None, None, None, 0)


def extract_values(document_type: str, page_texts: list[tuple[int, str]]) -> dict[str, ExtractedValue]:
    page_texts = expand_text_pages(page_texts)
    if document_type == DOCUMENT_CONSENT:
        version = find_labeled_value(page_texts, ("版本及日期", "版本日期", "版本号", "版本"))
        return {
            "icf_version_date": version,
            "subject_signed_at": find_date_field(
                page_texts,
                include=("受试者",),
                exclude=("研究者", "医生"),
                require_time=True,
            ),
            "investigator_signed_at": find_date_field(
                page_texts,
                include=("研究者",),
                require_time=True,
            ),
        }
    if document_type == DOCUMENT_CONSENT_HANDOVER:
        return {
            "icf_signed_date": find_date_field(
                page_texts,
                include=("知情同意书", "签署"),
                require_time=False,
            ),
            "subject_received_date": find_date_field(
                page_texts,
                include=("领用",),
                require_time=False,
            ),
        }
    if document_type == DOCUMENT_CT_REPORT:
        registration = find_labeled_value(page_texts, ("登记号", "影像号", "检查号"))
        exam_name = find_labeled_value(page_texts, ("检查名称", "检查项目", "检查部位"))
        return {
            "registration_no": registration,
            "exam_name": exam_name,
            "exam_at": find_date_field(
                page_texts,
                include=("检查",),
                require_time=True,
            ),
            "impression": find_impression(page_texts),
        }
    return {}


def field_status_for(spec: FieldSpec, value: ExtractedValue) -> str:
    if not spec.required:
        return FIELD_STATUS_EXTRACTED
    if not value.raw_value:
        return FIELD_STATUS_NEEDS_INPUT
    if spec.value_type in {"date", "datetime"} and not value.normalized_value:
        return FIELD_STATUS_NEEDS_INPUT
    return FIELD_STATUS_EXTRACTED


def clear_fields_for_source(
    db: Session,
    *,
    file_version_id: int | None = None,
    segment_id: int | None = None,
) -> None:
    statement = select(DocumentExtractedField)
    if file_version_id is not None:
        statement = statement.where(DocumentExtractedField.file_version_id == file_version_id)
    if segment_id is not None:
        statement = statement.where(DocumentExtractedField.pdf_packet_segment_id == segment_id)
    for field in db.scalars(statement):
        db.delete(field)
    db.flush()


def create_fields(
    db: Session,
    *,
    document_type: str,
    page_texts: list[tuple[int, str]],
    file_version_id: int | None = None,
    segment_id: int | None = None,
) -> list[DocumentExtractedField]:
    values = extract_values(document_type, page_texts)
    fields: list[DocumentExtractedField] = []
    for spec in FIELD_SPECS.get(document_type, ()):
        value = values.get(spec.key) or ExtractedValue(None, None, None, None, 0)
        field = DocumentExtractedField(
            file_version_id=file_version_id,
            pdf_packet_segment_id=segment_id,
            document_type=document_type,
            field_key=spec.key,
            field_label=spec.label,
            value_type=spec.value_type,
            raw_value=value.raw_value,
            normalized_value=value.normalized_value,
            source_page_no=value.source_page_no,
            source_text=value.source_text,
            confidence=value.confidence,
            status=field_status_for(spec, value),
            manually_edited=False,
        )
        db.add(field)
        fields.append(field)
    db.flush()
    return fields


def fields_for_file_version(db: Session, file_version_id: int) -> list[DocumentExtractedField]:
    return list(
        db.scalars(
            select(DocumentExtractedField)
            .where(DocumentExtractedField.file_version_id == file_version_id)
            .order_by(DocumentExtractedField.id)
        )
    )


def fields_for_segment(db: Session, segment_id: int) -> list[DocumentExtractedField]:
    return list(
        db.scalars(
            select(DocumentExtractedField)
            .where(DocumentExtractedField.pdf_packet_segment_id == segment_id)
            .order_by(DocumentExtractedField.id)
        )
    )


def analyze_file_version_fields(
    db: Session,
    file_asset: FileAsset,
    file_version: FileVersion,
    *,
    force: bool = False,
) -> list[DocumentExtractedField]:
    if file_version.mime_type != "application/pdf":
        return fields_for_file_version(db, file_version.id)
    existing = fields_for_file_version(db, file_version.id)
    if existing and not force:
        return existing
    if existing:
        clear_fields_for_source(db, file_version_id=file_version.id)
    subject_item = db.get(SubjectItem, file_asset.subject_item_id) if file_asset.subject_item_id else None
    document_type = document_type_for_subject_item(subject_item) or document_type_for_values(
        file_version.original_name,
        file_asset.original_name,
    )
    if document_type is None:
        return []
    try:
        page_texts = text_pages_for_file_version(file_version)
    except Exception:
        page_texts = []
    return create_fields(
        db,
        document_type=document_type,
        page_texts=page_texts,
        file_version_id=file_version.id,
    )


def analyze_segment_fields(
    db: Session,
    segment: PdfPacketSegment,
    *,
    force: bool = False,
) -> list[DocumentExtractedField]:
    existing = fields_for_segment(db, segment.id)
    if existing and not force:
        return existing
    if existing:
        clear_fields_for_source(db, segment_id=segment.id)
    subject_item = db.get(SubjectItem, segment.subject_item_id or segment.suggested_subject_item_id or 0)
    document_type = document_type_for_subject_item(subject_item) or document_type_for_values(
        segment.detected_code,
        segment.detected_name,
    )
    if document_type is None:
        return []
    return create_fields(
        db,
        document_type=document_type,
        page_texts=text_pages_from_text(segment.ocr_text, segment.page_start),
        segment_id=segment.id,
    )


def copy_segment_fields_to_file_version(
    db: Session,
    segment: PdfPacketSegment,
    file_version: FileVersion,
) -> list[DocumentExtractedField]:
    segment_fields = analyze_segment_fields(db, segment)
    clear_fields_for_source(db, file_version_id=file_version.id)
    copied: list[DocumentExtractedField] = []
    for source in segment_fields:
        field = DocumentExtractedField(
            file_version_id=file_version.id,
            document_type=source.document_type,
            field_key=source.field_key,
            field_label=source.field_label,
            value_type=source.value_type,
            raw_value=source.raw_value,
            normalized_value=source.normalized_value,
            source_page_no=source.source_page_no,
            source_text=source.source_text,
            confidence=source.confidence,
            status=source.status,
            manually_edited=source.manually_edited,
            confirmed_by=source.confirmed_by,
            confirmed_at=source.confirmed_at,
            updated_by=source.updated_by,
        )
        db.add(field)
        copied.append(field)
    db.flush()
    return copied


def normalize_manual_value(field: DocumentExtractedField, raw_value: str | None, normalized_value: str | None) -> tuple[str | None, str | None, str]:
    raw = raw_value.strip() if raw_value is not None else None
    normalized = normalized_value.strip() if normalized_value is not None else None
    if field.value_type == "date":
        normalized = normalized or parse_date(raw, require_time=False)
    elif field.value_type == "datetime":
        normalized = normalized or parse_date(raw, require_time=True)
    elif normalized is None:
        normalized = raw
    if not raw or (field.value_type in {"date", "datetime"} and not normalized):
        return raw or None, normalized or None, FIELD_STATUS_NEEDS_INPUT
    return raw, normalized, FIELD_STATUS_CONFIRMED


def update_field(
    db: Session,
    field: DocumentExtractedField,
    *,
    raw_value: str | None = None,
    normalized_value: str | None = None,
    status_value: str | None = None,
    user_id: int | None = None,
) -> DocumentExtractedField:
    next_raw, next_normalized, computed_status = normalize_manual_value(
        field,
        field.raw_value if raw_value is None else raw_value,
        field.normalized_value if normalized_value is None else normalized_value,
    )
    field.raw_value = next_raw
    field.normalized_value = next_normalized
    if status_value is not None:
        if status_value not in FIELD_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid field status")
        field.status = status_value
    else:
        field.status = computed_status
    field.manually_edited = True
    field.updated_by = user_id
    if field.status == FIELD_STATUS_CONFIRMED:
        field.confirmed_by = user_id
        field.confirmed_at = now_utc()
    db.flush()
    return field


def latest_file_version(db: Session, file_asset: FileAsset, version: int | None = None) -> FileVersion:
    target_version = version or file_asset.version
    file_version = db.scalar(
        select(FileVersion).where(
            FileVersion.file_id == file_asset.id,
            FileVersion.version == target_version,
        )
    )
    if file_version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file version not found")
    return file_version


def fielded_document_has_needs_input(fields: list[DocumentExtractedField]) -> bool:
    return any(field.status == FIELD_STATUS_NEEDS_INPUT for field in fields)


def sync_subject_item_after_fields(
    db: Session,
    file_asset: FileAsset,
    *,
    user_id: int | None = None,
    file_version: FileVersion | None = None,
) -> None:
    if file_asset.subject_item_id is None:
        return
    subject_item = db.get(SubjectItem, file_asset.subject_item_id)
    if subject_item is None or subject_item.upload_status not in UPLOADED_STATUSES:
        return
    target_version = file_version or latest_file_version(db, file_asset)
    fields = fields_for_file_version(db, target_version.id)
    if not fields:
        return
    if fielded_document_has_needs_input(fields):
        if subject_item.review_status != REVIEW_APPROVED:
            subject_item.review_status = REVIEW_UNREVIEWED
        subject = db.get(Subject, subject_item.subject_id)
        if subject is not None:
            recalculate_subject_status(db, subject)
        return
    if subject_item.review_status != REVIEW_APPROVED:
        subject_item.review_status = REVIEW_PENDING
        db.add(
            ReviewRecord(
                target_type="subject_item",
                target_id=subject_item.id,
                action="submit",
                review_status=REVIEW_PENDING,
                reviewer_id=user_id,
                comment="字段核查完成，系统自动提交待审核",
            )
        )
    subject = db.get(Subject, subject_item.subject_id)
    if subject is not None:
        recalculate_subject_status(db, subject)
