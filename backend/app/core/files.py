from dataclasses import dataclass
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
}

PREVIEW_MIME_PREFIXES = ("image/",)
PREVIEW_MIME_TYPES = {"application/pdf"}


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


def is_preview_supported(mime_type: str) -> bool:
    return mime_type in PREVIEW_MIME_TYPES or mime_type.startswith(PREVIEW_MIME_PREFIXES)


def ensure_relative_path(root: Path, storage_path: str) -> Path:
    candidate = (root / storage_path).resolve()
    resolved_root = root.resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError("invalid storage path")
    return candidate
