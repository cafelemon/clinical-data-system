from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ImageEvidenceType = Literal[
    "raw_package",
    "enhanced_package",
    "report_package",
    "report_image",
    "marked_image",
    "landmark_image",
]
ImageEvidenceMatchStatus = Literal[
    "resolved",
    "approx_matched",
    "unresolved",
    "not_supported",
]


class ImageEvidenceIndexRead(BaseModel):
    id: int
    project_id: int
    center_id: int
    subject_id: int
    subject_image_record_id: int
    evidence_type: ImageEvidenceType
    evidence_source: str | None = None
    relative_path: str | None = None
    match_status: ImageEvidenceMatchStatus | None = None
    file_hash: str | None = None
    file_size: int | None = None
    gastrointestinal_location: str | None = None
    payload_json: dict[str, Any] | None = None
    indexed_by: int | None = None
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
