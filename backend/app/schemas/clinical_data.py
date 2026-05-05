from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import StageRead


class SubjectBase(BaseModel):
    project_id: int
    center_id: int
    screening_no: str = Field(min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=30)
    age: int | None = Field(default=None, ge=0, le=130)
    enrolled_at: date | None = None
    review_status: str = Field(default="unreviewed", max_length=30)
    data_status: str = Field(default="incomplete", max_length=30)


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    center_id: int | None = None
    screening_no: str | None = Field(default=None, min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=30)
    age: int | None = Field(default=None, ge=0, le=130)
    enrolled_at: date | None = None
    review_status: str | None = Field(default=None, max_length=30)
    data_status: str | None = Field(default=None, max_length=30)


class SubjectRead(SubjectBase):
    id: int
    added_by: int | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectSectionRead(BaseModel):
    id: int
    project_id: int
    subject_id: int
    section_code: str
    name: str
    visit_name: str | None = None
    time_window: str | None = None
    sort_order: int
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SubjectItemRead(BaseModel):
    id: int
    subject_id: int
    section_id: int
    item_name: str
    item_code: str
    sort_order: int
    required: bool
    upload_status: str
    review_status: str
    remark: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectItemUpdate(BaseModel):
    upload_status: str | None = Field(default=None, max_length=30)
    review_status: str | None = Field(default=None, max_length=30)
    remark: str | None = None


class StageFileRead(BaseModel):
    id: int
    project_id: int
    center_id: int
    stage_id: int
    stage_template_id: int | None = None
    file_name: str
    file_type: str | None = None
    upload_status: str
    review_status: str
    added_by: int | None = None
    added_at: datetime
    remark: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalDatasetRead(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    stages: list[StageRead] = Field(default_factory=list)
    startup_files: list[StageFileRead] = Field(default_factory=list)
    subjects: list[SubjectRead] = Field(default_factory=list)
    closeout_files: list[StageFileRead] = Field(default_factory=list)
    stage_file_count: int = 0
    subject_count: int = 0
