from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_UNREVIEWED,
    UPLOADED_STATUSES,
)
from app.core.config import settings
from app.core.files import ensure_relative_path
from app.models import (
    ClinicalSsuProgress,
    DocumentExtractedField,
    FileAsset,
    FileVersion,
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
LOW_CONFIDENCE_THRESHOLD = 0.7
FALLBACK_DATE_CONFIDENCE = 0.45

DOCUMENT_CONSENT = "informed_consent"
DOCUMENT_CONSENT_HANDOVER = "informed_consent_handover"
DOCUMENT_CT_REPORT = "ct_report"
DOCUMENT_SSU_PROJECT_APPROVAL = "ssu_project_approval"
DOCUMENT_SSU_ETHICS = "ssu_ethics"
DOCUMENT_SSU_AGREEMENT_SIGNING = "ssu_agreement_signing"
DOCUMENT_SSU_PROVINCIAL_FILING = "ssu_provincial_filing"
DOCUMENT_SSU_STARTUP_MEETING = "ssu_startup_meeting"


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
    DOCUMENT_SSU_PROJECT_APPROVAL: (
        FieldSpec("submitted_at", "递交日期", "date"),
        FieldSpec("file_checklist", "文件清单", "long_text"),
        FieldSpec("approved_at", "同意日期", "date"),
    ),
    DOCUMENT_SSU_ETHICS: (
        FieldSpec("submitted_at", "递交日期", "date"),
        FieldSpec("file_checklist", "文件清单", "long_text"),
        FieldSpec("summary", "批件主旨内容", "long_text"),
        FieldSpec("approved_at", "同意日期", "date"),
    ),
    DOCUMENT_SSU_AGREEMENT_SIGNING: (
        FieldSpec("version_info", "版本信息", "text"),
        FieldSpec("completed_at", "签署日期", "date"),
        FieldSpec("fee_detail", "费用明细", "long_text"),
    ),
    DOCUMENT_SSU_PROVINCIAL_FILING: (
        FieldSpec("completed_at", "备案日期", "date"),
    ),
    DOCUMENT_SSU_STARTUP_MEETING: (
        FieldSpec("completed_at", "启动会日期", "date"),
    ),
}

DOCUMENT_LABELS = {
    DOCUMENT_CONSENT: "知情同意书",
    DOCUMENT_CONSENT_HANDOVER: "知情同意书交接表",
    DOCUMENT_CT_REPORT: "CT检查报告",
    DOCUMENT_SSU_PROJECT_APPROVAL: "SSU立项",
    DOCUMENT_SSU_ETHICS: "SSU伦理",
    DOCUMENT_SSU_AGREEMENT_SIGNING: "SSU协议签署",
    DOCUMENT_SSU_PROVINCIAL_FILING: "SSU省局备案",
    DOCUMENT_SSU_STARTUP_MEETING: "SSU启动会",
}

SSU_STAGE_DOCUMENT_TYPES = {
    "SSU_PROJECT_APPROVAL": DOCUMENT_SSU_PROJECT_APPROVAL,
    "SSU_ETHICS": DOCUMENT_SSU_ETHICS,
    "SSU_AGREEMENT_SIGNING": DOCUMENT_SSU_AGREEMENT_SIGNING,
    "SSU_PROVINCIAL_FILING": DOCUMENT_SSU_PROVINCIAL_FILING,
    "SSU_STARTUP_MEETING": DOCUMENT_SSU_STARTUP_MEETING,
}

DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s*[年/\-.]\s*(?P<month>\d{1,2})\s*[月/\-.]\s*"
    r"(?P<day>\d{1,2})\s*(?:日)?"
    r"(?:\s*(?P<hour>\d{1,2})\s*(?:[:：时点.])\s*(?P<minute>\d{1,2})\s*(?:分)?)?"
)

LABEL_SEPARATOR_PATTERN = re.compile(r"^[\s:：,，.。;；\-—_]+")
DATE_TAIL_PATTERN = re.compile(r"(?:日期|时间|签署|签名)\s*[:：,，.。;；\-—_]*\s*(?P<tail>.+)")
SECTION_DATE_LABEL_PATTERN = re.compile(r"(日期|时间|签署|签名|年\s*月\s*日)")
ID_LIKE_LABEL_PATTERN = re.compile(
    r"(备案号|编号|受理号|登记号|检查号|影像号|流水号|申请单号|报告单号|文件号|项目编号)"
)

