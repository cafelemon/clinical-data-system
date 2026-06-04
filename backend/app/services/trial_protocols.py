import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import ensure_relative_path, normalize_mime_type, safe_path_part
from app.models import Center, Project, Stage, StageTemplate, TrialProtocolVersion
from app.services.pdf_packets import PdfPacketError, pdf_page_count
from app.services.protocol_text_parser import ProtocolTextLine, compact_line, extract_protocol_text
from app.services.stage_config import SUBJECT_ITEM_SCOPE, ensure_project_stage_config
from app.services.subject_setup import sync_project_subject_sections


class TrialProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class StoredProtocol:
    original_name: str
    storage_path: str
    file_hash: str
    file_size: int


VISIT_NAME_KEYWORDS = (
    ("筛选期", "筛选期"),
    ("胶囊检查", "检查期-胶囊检查日"),
    ("结肠镜", "检查期-结肠镜检查日"),
    ("胶囊排出", "非预期随访-胶囊排出确认"),
    ("胶囊滞留", "非预期随访-胶囊滞留处理"),
)

INSTITUTION_TERMS = (
    "医院",
    "中心",
    "大学",
    "院区",
    "医科",
    "总院",
    "分院",
    "附属",
)
COMMON_CHINESE_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
    "金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方"
    "俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮"
    "卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计"
    "伏成戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童"
    "颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万支柯昝管卢莫经房裘"
    "缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊於"
    "惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓"
    "蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司"
    "韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴欎胥能苍"
    "双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕"
    "冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾"
    "终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍"
    "聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆"
    "红游竺权逯盖益桓公"
)
INSTITUTION_LEADING_TERMS = (
    "首都",
    "北京",
    "上海",
    "天津",
    "重庆",
    "陆军",
    "海军",
    "空军",
    "中国",
    "人民",
    "解放",
)
LOCATION_SUFFIX_CHARS = "州京沪津渝都省市县区"
FIELD_HEADER_TERMS = (
    "临床试验",
    "机构名称",
    "机构代号",
    "备案号",
    "研究者",
    "附件",
)
CONFIRMATION_ERROR = "存在未确认的高风险中心字段，请确认后再应用"


def write_protocol_upload(
    project: Project,
    upload_file: UploadFile,
    version_number: int,
) -> StoredProtocol:
    original_name = Path(upload_file.filename or "trial-protocol.pdf").name
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="trial protocol must be a PDF file",
        )
    mime_type = normalize_mime_type(upload_file.content_type, original_name)
    if mime_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="trial protocol must be a PDF file",
        )

    target_dir = (
        Path("projects")
        / safe_path_part(project.code)
        / "trial_protocols"
        / f"v{version_number}"
    )
    stored_name = f"{uuid4().hex}.pdf"
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

    return StoredProtocol(
        original_name=original_name,
        storage_path=relative_path.as_posix(),
        file_hash=hasher.hexdigest(),
        file_size=size,
    )


def next_protocol_version_number(db: Session, project_id: int) -> int:
    current = db.scalar(
        select(func.max(TrialProtocolVersion.version_number)).where(
            TrialProtocolVersion.project_id == project_id
        )
    )
    return int(current or 0) + 1


def parse_protocol_file(
    path: Path,
) -> tuple[int, dict[str, Any], str | None, str | None, str | None]:
    try:
        page_count = pdf_page_count(path)
        extraction = extract_protocol_text(path, page_count)
    except PdfPacketError as exc:
        raise TrialProtocolError(str(exc)) from exc

    page_texts = extraction.page_texts
    protocol_no, protocol_version, protocol_date = parse_protocol_meta(page_texts)
    visits = parse_visits(page_texts)
    centers = parse_centers(page_texts, extraction.lines)
    risky_centers = sum(1 for center in centers if center.get("requires_confirmation"))
    draft = {
        "visits": visits,
        "centers": centers,
        "deactivate_missing": {
            "visits": False,
            "items": False,
            "centers": False,
        },
        "parse_meta": {
            "text_source": extraction.source,
            "page_count": page_count,
            "center_count": len(centers),
            "center_risk_count": risky_centers,
            "evidence_mode": "summary",
        },
    }
    return page_count, draft, protocol_no, protocol_version, protocol_date


def parse_protocol_meta(page_texts: list[str]) -> tuple[str | None, str | None, str | None]:
    joined = "\n".join(page_texts[:3])
    protocol_no = _first_match(r"方案编号[:：]\s*([A-Za-z0-9_.\-]+)", joined)
    version_date = re.search(r"版本号/日期[:：]\s*([^\s/]+)\s*/\s*([0-9 年月日\-/.]+)", joined)
    if version_date:
        return protocol_no, version_date.group(1).strip(), version_date.group(2).strip()
    return protocol_no, None, None


