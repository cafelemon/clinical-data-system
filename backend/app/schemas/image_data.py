from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ImageType = Literal["raw", "enhanced", "report"]


class SubjectImageRecordRead(BaseModel):
    id: int
    project_id: int
    center_id: int
    subject_id: int
    image_type: ImageType
    screening_no_snapshot: str
    upload_status: str
    original_name: str | None = None
    stored_name: str | None = None
    file_ext: str | None = None
    mime_type: str | None = None
    file_size: int
    file_hash: str | None = None
    storage_path: str | None = None
    extracted_dir: str | None = None
    version: int
    image_count: int
    image_total_size: int
    image_extensions_json: dict | None = None
    parse_warning: str | None = None
    source_raw_record_id: int | None = None
    uploaded_by: int | None = None
    uploaded_at: datetime | None = None
    copied_by: int | None = None
    copied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectImageRowRead(BaseModel):
    subject_id: int
    project_id: int
    center_id: int
    screening_no: str
    subject_arm: str | None = None
    gender: str | None = None
    age: int | None = None
    record: SubjectImageRecordRead
    raw_record: SubjectImageRecordRead | None = None


class SubjectImageUploadRead(BaseModel):
    record: SubjectImageRecordRead
