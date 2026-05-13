from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Protocol

from app.services.page_text_normalizer import NormalizedPageText, normalize_page_text


class SubjectItemLike(Protocol):
    id: int
    item_name: str
    item_code: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class DocumentRule:
    doc_type: str
    display_name: str
    target_code: str
    title_terms: tuple[str, ...]
    feature_terms: tuple[str, ...]
    negative_terms: tuple[str, ...] = ()
    priority: int = 50
    allow_continuation: bool = False


@dataclass(frozen=True)
class PageClassification:
    page_no: int
    doc_type: str | None
    display_name: str | None
    target_code: str | None
    confidence: float
    matched_title: tuple[str, ...]
    title_locations: tuple[str, ...]
    matched_features: tuple[str, ...]
    negative_hits: tuple[str, ...]
    reason: str
    allow_continuation: bool
    strong_title: bool
    subject_item_id: int | None = None


@dataclass(frozen=True)
class SegmentBuildResult:
    segments: list[dict[str, object]]
    debug_report: dict[str, object]


DOCUMENT_RULES: tuple[DocumentRule, ...] = (
    DocumentRule(
        doc_type="consent_transfer",
        display_name="知情同意书交接表",
        target_code="知情同意书交接表",
        title_terms=("知情同意书交接记录表", "知情同意书交接表", "交接记录表"),
        feature_terms=("交接", "接收", "知情同意书份数", "研究者交接"),
        priority=95,
    ),
    DocumentRule(
        doc_type="consent",
        display_name="知情同意书",
        target_code="知情同意书",
        title_terms=("知情同意书", "受试者知情同意书"),
        feature_terms=("受试者知情同意", "知情同意", "签署知情", "同意参加"),
        negative_terms=("交接", "接收", "门诊病历", "现病史", "入组评估", "随机时间", "随机号"),
        priority=80,
    ),
    DocumentRule(
        doc_type="ct_report",
        display_name="CT报告",
        target_code="CT报告",
        title_terms=("医学影像检查报告单", "CT报告", "CT检查报告", "影像检查报告"),
        feature_terms=("CT", "影像号", "检查所见", "报告医师", "放射科"),
        negative_terms=("胶囊内镜",),
        priority=88,
    ),
    DocumentRule(
        doc_type="his_record",
        display_name="HIS记录",
        target_code="HIS记录",
        title_terms=("门诊病历", "门诊电子病历", "HIS记录", "门诊记录"),
        feature_terms=("主诉", "现病史", "既往史", "诊断", "处方", "门诊号", "就诊时间"),
        priority=70,
        allow_continuation=True,
    ),
    DocumentRule(
        doc_type="enrollment_review",
        display_name="入组审核记录表",
        target_code="入组审核记录表",
        title_terms=("受试者入组审核确认表", "入组审核记录表", "入组评估", "入组审核"),
        feature_terms=(
            "入组",
            "入选标准",
            "入甜标准",
            "排除标准",
            "是否符合",
            "研究者签名",
            "随机时间",
            "随机结果",
            "随机号",
        ),
        priority=92,
        allow_continuation=True,
    ),
    DocumentRule(
        doc_type="vital_signs",
        display_name="生命体征记录表",
        target_code="生命体征记录表",
        title_terms=("生命体征记录表",),
        feature_terms=("体温", "脉搏", "呼吸", "血压", "收缩压", "舒张压"),
        negative_terms=("门诊病历",),
        priority=88,
    ),
    DocumentRule(
        doc_type="comfort",
        display_name="舒适度评价表",
        target_code="舒适度评价表",
        title_terms=("舒适度评价表",),
        feature_terms=("舒适", "疼痛", "VAS", "不适", "评价"),
        negative_terms=("门诊病历",),
        priority=86,
    ),
    DocumentRule(
        doc_type="center_reading_quality",
        display_name="中心阅片评价结果表",
        target_code="中心阅片评价结果表",
        title_terms=("独立评估人检查图像质量评估表", "检查图像质量评估表", "中心阅片评价结果表"),
        feature_terms=("独立评估人", "阅片", "图像质量评估", "评估人签名"),
        negative_terms=("阅片描述", "诊疗建议", "报告医生"),
        priority=96,
        allow_continuation=True,
    ),
    DocumentRule(
        doc_type="image_quality",
        display_name="图像质量评价表",
        target_code="图像质量评价表",
        title_terms=("图像质量评价表",),
        feature_terms=("图像质量", "图片质量", "清晰度", "完整性", "评价结果"),
        negative_terms=("独立评估人", "中心阅片", "设备常用功能", "设备稳定性"),
        priority=84,
        allow_continuation=True,
    ),
    DocumentRule(
        doc_type="device_secondary",
        display_name="其他次要指标评价表",
        target_code="其他次要指标评价表",
        title_terms=(
            "设备常用功能评价表",
            "设备稳定性评价表",
            "设备常用功能、设备稳定性、其他次要标准评价表",
            "设备常用功能、设各稳定性、其他次要标准评价表",
        ),
        feature_terms=("设备常用功能", "设备稳定性", "胶囊定位", "电池", "下载", "传输"),
        negative_terms=("门诊病历",),
        priority=93,
        allow_continuation=True,
    ),
    DocumentRule(
        doc_type="other_secondary",
        display_name="其他次要指标评价表",
        target_code="其他次要指标评价表",
        title_terms=("其他次要标准评价表", "其他次要指标评价表"),
        feature_terms=(
            "其他次要标准",
            "胶囊内镜报告信息",
            "胶囊内镜报告",
            "胃通过时间",
            "小肠通过时间",
        ),
        negative_terms=("门诊病历",),
        priority=91,
    ),
    DocumentRule(
        doc_type="capsule_endoscopy_report",
        display_name="胶囊内镜报告",
        target_code="胶囊内镜报告",
        title_terms=("胶囊内镜报告", "胶囊内镜检查报告"),
        feature_terms=(
            "检查所见",
            "诊断意见",
            "检查结果",
            "诊疗建议",
            "报告医生",
            "报告日期",
            "阅片描述",
            "胃通过时间",
            "小肠通过时间",
            "胶囊内镜",
        ),
        negative_terms=("报告信息", "其他次要标准", "其他次要指标"),
        priority=82,
    ),
)