def parse_visits(page_texts: list[str]) -> list[dict[str, Any]]:
    flow_text = next((text for text in page_texts if "试验流程" in text and "访视" in text), "")
    if not flow_text:
        return []

    lines = flow_text.splitlines()
    visit_line = next((line for line in lines if "访视" in line and "V" in line), "")
    raw_visit_matches = list(re.finditer(r"V\s*\d+(?:\.\d+)?(?:\d{1,2})?", visit_line))
    if not raw_visit_matches:
        return []

    visit_positions = [match.start() for match in raw_visit_matches]
    visit_names = infer_visit_names(flow_text, len(visit_positions))
    visits = [
        {
            "ordinal": index + 1,
            "source_visit_code": normalize_visit_code(match.group(0), index + 1),
            "name": visit_names[index] if index < len(visit_names) else f"访视{index + 1}",
            "window": infer_visit_window(lines, index),
            "enabled": True,
            "items": [],
        }
        for index, match in enumerate(raw_visit_matches)
    ]

    pending_item_name: str | None = None
    for line in lines:
        if should_skip_flow_line(line):
            pending_item_name = None
            continue
        marker_matches = list(re.finditer(r"√\*?", line))
        if not marker_matches:
            candidate = clean_item_name(line.strip())
            if candidate:
                pending_item_name = candidate
            continue

        first_marker = marker_matches[0].start()
        item_name = clean_item_name(line[:first_marker].strip()) or pending_item_name
        pending_item_name = None
        if not item_name:
            continue
        for marker in marker_matches:
            visit_index = nearest_visit_index(marker.start(), visit_positions)
            visits[visit_index]["items"].append(
                {
                    "ordinal": len(visits[visit_index]["items"]) + 1,
                    "name": item_name,
                    "required": marker.group(0) == "√",
                    "enabled": True,
                }
            )

    return visits


def infer_visit_names(flow_text: str, count: int) -> list[str]:
    names = [name for keyword, name in VISIT_NAME_KEYWORDS if keyword in flow_text]
    return names[:count]


def infer_visit_window(lines: list[str], visit_index: int) -> str | None:
    window_line = next((line for line in lines if "窗口期" in line), "")
    if not window_line:
        return None
    windows = re.findall(r"(?:-\d+~\s*-?\d+\s*天|第\s*\d+(?:-\d+|\+\d+)?\s*天)", window_line)
    return windows[visit_index].strip() if visit_index < len(windows) else None


def normalize_visit_code(value: str, ordinal: int) -> str:
    compact = value.replace(" ", "")
    dotted = re.match(r"V(\d+)\.(\d+)", compact)
    if dotted:
        return f"V{dotted.group(1)}.{dotted.group(2)}"
    simple = re.match(r"V(\d+)", compact)
    return f"V{simple.group(1)}" if simple else f"V{ordinal}"


def nearest_visit_index(position: int, visit_positions: list[int]) -> int:
    return min(
        range(len(visit_positions)),
        key=lambda index: abs(position - visit_positions[index]),
    )


def should_skip_flow_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    skip_terms = (
        "方案编号",
        "版本号",
        "试验流程",
        "随访",
        "窗口期",
        "访视",
        "备注",
        "（",
        "则",
        "本院",
        "页",
    )
    return any(stripped.startswith(term) for term in skip_terms) or stripped.isdigit()


def clean_item_name(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value)
    cleaned = re.sub(r"\d+$", "", cleaned)
    cleaned = cleaned.strip("：:")
    if len(cleaned) < 2:
        return ""
    if cleaned.startswith("（") or cleaned.startswith("("):
        return ""
    return cleaned


def parse_centers(
    page_texts: list[str],
    text_lines: list[ProtocolTextLine] | None = None,
) -> list[dict[str, Any]]:
    center_page_no, center_text = next(
        (
            (page_index + 1, text)
            for page_index, text in enumerate(page_texts)
            if "临床试验机构" in text and "机构代号" in text
        ),
        (None, ""),
    )
    if center_page_no is None or not center_text:
        return []
    lines = scoped_center_lines(center_text, center_page_no, text_lines)
    centers: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if re.match(r"^\s*20\d{7}\s*$", line.text):
            continue
        match = re.match(r"^\s*(\d{2})\s*(.*)$", line.text)
        if match is None:
            continue
        code = match.group(1)
        inline = match.group(2).strip()
        window = lines[max(0, index - 2) : min(len(lines), index + 4)]
        center_name, investigator, filing_no, mixed_investigator = parse_center_fields(
            code,
            inline,
            window,
        )
        if not center_name:
            continue
        risk_reasons = center_risk_reasons(
            code=code,
            center_name=center_name,
            filing_no=filing_no,
            investigator=investigator,
            mixed_investigator=mixed_investigator,
        )
        confidence = center_confidence(risk_reasons, window)
        centers.append(
            {
                "code": code,
                "name": center_name,
                "filing_no": filing_no,
                "principal_investigator": investigator,
                "enabled": True,
                "confidence": confidence,
                "requires_confirmation": bool(risk_reasons),
                "confirmed": not risk_reasons,
                "evidence": {
                    "page_no": line.page_no,
                    "source": line.source,
                    "lines": evidence_lines(window),
                    "risk_reasons": risk_reasons,
                },
            }
        )
    return centers


