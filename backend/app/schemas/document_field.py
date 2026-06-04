from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentExtractedFieldRead(BaseModel):
    id: int
    file_version_id: int | None = None
    pdf_packet_segment_id: int | None = None
    document_type: str
    field_key: str
    field_label: str
    value_type: str
    raw_value: str | None = None
    normalized_value: str | None = None
    source_page_no: int | None = None
    source_text: str | None = None
    confidence: float
    status: str
    manually_edited: bool
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentExtractedFieldUpdate(BaseModel):
    raw_value: str | None = Field(default=None, max_length=4000)
    normalized_value: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, max_length=30)
