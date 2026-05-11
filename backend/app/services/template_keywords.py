import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path
from app.models import FileAsset, StageTemplate, Subject, SubjectItem
from app.services.pdf_packets import (
    extract_page_texts,
    normalize_for_match,
    pdf_page_count,
    split_keywords,
)

TITLE_MARKERS = (
    "表",
    "报告",
    "记录",
    "评价",
    "知情",
    "同意",
    "检查",
    "HIS",
    "CT",
    "X线",
    "胶囊",
    "生命体征",
    "入组",
    "随机",
    "肠道",
    "安全事件",
    "器械缺陷",
    "阅片",
)
SENSITIVE_MARKERS = (
    "签名",
    "日期",
    "电话",
    "身份证",
    "姓名",
    "性别",
    "年龄",
    "住院号",
    "门诊号",
    "病历号",
    "联系方式",
)


@dataclass
class KeywordGenerationItem:
    subject_item_id: int
    stage_template_id: int | None
    item_name: str
    item_code: str
    status: str
    keywords: list[str] = field(default_factory=list)
    keyword_count: int = 0
    ocr_page_count: int = 0
    message: str | None = None


@dataclass
class KeywordGenerationResult:
    subject_id: int
    updated_count: int
    skipped_count: int
    items: list[KeywordGenerationItem]


def clean_keyword(value: str) -> str | None:
    keyword = re.sub(r"\s+", "", value.strip())
    keyword = keyword.strip("-_—=：:，,。.;；（）()【】[]《》<>")
    if len(keyword) < 2 or len(keyword) > 30:
        return None
    if re.search(r"\d{4,}", keyword):
        return None
    if any(marker in keyword for marker in SENSITIVE_MARKERS):
        return None
    if keyword.startswith("扫描全能王"):
        return None
    return keyword


def dedupe_keywords(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        keyword = clean_keyword(value)
        if not keyword:
            continue
        normalized = normalize_for_match(keyword)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(keyword)
        if len(result) >= limit:
            break
    return result


def filename_keywords(file_asset: FileAsset, screening_no: str) -> list[str]:
    stem = Path(file_asset.original_name).stem
    stem = re.sub(rf"^{re.escape(screening_no)}[-_ ]*", "", stem)
    return [stem]


def text_keywords(page_texts: list[str]) -> list[str]:
    keywords: list[str] = []
    for text in page_texts:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if not any(marker in line for marker in TITLE_MARKERS):
                continue
            keywords.append(line)
    return keywords


def generate_keywords_from_subject(
    db: Session,
    subject: Subject,
    mode: str,
    max_keywords_per_item: int,
) -> KeywordGenerationResult:
    items = list(
        db.scalars(
            select(SubjectItem)
            .where(SubjectItem.subject_id == subject.id)
            .order_by(SubjectItem.id)
        )
    )
    updated_count = 0
    skipped_count = 0
    result_items: list[KeywordGenerationItem] = []

    for item in items:
        result = KeywordGenerationItem(
            subject_item_id=item.id,
            stage_template_id=item.stage_template_id,
            item_name=item.item_name,
            item_code=item.item_code,
            status="skipped",
        )
        template = db.get(StageTemplate, item.stage_template_id or 0)
        if template is None:
            result.message = "资料项未绑定模板"
            skipped_count += 1
            result_items.append(result)
            continue

        files = list(
            db.scalars(
                select(FileAsset)
                .where(
                    FileAsset.subject_item_id == item.id,
                    FileAsset.status == "active",
                    FileAsset.mime_type == "application/pdf",
                )
                .order_by(FileAsset.uploaded_at.desc(), FileAsset.id.desc())
            )
        )

        candidates = [item.item_name, item.item_code]
        page_count = 0
        messages: list[str] = []
        if not files:
            messages.append("资料项没有PDF文件")
        for file_asset in files:
            candidates.extend(filename_keywords(file_asset, subject.screening_no))
            try:
                path = ensure_relative_path(settings.file_storage_root, file_asset.storage_path)
                if not path.exists():
                    messages.append(f"{file_asset.original_name} 文件不存在")
                    continue
                file_page_count = pdf_page_count(path)
                page_count += file_page_count
                candidates.extend(text_keywords(extract_page_texts(path, file_page_count)))
            except Exception as exc:
                messages.append(f"{file_asset.original_name}: {exc}")
                continue

        generated = dedupe_keywords(candidates, max_keywords_per_item)
        if mode == "merge":
            generated = dedupe_keywords(
                [*split_keywords(template.recognition_keywords), *generated],
                max_keywords_per_item,
            )
        template.recognition_keywords = "\n".join(generated) if generated else None
        result.status = "updated"
        result.keywords = generated
        result.keyword_count = len(generated)
        result.ocr_page_count = page_count
        result.message = "；".join(messages) if messages else None
        updated_count += 1
        result_items.append(result)

    return KeywordGenerationResult(
        subject_id=subject.id,
        updated_count=updated_count,
        skipped_count=skipped_count,
        items=result_items,
    )