def scoped_center_lines(
    center_text: str,
    center_page_no: int,
    text_lines: list[ProtocolTextLine] | None,
) -> list[ProtocolTextLine]:
    if text_lines:
        page_lines = [
            line
            for line in text_lines
            if line.page_no == center_page_no and line.text.strip()
        ]
        if page_lines:
            return page_lines
    return [
        ProtocolTextLine(page_no=center_page_no, text=line, source="page_text")
        for line in center_text.splitlines()
        if line.strip()
    ]


def parse_center_fields(
    code: str,
    inline: str,
    window: list[ProtocolTextLine],
) -> tuple[str, str | None, str | None, bool]:
    raw_values = scoped_center_field_values(code, inline, window)
    compact_values = [compact_line(value) for value in raw_values]
    combined = "\n".join(raw_values)
    compact_combined = "".join(compact_values)

    filing_no = _first_match(r"(20\d{7})", combined)
    investigator = extract_investigator(inline) or extract_investigator_from_values(raw_values)
    mixed_investigator = False

    candidates = []
    for value in raw_values:
        if is_mixed_investigator_line(value, investigator):
            mixed_investigator = True
        candidate = clean_center_name_candidate(value, investigator)
        if candidate:
            candidates.append(candidate)
    fragment_candidate = clean_center_name_candidate(
        "".join(center_name_fragments(raw_values, investigator)),
        investigator,
    )
    if fragment_candidate:
        candidates.append(fragment_candidate)
    compact_candidate = clean_center_name_candidate(compact_combined, investigator)
    if compact_candidate:
        candidates.append(compact_candidate)

    center_name = best_center_name(candidates) or fallback_risky_center_name(raw_values)
    return center_name, investigator, filing_no, mixed_investigator


def scoped_center_field_values(
    code: str,
    inline: str,
    window: list[ProtocolTextLine],
) -> list[str]:
    code_line_index = next(
        (
            index
            for index, line in enumerate(window)
            if re.match(rf"^\s*{re.escape(code)}\b", line.text)
        ),
        0,
    )
    values: list[str] = []
    for line in reversed(window[:code_line_index]):
        text = line.text.strip()
        if is_center_code_line(text) or is_center_header_line(text):
            break
        values.insert(0, text)
    values.append(inline)
    for line in window[code_line_index + 1 :]:
        text = line.text.strip()
        if is_center_code_line(text):
            break
        values.append(text)
    return [value for value in values if value.strip()]


def is_center_code_line(value: str) -> bool:
    return re.match(r"^\s*\d{2}\b", value) is not None


def is_center_header_line(value: str) -> bool:
    compact = compact_line(value)
    return any(term in compact for term in FIELD_HEADER_TERMS)


def is_mixed_investigator_line(value: str, investigator: str | None) -> bool:
    if not investigator or investigator not in value:
        return False
    if not any(term in value for term in INSTITUTION_TERMS):
        return False
    # Normal table extraction often separates the investigator column with wide
    # whitespace. Treat only visually glued values as risky.
    return re.search(rf"\s{{2,}}{re.escape(investigator)}\s*$", value) is None


def clean_center_name_candidate(value: str, investigator: str | None) -> str:
    cleaned = strip_filing_label(value)
    cleaned = re.sub(r"^\d{2}", "", cleaned)
    if investigator:
        cleaned = cleaned.replace(investigator, "")
    for term in FIELD_HEADER_TERMS:
        cleaned = cleaned.replace(term, "")
    cleaned = re.sub(r"[\s:：|｜]+", "", cleaned)
    cleaned = re.sub(r"^[一二三四五六七八九十、.．]+", "", cleaned)
    return cleaned.strip()