def normalize_for_match(value: str) -> str:
    text = normalize_page_text(value).normalized_text
    return re.sub(r"[\s_：:，,。.;；、（）()【】\[\]《》<>/\\|·~\-—]+", "", text).lower()


def matched_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    normalized_text = normalize_for_match(text)
    return tuple(term for term in terms if normalize_for_match(term) in normalized_text)


def title_locations(page: NormalizedPageText, title_hits: tuple[str, ...]) -> tuple[str, ...]:
    locations: list[str] = []
    head_text = "\n".join(page.head_lines)
    tail_text = "\n".join(page.tail_lines)
    for title in title_hits:
        normalized_title = normalize_for_match(title)
        if normalized_title and normalized_title in normalize_for_match(head_text):
            locations.append("head")
        elif normalized_title and normalized_title in normalize_for_match(tail_text):
            locations.append("tail")
        else:
            locations.append("body")
    return tuple(dict.fromkeys(locations))


def title_match_length(title_hits: tuple[str, ...]) -> int:
    if not title_hits:
        return 0
    return max(len(normalize_for_match(title)) for title in title_hits)


def score_rule(page: NormalizedPageText, rule: DocumentRule) -> PageClassification | None:
    title_hits = matched_terms(page.normalized_text, rule.title_terms)
    locations = title_locations(page, title_hits)
    feature_hits = matched_terms(page.normalized_text, rule.feature_terms)
    negative_hits = matched_terms(page.normalized_text, rule.negative_terms)
    if not title_hits and not feature_hits:
        return None

    if title_hits and "head" in locations:
        confidence = 0.84
    elif title_hits:
        confidence = 0.68
    else:
        confidence = 0.42
    confidence += min(0.18, len(feature_hits) * 0.045)
    confidence -= min(0.28, len(negative_hits) * 0.14)
    confidence = round(max(0, min(0.99, confidence)), 3)
    if confidence < 0.35:
        return None

    reasons = []
    if title_hits:
        reasons.append(f"title={'+'.join(title_hits)}")
        reasons.append(f"title_location={'+'.join(locations)}")
    if feature_hits:
        reasons.append(f"features={'+'.join(feature_hits[:5])}")
    if negative_hits:
        reasons.append(f"negative={'+'.join(negative_hits)}")
    reasons.append(f"priority={rule.priority}")
    return PageClassification(
        page_no=0,
        doc_type=rule.doc_type,
        display_name=rule.display_name,
        target_code=rule.target_code,
        confidence=confidence,
        matched_title=title_hits,
        title_locations=locations,
        matched_features=feature_hits,
        negative_hits=negative_hits,
        reason="; ".join(reasons),
        allow_continuation=rule.allow_continuation,
        strong_title=bool(title_hits),
    )