FIELD_TEXT_REPLACEMENTS = {
    "递父": "递交",
    "递父日期": "递交日期",
    "同怠": "同意",
    "问意": "同意",
    "批淮": "批准",
    "签暑": "签署",
    "签暑日期": "签署日期",
    "检査": "检查",
    "检 查": "检查",
    "知情同意见": "知情同意书",
    "临床试验协仪": "临床试验协议",
    "启 动 会": "启动会",
    "文 件 清 单": "文件清单",
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def compact_source(value: str | None, max_length: int = 500) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text[:max_length] or None


def normalize_field_source_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    for source, target in FIELD_TEXT_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = re.sub(r"([一-龥])[ \t\f\v]+([一-龥])", r"\1\2", text)
    text = re.sub(r"(20\d{2})\s*[年/\-.]\s*(\d{1,2})\s*[月/\-.]\s*(\d{1,2})\s*日?", r"\1年\2月\3日", text)
    text = re.sub(r"(\d{1,2})\s*[:：时点.]\s*(\d{1,2})", r"\1:\2", text)
    text = text.replace("：", ":").replace("，", ",").replace("。", ".").replace("；", ";")
    return text


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s_：:，,。.;；、（）()【】\[\]《》<>/\\|·~\-—]+", "", value).lower()


def expanded_lines_for_matching(text: str | None) -> list[str]:
    text = normalize_field_source_text(text)
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
    for index in range(len(source_lines) - 3):
        expanded.append(
            f"{source_lines[index]} {source_lines[index + 1]} "
            f"{source_lines[index + 2]} {source_lines[index + 3]}"
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


def document_type_for_ssu_progress(progress: ClinicalSsuProgress | None) -> str | None:
    if progress is None:
        return None
    return SSU_STAGE_DOCUMENT_TYPES.get(progress.stage_code)


def parse_date(value: str | None, *, require_time: bool) -> str | None:
    if not value:
        return None
    value = normalize_field_source_text(value)
    match = DATE_PATTERN.search(value)
    if match is None:
        compact_match = re.search(
            r"(?P<year>20\d{2})(?P<month>\d{2})(?P<day>\d{2})"
            r"(?:\D*(?P<hour>\d{1,2})\D+(?P<minute>\d{1,2}))?",
            value,
        )
        match = compact_match
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
    text = normalize_field_source_text(value)
    match = DATE_PATTERN.search(text or "")
    if match is not None:
        return match.group(0).strip()
    compact_match = re.search(r"20\d{6}(?:\D*\d{1,2}\D+\d{1,2})?", text or "")
    return compact_match.group(0).strip() if compact_match is not None else None


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


def truncate_at_labels(value: str, labels: tuple[str, ...]) -> str:
    normalized_value = normalize_field_source_text(value)
    stops = [
        normalized_value.find(label)
        for label in labels
        if label and normalized_value.find(label) > 0
    ]
    if stops:
        normalized_value = normalized_value[: min(stops)]
        value = value[: min(stops)]
    return (normalized_value or value).strip()


def find_labeled_value(
    page_texts: list[tuple[int, str]],
    labels: tuple[str, ...],
    *,
    stop_labels: tuple[str, ...] = (),
) -> ExtractedValue:
    for page_no, text in page_texts:
        for line in text.splitlines():
            normalized_line = normalize_field_source_text(line)
            for label in labels:
                if not keyword_matches(normalized_line, label):
                    continue
                value = ""
                pattern = re.compile(rf"{re.escape(label)}\s*[:：]?\s*(?P<value>.*)")
                match = pattern.search(normalized_line)
                if match is not None:
                    value = match.group("value").strip()
                elif label in normalized_line:
                    value = normalized_line.split(label, 1)[1].strip()
                else:
                    compact_line = normalize_name(normalized_line)
                    compact_label = normalize_name(label)
                    index = compact_line.find(compact_label)
                    if index >= 0:
                        value = normalized_line[index + len(label) :].strip()
                value = LABEL_SEPARATOR_PATTERN.sub("", value).strip()
                value = truncate_at_labels(value, stop_labels)
                if not value:
                    continue
                return ExtractedValue(value, value, page_no, compact_source(line), 0.75)
    return ExtractedValue(None, None, None, None, 0)


def find_first_date(page_texts: list[tuple[int, str]]) -> ExtractedValue:
    for page_no, text in page_texts:
        for line in text.splitlines():
            raw = first_date_raw(line)
            normalized = parse_date(raw or line, require_time=False)
            if normalized is not None:
                return ExtractedValue(
                    raw or line.strip(),
                    normalized,
                    page_no,
                    compact_source(line),
                    0.68,
                )
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


def find_best_date_field(
    page_texts: list[tuple[int, str]],
    *,
    include_any: tuple[str, ...],
    exclude: tuple[str, ...] = (),
    require_time: bool,
    fallback: bool = False,
    exclude_id_like: bool = False,
) -> ExtractedValue:
    best = ExtractedValue(None, None, None, None, 0)
    for page_no, text in page_texts:
        for line in text.splitlines():
            normalized_line = normalize_field_source_text(line)
            if not any_keyword_matches(normalized_line, include_any):
                continue
            if any_keyword_matches(normalized_line, exclude):
                continue
            if exclude_id_like and ID_LIKE_LABEL_PATTERN.search(normalized_line):
                continue
            matching_labels = tuple(
                label for label in include_any if keyword_matches(normalized_line, label)
            )
            search_line = tail_after_first_keyword(normalized_line, matching_labels or include_any)
            raw = first_date_raw(search_line)
            normalized = parse_date(raw or search_line, require_time=require_time)
            if normalized is None:
                normalized = parse_noisy_labeled_date(search_line, require_time=require_time)
            if raw is None and normalized is None:
                continue
            confidence = 0.58 if normalized is None else 0.76
            compact_line = normalize_name(normalized_line)
            label_indexes = [
                index
                for index, label in enumerate(include_any)
                if normalize_name(label) in compact_line
            ]
            if label_indexes:
                confidence += max(0.02, 0.12 - (min(label_indexes) * 0.015))
            if SECTION_DATE_LABEL_PATTERN.search(normalized_line):
                confidence += 0.04
            candidate = ExtractedValue(
                raw or normalized_line.strip(),
                normalized,
                page_no,
                compact_source(line),
                min(confidence, 0.92),
            )
            if candidate.confidence > best.confidence:
                best = candidate
    if best.raw_value or not fallback:
        return best
    fallback_value = find_first_date(page_texts)
    if fallback_value.raw_value:
        return ExtractedValue(
            fallback_value.raw_value,
            fallback_value.normalized_value,
            fallback_value.source_page_no,
            fallback_value.source_text,
            FALLBACK_DATE_CONFIDENCE,
        )
    return fallback_value


def find_section_value(
    page_texts: list[tuple[int, str]],
    *,
    labels: tuple[str, ...],
    stop_labels: tuple[str, ...] = (),
    max_length: int = 1200,
) -> ExtractedValue:
    for page_no, text in page_texts:
        text = normalize_field_source_text(text.replace("\r", "\n"))
        normalized = normalize_page_text(text).normalized_text or text
        for label in labels:
            index = normalized.find(label)
            if index < 0:
                continue
            tail = normalized[index + len(label) :]
            tail = re.sub(r"^[：:\s,，.。;；\-—_]+", "", tail)
            tail = re.sub(r"\n\s*[-·•]?\s*", "\n", tail)
            stop_positions = [
                tail.find(stop) for stop in stop_labels if stop and tail.find(stop) >= 0
            ]
            if stop_positions:
                tail = tail[: min(stop_positions)]
            value = re.sub(r"[ \t]+", " ", tail).strip()[:max_length]
            if value:
                return ExtractedValue(value, value, page_no, compact_source(value), 0.72)
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
    source_page_texts = page_texts
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
            "icf_signed_date": find_best_date_field(
                page_texts,
                include_any=("知情同意书签署", "签署日期", "签署时间", "签署"),
                require_time=False,
            ),
            "subject_received_date": find_best_date_field(
                page_texts,
                include_any=("领用", "领取", "接收", "收到"),
                require_time=False,
            ),
        }
    if document_type == DOCUMENT_CT_REPORT:
        registration = find_labeled_value(
            page_texts,
            ("登记号", "影像号", "检查号"),
            stop_labels=("检查名称", "检查项目", "检查部位", "检查时间", "检查日期", "印象"),
        )
        exam_name = find_labeled_value(
            page_texts,
            ("检查名称", "检查项目", "检查部位"),
            stop_labels=("检查时间", "检查日期", "报告时间", "印象", "诊断意见"),
        )
        return {
            "registration_no": registration,
            "exam_name": exam_name,
            "exam_at": find_best_date_field(
                page_texts,
                include_any=("检查时间", "检查日期", "报告日期", "检查"),
                require_time=True,
            ),
            "impression": find_impression(page_texts),
        }
    if document_type == DOCUMENT_SSU_PROJECT_APPROVAL:
        return {
            "submitted_at": find_best_date_field(
                page_texts,
                include_any=("递交日期", "提交日期", "递交", "提交", "送审日期"),
                exclude=("同意", "批准", "通过", "签发"),
                require_time=False,
            ),
            "file_checklist": find_section_value(
                source_page_texts,
                labels=("文件清单", "资料清单", "递交文件", "提交文件"),
                stop_labels=("同意日期", "批准日期", "通过日期", "审批意见", "备注"),
            ),
            "approved_at": find_best_date_field(
                page_texts,
                include_any=("同意日期", "批准日期", "通过日期", "审批日期", "签发日期", "同意", "批准", "通过"),
                exclude=("递交", "提交", "送审"),
                require_time=False,
            ),
        }
    if document_type == DOCUMENT_SSU_ETHICS:
        return {
            "submitted_at": find_best_date_field(
                page_texts,
                include_any=("递交日期", "提交日期", "送审日期", "受理日期", "递交", "提交"),
                exclude=("同意", "批准", "签发", "审查意见"),
                require_time=False,
            ),
            "file_checklist": find_section_value(
                source_page_texts,
                labels=("文件清单", "资料清单", "递交文件", "提交文件"),
                stop_labels=("批件主旨", "审查意见", "同意日期", "批准日期", "备注"),
            ),
            "summary": find_section_value(
                source_page_texts,
                labels=("批件主旨内容", "批件主旨", "审查意见", "伦理审查意见", "批件内容"),
                stop_labels=("同意日期", "批准日期", "主任委员", "签发日期", "备注"),
            ),
            "approved_at": find_best_date_field(
                page_texts,
                include_any=("签发日期", "批准日期", "同意日期", "审查日期", "批件日期", "同意开展", "同意"),
                exclude=("递交", "提交", "受理"),
                require_time=False,
            ),
        }
    if document_type == DOCUMENT_SSU_AGREEMENT_SIGNING:
        return {
            "version_info": find_labeled_value(
                page_texts,
                ("版本号", "版本日期", "版本", "协议版本"),
                stop_labels=("签署日期", "签订日期", "费用明细", "研究经费"),
            ),
            "completed_at": find_best_date_field(
                page_texts,
                include_any=("签署日期", "签订日期", "合同日期", "协议日期", "签署", "签订"),
                require_time=False,
            ),
            "fee_detail": find_section_value(
                source_page_texts,
                labels=("费用明细", "费用预算", "研究经费", "付款计划"),
                stop_labels=("签署日期", "签章", "甲方", "乙方", "备注"),
            ),
        }
    if document_type == DOCUMENT_SSU_PROVINCIAL_FILING:
        completed = find_best_date_field(
            page_texts,
            include_any=("备案日期", "备案完成日期", "备案完成", "盖章日期", "省级药品监管部门盖章", "盖章", "备案"),
            exclude=("备案号", "备案编号", "受理号", "编号"),
            require_time=False,
            exclude_id_like=True,
        )
        return {"completed_at": completed}
    if document_type == DOCUMENT_SSU_STARTUP_MEETING:
        completed = find_best_date_field(
            page_texts,
            include_any=("启动会日期", "会议日期", "会议时间", "培训日期", "培训时间", "签到日期", "启动会", "会议"),
            require_time=False,
            fallback=True,
        )
        return {"completed_at": completed}
    return {}