def center_name_fragments(values: list[str], investigator: str | None) -> list[str]:
    fragments: list[str] = []
    for value in values:
        cleaned = clean_center_name_candidate(value, investigator)
        if not cleaned:
            continue
        if re.fullmatch(r"20\d{7}", cleaned):
            continue
        if investigator and cleaned == investigator:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", cleaned) and not any(
            term in cleaned for term in INSTITUTION_TERMS
        ):
            continue
        fragments.append(cleaned)
    return fragments


def best_center_name(candidates: list[str]) -> str:
    institution_candidates = [
        candidate
        for candidate in candidates
        if is_valid_institution_name(candidate)
    ]
    if institution_candidates:
        return max(institution_candidates, key=len)
    long_candidates = [candidate for candidate in candidates if len(candidate) >= 5]
    return max(long_candidates, key=len) if long_candidates else ""


def fallback_risky_center_name(values: list[str]) -> str:
    for value in values:
        cleaned = clean_center_name_candidate(value, investigator=None)
        if not cleaned:
            continue
        if re.fullmatch(r"20\d{7}", cleaned):
            continue
        return cleaned
    return ""


def extract_investigator(value: str) -> str | None:
    parts = re.split(r"\s{2,}", value.strip())
    if len(parts) >= 2 and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", parts[-1]):
        return parts[-1]
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value.strip()):
        return value.strip()
    return None


def extract_investigator_from_values(values: list[str]) -> str | None:
    for value in values:
        investigator = extract_investigator(value)
        if investigator:
            return investigator
    for value in values:
        investigator = extract_glued_leading_investigator(value)
        if investigator:
            return investigator
    for value in values:
        compact = compact_line(value)
        matches = re.findall(r"[\u4e00-\u9fff]{2,4}", compact)
        for match in reversed(matches):
            if not is_valid_institution_name(match) and not any(
                term in match for term in FIELD_HEADER_TERMS
            ):
                return match
    return None


def extract_glued_leading_investigator(value: str) -> str | None:
    compact = clean_center_name_candidate(value, investigator=None)
    compact = re.sub(r"^\d{2}", "", compact)
    if len(compact) < 7 or compact[:2] in INSTITUTION_LEADING_TERMS:
        return None
    for name_length in range(2, 5):
        possible_name = compact[:name_length]
        possible_institution = compact[name_length:]
        if possible_name[0] not in COMMON_CHINESE_SURNAMES:
            continue
        if possible_name.endswith(tuple(LOCATION_SUFFIX_CHARS)):
            continue
        if any(term in possible_name for term in INSTITUTION_TERMS):
            continue
        if is_valid_institution_name(possible_institution):
            return possible_name
    return None


def is_valid_institution_name(value: str) -> bool:
    return len(value) >= 5 and any(term in value for term in INSTITUTION_TERMS)