def best_rule_classification(page_no: int, page: NormalizedPageText) -> PageClassification | None:
    matches = [match for rule in DOCUMENT_RULES if (match := score_rule(page, rule)) is not None]
    if not matches:
        return None
    priority_by_type = {rule.doc_type: rule.priority for rule in DOCUMENT_RULES}
    best = max(
        matches,
        key=lambda item: (
            item.confidence,
            title_match_length(item.matched_title),
            priority_by_type.get(item.doc_type or "", 0),
            item.strong_title,
        ),
    )
    return PageClassification(**{**asdict(best), "page_no": page_no})


def best_candidate_classification(
    page_no: int,
    page: NormalizedPageText,
    candidates: list[SubjectItemLike],
) -> PageClassification | None:
    normalized_text = normalize_for_match(page.normalized_text)
    if not normalized_text:
        return None
    best: PageClassification | None = None
    for candidate in candidates:
        checks = [
            (candidate.item_name, 0.74, "item_name"),
            (candidate.item_code, 0.7, "item_code"),
            *[(keyword, 0.68, "keyword") for keyword in candidate.keywords],
        ]
        for keyword, confidence, source in checks:
            normalized_keyword = normalize_for_match(keyword)
            if not normalized_keyword or normalized_keyword not in normalized_text:
                continue
            match = PageClassification(
                page_no=page_no,
                doc_type=f"subject_item:{candidate.item_code}",
                display_name=candidate.item_name,
                target_code=candidate.item_code,
                confidence=confidence,
                matched_title=(),
                title_locations=(),
                matched_features=(keyword,),
                negative_hits=(),
                reason=f"fallback {source}={keyword}",
                allow_continuation=False,
                strong_title=False,
                subject_item_id=candidate.id,
            )
            if best is None or match.confidence > best.confidence:
                best = match
    return best


def classify_page(
    page_no: int,
    page: NormalizedPageText | str,
    candidates: list[SubjectItemLike],
) -> PageClassification:
    normalized_page = normalize_page_text(page) if isinstance(page, str) else page
    rule_match = best_rule_classification(page_no, normalized_page)
    if rule_match is not None:
        return rule_match
    candidate_match = best_candidate_classification(page_no, normalized_page, candidates)
    if candidate_match is not None:
        return candidate_match
    return PageClassification(
        page_no=page_no,
        doc_type=None,
        display_name=None,
        target_code=None,
        confidence=0,
        matched_title=(),
        title_locations=(),
        matched_features=(),
        negative_hits=(),
        reason="no registry or subject-item keyword hit",
        allow_continuation=False,
        strong_title=False,
    )


def compact_text(texts: list[str], max_length: int = 4000) -> str:
    value = "\n".join(text.strip() for text in texts if text.strip())
    return value[:max_length]


