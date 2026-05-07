from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileRead(BaseModel):
    id: int
    file_id: str
    original_name: str
    stored_name: str
    file_ext: str | None = None
    mime_type: str
    file_size: int
    file_hash: str
    storage_path: str
    storage_type: str
    project_id: int
    center_id: int
    subject_id: int | None = None
    stage_id: int | None = None
    stage_file_id: int | None = None
    subject_item_id: int | None = None
    source_pdf_packet_id: int | None = None
    source_page_start: int | None = None
    source_page_end: int | None = None
    file_category: str
    version: int
    uploaded_by: int | None = None
    uploaded_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class FileVersionRead(BaseModel):
    id: int
    file_id: int
    version: int
    storage_path: str
    file_hash: str
    file_size: int
    mime_type: str
    original_name: str
    stored_name: str
    uploaded_by: int | None = None
    uploaded_at: datetime
    change_note: str | None = None

    model_config = ConfigDict(from_attributes=True)
