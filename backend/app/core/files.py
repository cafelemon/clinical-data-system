from dataclasses import dataclass
import mimetypes
from pathlib import Path

FILE_CATEGORIES = {
    "clinical_document",
    "raw_pdf",
    "image_raw",
    "image_enhanced",
    "video_raw",
    "doctor_annotation",
    "metadata_json",
    "annotation_json",
    "report",
    "ssu_document",
}

CATEGORY_FOLDERS = {
    "clinical_document": "documents",
    "raw_pdf": "documents",
    "image_raw": "images_raw",
    "image_enhanced": "images_enhanced",
    "video_raw": "videos_raw",
    "doctor_annotation": "documents",
    "metadata_json": "annotations",
    "annotation_json": "annotations",
    "report": "documents",
    "ssu_document": "documents",
}

PREVIEW_MIME_PREFIXES = ("image/",)
PREVIEW_MIME_TYPES = {"application/pdf"}
GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


@dataclass(frozen=True)
class StoredUpload:
    original_name: str
    stored_name: str
    file_ext: str | None
    mime_type: str
    file_size: int
    file_hash: str
    storage_path: str


def safe_path_part(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value)
    cleaned = cleaned.strip("._")
    return cleaned or "unknown"


def normalize_mime_type(mime_type: str | None, filename: str) -> str:
    cleaned = (mime_type or "").split(";", 1)[0].strip().lower()
    guessed = mimetypes.guess_type(filename)[0]
    if cleaned in GENERIC_MIME_TYPES and guessed:
        return guessed
    return cleaned or guessed or "application/octet-stream"


def is_preview_supported(mime_type: str) -> bool:
    return mime_type in PREVIEW_MIME_TYPES or mime_type.startswith(PREVIEW_MIME_PREFIXES)


def preview_media_type(mime_type: str | None, filename: str) -> str | None:
    normalized = normalize_mime_type(mime_type, filename)
    if is_preview_supported(normalized):
        return normalized
    guessed = mimetypes.guess_type(filename)[0] or ""
    if is_preview_supported(guessed):
        return guessed
    return None


def ensure_relative_path(root: Path, storage_path: str) -> Path:
    candidate = (root / storage_path).resolve()
    resolved_root = root.resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError("invalid storage path")
    return candidate