def candidate_lookup(candidates: list[SubjectItemLike]) -> dict[str, SubjectItemLike]:
    lookup: dict[str, SubjectItemLike] = {}
    for candidate in candidates:
        lookup[normalize_for_match(candidate.item_code)] = candidate
        lookup[normalize_for_match(candidate.item_name)] = candidate
    return lookup


def resolve_subject_item(
    classification: PageClassification,
    candidates: list[SubjectItemLike],
) -> SubjectItemLike | None:
    if classification.subject_item_id is not None:
        return next(
            (
                candidate
                for candidate in candidates
                if candidate.id == classification.subject_item_id
            ),
            None,
        )
    lookup = candidate_lookup(candidates)
    for key in (classification.target_code, classification.display_name):
        if key is None:
            continue
        candidate = lookup.get(normalize_for_match(key))
        if candidate is not None:
            return candidate
    return None


def should_start_new_segment(
    current: PageClassification,
    next_page: PageClassification,
) -> tuple[bool, str]:
    if current.doc_type is None and next_page.doc_type is None:
        return False, "continued unknown pages"
    if current.doc_type is None or next_page.doc_type is None:
        if next_page.doc_type is None and current.allow_continuation:
            return False, "continued previous multi-page document through weak/blank page"
        return True, "recognized/unknown boundary"
    if next_page.strong_title and next_page.doc_type != current.doc_type:
        return True, "strong title starts a new document type"
    if next_page.doc_type != current.doc_type:
        return True, "document type changed"
    return False, "same document type"


def payload_for_segment(
    page_texts: list[str],
    classifications: list[PageClassification],
    candidates: list[SubjectItemLike],
    start: int,
    end: int,
    reason: str,
) -> dict[str, object]:
    classification = classifications[start - 1]
    candidate = resolve_subject_item(classification, candidates)
    return {
        "page_start": start,
        "page_end": end,
        "detected_name": candidate.item_name if candidate else classification.display_name,
        "detected_code": candidate.item_code if candidate else classification.target_code,
        "confidence": classification.confidence,
        "suggested_subject_item_id": candidate.id if candidate else None,
        "ocr_text": compact_text(page_texts[start - 1 : end]),
        "_debug": {
            "doc_type": classification.doc_type,
            "reason": reason,
            "page_reasons": [item.reason for item in classifications[start - 1 : end]],
        },
    }


def build_document_segments(
    page_texts: list[str],
    candidates: list[SubjectItemLike],
) -> SegmentBuildResult:
    normalized_pages = [normalize_page_text(text) for text in page_texts]
    classifications = [
        classify_page(page_no, page, candidates)
        for page_no, page in enumerate(normalized_pages, start=1)
    ]
    if not classifications:
        return SegmentBuildResult(segments=[], debug_report={"pages": [], "segments": []})

    segments: list[dict[str, object]] = []
    start = 1
    segment_reason = "first page"
    current = classifications[0]
    for index, classification in enumerate(classifications[1:], start=2):
        should_split, reason = should_start_new_segment(current, classification)
        if should_split:
            segments.append(
                payload_for_segment(
                    page_texts,
                    classifications,
                    candidates,
                    start,
                    index - 1,
                    segment_reason,
                )
            )
            start = index
            segment_reason = reason
            current = classification
        elif classification.doc_type is not None:
            current = classification

    segments.append(
        payload_for_segment(
            page_texts,
            classifications,
            candidates,
            start,
            len(classifications),
            segment_reason,
        )
    )

    debug_segments = []
    for segment in segments:
        debug = segment.pop("_debug")
        debug_segments.append({**segment, **debug})

    return SegmentBuildResult(
        segments=segments,
        debug_report={
            "pages": [
                {
                    **asdict(classification),
                    "raw_text": normalized_page.raw_text,
                    "normalized_text": normalized_page.normalized_text,
                    "head_lines": normalized_page.head_lines,
                    "tail_lines": normalized_page.tail_lines,
                }
                for classification, normalized_page in zip(
                    classifications,
                    normalized_pages,
                    strict=True,
                )
            ],
            "segments": debug_segments,
        },
    )
