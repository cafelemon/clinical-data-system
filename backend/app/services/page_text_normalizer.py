from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedPageText:
    raw_text: str
    normalized_text: str
    lines: list[str]
    head_lines: list[str]
    tail_lines: list[str]


OCR_REPLACEMENTS = {
    "检査": "检查",
    "检 查": "检查",
    "评佔": "评估",
    "质景": "质量",
    "图象": "图像",
    "知情同意见": "知情同意书",
    "肠镜": "内镜",
    "囗": "口",
}

NOISE_LINE_PATTERNS = (
    re.compile(r"^\s*第\s*[\(（]?\s*\d+\s*[\)）]?\s*(?:页|贞)?\s*(?:/|共)?\s*\d*\s*$"),
    re.compile(r"^\s*page\s*\d+\s*(?:of\s*\d+)?\s*$", re.IGNORECASE),
    re.compile(r"(二维码|QR\s*code|请扫描|扫码|扫描水印)", re.IGNORECASE),
    re.compile(r"(扫描全能王|扫描App|3亿人都在用)"),
    re.compile(r"(仅供.*?使用|复印无效|打印时间|生成时间)"),
)


def normalize_line(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    for source, target in OCR_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = text.replace("：", ":")
    text = text.replace("；", ";")
    text = text.replace("，", ",")
    text = text.replace("。", ".")
    text = re.sub(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", r"\1-\2-\3", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    return text.strip()


def is_noise_line(value: str) -> bool:
    if not value:
        return True
    return any(pattern.search(value) for pattern in NOISE_LINE_PATTERNS)


def normalize_page_text(text: str) -> NormalizedPageText:
    raw_text = text or ""
    raw_lines = re.split(r"\r\n|\r|\n", raw_text)
    lines = [line for line in (normalize_line(raw_line) for raw_line in raw_lines) if line]
    signal_lines = [line for line in lines if not is_noise_line(line)]
    normalized_text = "\n".join(signal_lines)
    normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text).strip()
    final_lines = normalized_text.splitlines() if normalized_text else []
    return NormalizedPageText(
        raw_text=raw_text,
        normalized_text=normalized_text,
        lines=final_lines,
        head_lines=final_lines[:20],
        tail_lines=final_lines[-10:],
    )