def center_risk_reasons(
    code: str,
    center_name: str,
    filing_no: str | None,
    investigator: str | None,
    mixed_investigator: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if not re.fullmatch(r"\d{2}", code):
        reasons.append("机构代号格式异常")
    if not is_valid_institution_name(center_name):
        reasons.append("机构名称缺少医院/中心等特征")
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", center_name):
        reasons.append("机构名称疑似人名")
    if not filing_no or not re.fullmatch(r"20\d{7}", filing_no):
        reasons.append("备案号缺失或格式异常")
    if not investigator or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", investigator):
        reasons.append("研究者缺失或格式异常")
    if investigator and investigator in center_name:
        reasons.append("研究者疑似混入机构名称")
    if mixed_investigator:
        reasons.append("OCR行疑似混合机构名称和研究者")
    return reasons


def center_confidence(risk_reasons: list[str], window: list[ProtocolTextLine]) -> float:
    block_scores = [
        line.confidence for line in window if isinstance(line.confidence, int | float)
    ]
    block_score = sum(block_scores) / len(block_scores) if block_scores else 0.9
    penalty = min(0.6, len(risk_reasons) * 0.18)
    return round(max(0.0, min(1.0, block_score - penalty)), 2)


def evidence_lines(window: list[ProtocolTextLine]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in window:
        stripped = line.text.strip()
        if not stripped:
            continue
        result.append(
            {
                "page_no": line.page_no,
                "text": stripped[:160],
                "source": line.source,
                "confidence": line.confidence,
            }
        )
    return result[:6]


def strip_filing_label(value: str) -> str:
    cleaned = value.replace("械临机构备", "")
    cleaned = re.sub(r"20\d{7}", "", cleaned)
    return re.sub(r"\s+", "", cleaned)


def apply_protocol_draft(
    db: Session,
    project: Project,
    draft: dict[str, Any],
) -> dict[str, Any]:
    ensure_project_stage_config(db, project)
    trial_parent = db.scalar(
        select(Stage).where(
            Stage.project_id == project.id,
            Stage.code == "TRIAL",
            Stage.parent_id.is_(None),
        )
    )
    if trial_parent is None:
        raise TrialProtocolError("TRIAL parent stage was not initialized")
    ensure_centers_confirmed(draft)

    result = {
        "created_stages": 0,
        "updated_stages": 0,
        "created_templates": 0,
        "updated_templates": 0,
        "created_centers": 0,
        "updated_centers": 0,
        "synced_subjects": 0,
        "created_subject_sections": 0,
        "created_subject_items": 0,
        "removed_empty_legacy_sections": 0,
        "retained_legacy_sections": 0,
    }
    for visit in draft.get("visits", []):
        if not visit.get("enabled", True):
            continue
        ordinal = int(visit.get("ordinal") or 0)
        if ordinal <= 0:
            continue
        stage_code = f"PROTOCOL_VISIT_{ordinal:03d}"
        stage_name = f"访视{ordinal}:{str(visit.get('name') or f'访视{ordinal}').strip()}"
        stage = db.scalar(
            select(Stage).where(Stage.project_id == project.id, Stage.code == stage_code)
        )
        if stage is None:
            stage = Stage(
                project_id=project.id,
                parent_id=trial_parent.id,
                phase_code="TRIAL",
                option_code=stage_code,
                code=stage_code,
                name=stage_name,
                sort_order=100 + ordinal,
                enabled=True,
                description=visit.get("window"),
            )
            db.add(stage)
            db.flush()
            result["created_stages"] += 1
        else:
            stage.parent_id = trial_parent.id
            stage.phase_code = "TRIAL"
            stage.option_code = stage_code
            stage.name = stage_name
            stage.enabled = True
            stage.sort_order = 100 + ordinal
            stage.description = visit.get("window")
            result["updated_stages"] += 1

        for item in visit.get("items", []):
            if not item.get("enabled", True):
                continue
            item_ordinal = int(item.get("ordinal") or 0)
            if item_ordinal <= 0:
                continue
            item_name = str(item.get("name") or "").strip()
            if not item_name:
                continue
            item_code = f"PROTOCOL_V{ordinal:03d}_ITEM{item_ordinal:03d}"
            template = db.scalar(
                select(StageTemplate).where(
                    StageTemplate.project_id == project.id,
                    StageTemplate.stage_id == stage.id,
                    StageTemplate.template_scope == SUBJECT_ITEM_SCOPE,
                    StageTemplate.item_code == item_code,
                )
            )
            if template is None:
                db.add(
                    StageTemplate(
                        project_id=project.id,
                        stage_id=stage.id,
                        template_scope=SUBJECT_ITEM_SCOPE,
                        item_name=item_name,
                        item_code=item_code,
                        required=bool(item.get("required", True)),
                        sort_order=item_ordinal,
                        recognition_keywords=item_name,
                        description=None,
                    )
                )
                result["created_templates"] += 1
            else:
                template.item_name = item_name
                template.required = bool(item.get("required", True))
                template.sort_order = item_ordinal
                template.recognition_keywords = item_name
                result["updated_templates"] += 1

    for center_data in draft.get("centers", []):
        if not center_data.get("enabled", True):
            continue
        center_code = str(center_data.get("code") or "").strip()
        center_name = str(center_data.get("name") or "").strip()
        if not center_code or not center_name:
            continue
        description = center_description(center_data)
        center = db.scalar(
            select(Center).where(Center.project_id == project.id, Center.code == center_code)
        )
        if center is None:
            db.add(
                Center(
                    project_id=project.id,
                    code=center_code,
                    name=center_name,
                    contact_person=center_data.get("principal_investigator"),
                    status="active",
                    description=description,
                )
            )
            result["created_centers"] += 1
        else:
            center.name = center_name
            center.contact_person = center_data.get("principal_investigator")
            center.description = description
            result["updated_centers"] += 1
    db.flush()
    subject_sync = sync_project_subject_sections(db, project.id)
    result.update(subject_sync.to_dict())
    return result


def ensure_centers_confirmed(draft: dict[str, Any]) -> None:
    for center_data in draft.get("centers", []):
        if not center_data.get("enabled", True):
            continue
        if center_data.get("requires_confirmation") and not center_data.get("confirmed"):
            raise TrialProtocolError(CONFIRMATION_ERROR)


def center_description(center_data: dict[str, Any]) -> str | None:
    filing_no = str(center_data.get("filing_no") or "").strip()
    return f"备案号：{filing_no}" if filing_no else None


def _first_match(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value)
    return match.group(1).strip() if match else None
