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
from app.services.pdf_packets import PdfPacketError, extract_page_texts, pdf_page_count
from app.services.stage_config import SUBJECT_ITEM_SCOPE, ensure_project_stage_config


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
        page_texts = extract_page_texts(path, page_count)
    except PdfPacketError as exc:
        raise TrialProtocolError(str(exc)) from exc

    protocol_no, protocol_version, protocol_date = parse_protocol_meta(page_texts)
    visits = parse_visits(page_texts)
    centers = parse_centers(page_texts)
    draft = {
        "visits": visits,
        "centers": centers,
        "deactivate_missing": {
            "visits": False,
            "items": False,
            "centers": False,
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


def parse_centers(page_texts: list[str]) -> list[dict[str, Any]]:
    center_text = next(
        (text for text in page_texts if "临床试验机构" in text and "机构代号" in text),
        "",
    )
    if not center_text:
        return []
    lines = center_text.splitlines()
    centers: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if re.match(r"^\s*20\d{7}\s*$", line):
            continue
        match = re.match(r"^\s*(\d{2})\s*(.*)$", line)
        if match is None:
            continue
        code = match.group(1)
        inline = match.group(2).strip()
        prev_line = lines[index - 1].strip() if index > 0 else ""
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        filing_no = _first_match(r"(20\d{7})", "\n".join([prev_line, inline, next_line]))
        investigator = extract_investigator(inline)
        inline_name = inline
        if investigator and investigator in inline_name:
            inline_name = inline_name.rsplit(investigator, 1)[0].strip()
        inline_name = re.sub(r"20\d{7}", "", inline_name).strip()
        name_parts = []
        prev_name = strip_filing_label(prev_line)
        next_name = strip_filing_label(re.sub(r"20\d{7}", "", next_line).strip())
        if inline_name and len(inline_name) > 4:
            name_parts.append(inline_name)
        else:
            if prev_name:
                name_parts.append(prev_name)
            if next_name:
                name_parts.append(next_name)
        center_name = "".join(name_parts).strip()
        if not center_name:
            continue
        centers.append(
            {
                "code": code,
                "name": center_name,
                "filing_no": filing_no,
                "principal_investigator": investigator,
                "enabled": True,
            }
        )
    return centers


def extract_investigator(value: str) -> str | None:
    parts = re.split(r"\s{2,}", value.strip())
    if len(parts) >= 2 and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", parts[-1]):
        return parts[-1]
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value.strip()):
        return value.strip()
    return None


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

    result = {
        "created_stages": 0,
        "updated_stages": 0,
        "created_templates": 0,
        "updated_templates": 0,
        "created_centers": 0,
        "updated_centers": 0,
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
    return result


def center_description(center_data: dict[str, Any]) -> str | None:
    filing_no = str(center_data.get("filing_no") or "").strip()
    return f"备案号：{filing_no}" if filing_no else None


def _first_match(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value)
    return match.group(1).strip() if match else None
