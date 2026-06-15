import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.ocr_client import OcrClientError, PaddleOcrClient
from app.services.pdf_packets import (
    PdfPacketError,
    extract_text_with_pdftotext,
    extract_text_with_pypdf,
)


@dataclass(frozen=True)
class ProtocolTextLine:
    page_no: int
    text: str
    source: str
    confidence: float | None = None
    box: dict[str, float] | None = None


@dataclass(frozen=True)
class ProtocolTextExtraction:
    source: str
    page_texts: list[str]
    lines: list[ProtocolTextLine] = field(default_factory=list)


def extract_protocol_text(path: Path, page_count: int) -> ProtocolTextExtraction:
    pypdf_texts = extract_text_with_pypdf(path, page_count)
    if pypdf_texts is not None and any(text.strip() for text in pypdf_texts):
        return ProtocolTextExtraction(
            source="pypdf",
            page_texts=pypdf_texts,
            lines=lines_from_page_texts(pypdf_texts, "pypdf"),
        )

    layout_texts = extract_text_with_pdftotext(path, page_count)
    if layout_texts is not None and any(text.strip() for text in layout_texts):
        return ProtocolTextExtraction(
            source="pdftotext",
            page_texts=layout_texts,
            lines=lines_from_page_texts(layout_texts, "pdftotext"),
        )

    ocr_extraction = extract_text_with_ocr_api(path, page_count)
    if any(text.strip() for text in ocr_extraction.page_texts):
        return ocr_extraction

    command_texts = extract_text_with_ocr_command(path, page_count)
    if command_texts is not None and any(text.strip() for text in command_texts):
        return ProtocolTextExtraction(
            source="ocr_command",
            page_texts=command_texts,
            lines=lines_from_page_texts(command_texts, "ocr_command"),
        )

    return ProtocolTextExtraction(source="empty", page_texts=["" for _ in range(page_count)])


def lines_from_page_texts(page_texts: list[str], source: str) -> list[ProtocolTextLine]:
    lines: list[ProtocolTextLine] = []
    for page_index, page_text in enumerate(page_texts, start=1):
        for line in page_text.splitlines():
            if line.strip():
                lines.append(ProtocolTextLine(page_no=page_index, text=line, source=source))
    return lines


def extract_text_with_ocr_api(path: Path, page_count: int) -> ProtocolTextExtraction:
    if not settings.pdf_packet_ocr_api_url:
        return ProtocolTextExtraction(source="ocr_api", page_texts=["" for _ in range(page_count)])
    try:
        client = PaddleOcrClient(
            settings.pdf_packet_ocr_api_url,
            timeout_seconds=settings.pdf_packet_ocr_timeout_seconds,
        )
        payload = client.ocr_pdf_payload(
            path,
            page_count=page_count,
            dpi=settings.pdf_packet_ocr_dpi,
            include_blocks=True,
        )
    except OcrClientError as exc:
        raise PdfPacketError(f"OCR API failed: {exc}") from exc

    pages = payload.get("pages")
    if not isinstance(pages, list):
        return ProtocolTextExtraction(source="ocr_api", page_texts=["" for _ in range(page_count)])

    page_texts = ["" for _ in range(page_count)]
    lines: list[ProtocolTextLine] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_no = page.get("page_no")
        if not isinstance(page_no, int) or page_no < 1 or page_no > page_count:
            continue
        text = page.get("text")
        if isinstance(text, str):
            page_texts[page_no - 1] = text
        blocks = page.get("blocks")
        if isinstance(blocks, list):
            lines.extend(block_lines(page_no, blocks))
        elif isinstance(text, str):
            lines.extend(
                ProtocolTextLine(page_no=page_no, text=line, source="ocr_api")
                for line in text.splitlines()
                if line.strip()
            )

    return ProtocolTextExtraction(source="ocr_api", page_texts=page_texts, lines=lines)


def block_lines(page_no: int, blocks: list[Any]) -> list[ProtocolTextLine]:
    result: list[ProtocolTextLine] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        confidence = block.get("confidence")
        result.append(
            ProtocolTextLine(
                page_no=page_no,
                text=text,
                source="ocr_api",
                confidence=confidence if isinstance(confidence, float | int) else None,
                box=block.get("box") if isinstance(block.get("box"), dict) else None,
            )
        )
    return result


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


def compact_line(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def has_pdftotext() -> bool:
    return shutil.which("pdftotext") is not None