def field_status_for(spec: FieldSpec, value: ExtractedValue) -> str:
    if not spec.required:
        return FIELD_STATUS_EXTRACTED
    if not value.raw_value:
        return FIELD_STATUS_NEEDS_INPUT
    if value.confidence and value.confidence < LOW_CONFIDENCE_THRESHOLD:
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
    subject_item = (
        db.get(SubjectItem, file_asset.subject_item_id)
        if file_asset.subject_item_id
        else None
    )
    ssu_progress = (
        db.get(ClinicalSsuProgress, file_asset.ssu_progress_id)
        if file_asset.ssu_progress_id
        else None
    )
    document_type = (
        document_type_for_subject_item(subject_item)
        or document_type_for_ssu_progress(ssu_progress)
        or document_type_for_values(
            file_version.original_name,
            file_asset.original_name,
        )
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


def best_fields_by_key(fields: list[DocumentExtractedField]) -> dict[str, DocumentExtractedField]:
    values: dict[str, DocumentExtractedField] = {}
    for field in fields:
        if field.status == FIELD_STATUS_NEEDS_INPUT:
            continue
        if not field.raw_value and not field.normalized_value:
            continue
        current = values.get(field.field_key)
        if current is None or field.confidence > current.confidence:
            values[field.field_key] = field
    return values


def required_field_keys_for_progress(progress: ClinicalSsuProgress) -> set[str]:
    document_type = document_type_for_ssu_progress(progress)
    return {
        spec.key
        for spec in FIELD_SPECS.get(document_type or "", ())
        if spec.required
    }


def date_value_for_field(field: DocumentExtractedField) -> date | None:
    value = field.normalized_value or field.raw_value
    if not value:
        return None
    normalized = parse_date(value, require_time=False) or value[:10]
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def field_text_value(field: DocumentExtractedField) -> str | None:
    value = field.normalized_value or field.raw_value
    if value is None:
        return None
    value = value.strip()
    return value or None


def sync_ssu_progress_after_fields(
    db: Session,
    file_asset: FileAsset,
    *,
    file_version: FileVersion | None = None,
    fields: list[DocumentExtractedField] | None = None,
) -> ClinicalSsuProgress | None:
    if file_asset.ssu_progress_id is None:
        return None
    progress = db.get(ClinicalSsuProgress, file_asset.ssu_progress_id)
    if progress is None:
        return None
    target_version = file_version or latest_file_version(db, file_asset)
    fields = fields if fields is not None else fields_for_file_version(db, target_version.id)
    if not fields:
        return progress
    required_keys = required_field_keys_for_progress(progress)
    values = best_fields_by_key(fields)
    if required_keys and not required_keys.issubset(values):
        return progress
    return apply_ssu_progress_field_values(db, progress, values)


def apply_ssu_progress_field_values(
    db: Session,
    progress: ClinicalSsuProgress,
    values: dict[str, DocumentExtractedField],
) -> ClinicalSsuProgress:
    date_updated = False
    for key in ("submitted_at", "approved_at", "completed_at"):
        field = values.get(key)
        if field is None:
            continue
        next_value = date_value_for_field(field)
        if next_value is not None:
            setattr(progress, key, next_value)
            date_updated = True
    for key in ("version_info", "file_checklist", "summary", "fee_detail"):
        field = values.get(key)
        if field is None:
            continue
        next_value = field_text_value(field)
        if next_value is not None:
            setattr(progress, key, next_value)
    if date_updated:
        progress.status = "completed"
    db.flush()
    return progress


def sync_ssu_progress_from_fields(
    db: Session,
    progress: ClinicalSsuProgress,
    fields: list[DocumentExtractedField],
) -> ClinicalSsuProgress:
    values = best_fields_by_key(fields)
    required_keys = required_field_keys_for_progress(progress)
    if required_keys and not required_keys.issubset(values):
        return progress
    return apply_ssu_progress_field_values(db, progress, values)


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
