from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.file_asset import FileVersionRead

ISSUE_TYPES = {
    "missing_page",
    "wrong_page",
    "unclear_scan",
    "inconsistent_info",
    "missing_signature",
    "missing_stamp",
    "missing_date",
    "wrong_subject",
    "wrong_document",
    "other",
}
SEVERITIES = {"low", "medium", "high"}
ANNOTATION_STATUSES = {
    "open",
    "task_created",
    "submitted",
    "resolved",
    "rejected",
    "closed",
}
TASK_STATUSES = {"pending", "processing", "submitted", "returned", "closed", "cancelled"}


class PdfAnnotationBase(BaseModel):
    page_no: int = Field(ge=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    comment: str = Field(min_length=1, max_length=4000)
    issue_type: str
    severity: str

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, value: str) -> str:
        if value not in ISSUE_TYPES:
            raise ValueError("invalid issue_type")
        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError("invalid severity")
        return value

    @field_validator("height")
    @classmethod
    def validate_height(cls, value: float, info) -> float:
        data = info.data
        if "y" in data and data["y"] + value > 1:
            raise ValueError("annotation rectangle exceeds page height")
        return value

    @field_validator("width")
    @classmethod
    def validate_width(cls, value: float, info) -> float:
        data = info.data
        if "x" in data and data["x"] + value > 1:
            raise ValueError("annotation rectangle exceeds page width")
        return value


class PdfAnnotationCreate(PdfAnnotationBase):
    file_id: int
    file_version_id: int


class PdfAnnotationUpdate(BaseModel):
    page_no: int | None = Field(default=None, ge=1)
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    width: float | None = Field(default=None, gt=0, le=1)
    height: float | None = Field(default=None, gt=0, le=1)
    comment: str | None = Field(default=None, min_length=1, max_length=4000)
    issue_type: str | None = None
    severity: str | None = None
    status: str | None = None

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, value: str | None) -> str | None:
        if value is not None and value not in ISSUE_TYPES:
            raise ValueError("invalid issue_type")
        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str | None) -> str | None:
        if value is not None and value not in SEVERITIES:
            raise ValueError("invalid severity")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in ANNOTATION_STATUSES:
            raise ValueError("invalid status")
        return value


class PdfAnnotationRead(BaseModel):
    id: int
    file_id: int
    file_version_id: int
    project_id: int
    center_id: int
    subject_id: int | None = None
    subject_item_id: int | None = None
    page_no: int
    x: float
    y: float
    width: float
    height: float
    comment: str
    issue_type: str
    severity: str
    status: str
    created_by: int | None = None
    updated_by: int | None = None
    resolved_by: int | None = None
    deleted_by: int | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PdfReviewFileRead(BaseModel):
    file_id: int
    file_version_id: int
    file_name: str
    preview_url: str
    version: int
    mime_type: str
    status: str
    project_id: int
    center_id: int
    subject_id: int | None = None
    subject_item_id: int | None = None
    ssu_progress_id: int | None = None
    read_only: bool = False
    active_task_id: int | None = None
    active_task_status: str | None = None
    active_task_annotation_count: int = 0
    versions: list[FileVersionRead]
    annotations: list[PdfAnnotationRead]


class CorrectionTaskCreate(BaseModel):
    file_id: int
    file_version_id: int
    annotation_ids: list[int] = Field(min_length=1)
    assigned_to: int | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    due_date: date | None = None


class CorrectionTaskSubmitRead(BaseModel):
    task: "CorrectionTaskRead"


class CorrectionTaskReviewRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=4000)


class CorrectionTaskReturnRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


class CorrectionTaskRead(BaseModel):
    id: int
    task_no: str
    project_id: int
    center_id: int
    subject_id: int | None = None
    subject_item_id: int | None = None
    file_id: int
    source_file_version_id: int
    latest_file_version_id: int | None = None
    title: str
    description: str | None = None
    assigned_to: int | None = None
    created_by: int | None = None
    status: str
    due_date: date | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    closed_at: datetime | None = None
    submission_remark: str | None = None
    review_comment: str | None = None
    review_result: str | None = None
    created_at: datetime
    updated_at: datetime
    annotations: list[PdfAnnotationRead] = []

    model_config = ConfigDict(from_attributes=True)


CorrectionTaskSubmitRead.model_rebuild()
