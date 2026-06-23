from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class ReportImageIndexResponse(BaseModel):
    record_id: int
    report_version: int
    index_status: Literal["indexed", "empty", "not_supported", "failed"]
    report_package_evidence_id: int
    indexed_image_count: int
    duplicate_count: int
    warning: str | None = None
    evidence: list[ImageEvidenceIndexRead]


LandmarkIndexStatus = Literal[
    "waiting_for_assets",
    "indexed",
    "partial",
    "unresolved",
    "not_supported",
    "failed",
]


class LandmarkIndexCounts(BaseModel):
    resolved: int = 0
    approx_matched: int = 0
    unresolved: int = 0
    marked: int = 0


class LandmarkIndexResponse(BaseModel):
    report_record_id: int
    raw_record_id: int | None = None
    enhanced_record_id: int | None = None
    index_status: LandmarkIndexStatus
    counts: LandmarkIndexCounts = Field(default_factory=LandmarkIndexCounts)
    warning: str | None = None
    evidence: list[ImageEvidenceIndexRead] = Field(default_factory=list)


class LandmarkConfirmRequest(BaseModel):
    candidate_key: str = Field(min_length=1)
