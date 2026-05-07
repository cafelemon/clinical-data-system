from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.file_asset import FileRead


class PdfPacketRead(BaseModel):
    id: int
    packet_id: str
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
    subject_id: int
    screening_no: str
    filename_screening_no: str | None = None
    page_count: int
    status: str
    error_message: str | None = None
    analysis_summary: str | None = None
    uploaded_by: int | None = None
    uploaded_at: datetime
    updated_at: datetime
    segment_count: int | None = None

    model_config = ConfigDict(from_attributes=True)


class PdfPacketSegmentRead(BaseModel):
    id: int
    packet_id: int
    page_start: int
    page_end: int
    detected_name: str | None = None
    detected_code: str | None = None
    confidence: float
    suggested_subject_item_id: int | None = None
    subject_item_id: int | None = None
    file_asset_id: int | None = None
    status: str
    ocr_text: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PdfPacketSegmentCreate(BaseModel):
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    detected_name: str | None = Field(default=None, max_length=150)
    detected_code: str | None = Field(default=None, max_length=100)
    confidence: float = Field(default=0, ge=0, le=1)
    suggested_subject_item_id: int | None = None
    subject_item_id: int | None = None
    ocr_text: str | None = None

    @model_validator(mode="after")
    def validate_page_range(self) -> "PdfPacketSegmentCreate":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class PdfPacketSegmentUpdate(BaseModel):
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    detected_name: str | None = Field(default=None, max_length=150)
    detected_code: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    suggested_subject_item_id: int | None = None
    subject_item_id: int | None = None
    status: str | None = Field(default=None, max_length=30)
    ocr_text: str | None = None


class PdfPacketSegmentUpload(BaseModel):
    subject_item_id: int


class PdfPacketSegmentUploadRead(BaseModel):
    segment: PdfPacketSegmentRead
    file: FileRead
