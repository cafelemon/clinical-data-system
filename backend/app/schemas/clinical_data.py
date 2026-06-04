from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.master_data import StageRead

SUBJECT_ARMS = {"experimental", "control"}


class SubjectBase(BaseModel):
    project_id: int
    center_id: int
    screening_no: str = Field(min_length=1, max_length=80)
    gender: str | None = Field(default=None, max_length=30)
    age: int | None = Field(default=None, ge=0, le=130)
    enrolled_at: date | None = None
    informed_at: datetime | None = None
    visit1_date: date | None = None
    visit2_date: date | None = None
    visit3_date: date | None = None
    visit4_date: date | None = None
    visit5_date: date | None = None
    review_status: str = Field(default="unreviewed", max_length=30)
    data_status: str = Field(default="incomplete", max_length=30)


class SubjectCreate(SubjectBase):
    subject_arm: str = Field(max_length=20)

    @field_validator("subject_arm")
    @classmethod
    def validate_subject_arm(cls, value: str) -> str:
        if value not in SUBJECT_ARMS:
            raise ValueError("invalid subject_arm")
        return value


class SubjectUpdate(BaseModel):
    center_id: int | None = None
    screening_no: str | None = Field(default=None, min_length=1, max_length=80)
    subject_arm: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=30)
    age: int | None = Field(default=None, ge=0, le=130)
    enrolled_at: date | None = None
    informed_at: datetime | None = None
    visit1_date: date | None = None
    visit2_date: date | None = None
    visit3_date: date | None = None
    visit4_date: date | None = None
    visit5_date: date | None = None
    review_status: str | None = Field(default=None, max_length=30)
    data_status: str | None = Field(default=None, max_length=30)

    @field_validator("subject_arm")
    @classmethod
    def validate_subject_arm(cls, value: str | None) -> str | None:
        if value is not None and value not in SUBJECT_ARMS:
            raise ValueError("invalid subject_arm")
        return value


class SubjectRead(SubjectBase):
    id: int
    subject_arm: str | None = None
    added_by: int | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectSectionRead(BaseModel):
    id: int
    project_id: int
    stage_id: int | None = None
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
    stage_template_id: int | None = None
    item_name: str
    item_code: str
    sort_order: int
    required: bool
    upload_status: str
    review_status: str
    remark: str | None = None
    uploaded_by: int | None = None
    uploaded_by_name: str | None = None
    uploaded_at: datetime | None = None
    reviewer_id: int | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    completeness_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectItemUpdate(BaseModel):
    upload_status: str | None = Field(default=None, max_length=30)
    review_status: str | None = Field(default=None, max_length=30)
    remark: str | None = None


class SubjectItemRemarkUpdate(BaseModel):
    remark: str | None = None


class SubjectItemRemarkRead(BaseModel):
    success: bool = True
    remark: str | None = None
    updated_at: datetime


class SubjectItemTimelineEntryRead(BaseModel):
    id: str
    occurred_at: datetime
    actor: str | None = None
    action: str
    action_label: str
    description: str | None = None
    file_id: int | None = None
    file_version: int | None = None
    task_id: int | None = None
    remark: str | None = None


class StageFileRead(BaseModel):
    id: int
    project_id: int
    center_id: int
    stage_id: int
    stage_template_id: int | None = None
    file_name: str
    file_type: str | None = None
    required: bool = True
    upload_status: str
    review_status: str
    added_by: int | None = None
    added_at: datetime
    uploaded_by: int | None = None
    uploaded_by_name: str | None = None
    uploaded_at: datetime | None = None
    reviewer_id: int | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    not_applicable: bool = False
    not_applicable_reason: str | None = None
    not_applicable_by: int | None = None
    not_applicable_by_name: str | None = None
    not_applicable_at: datetime | None = None
    completeness_status: str | None = None
    remark: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageFileApplicabilityUpdate(BaseModel):
    not_applicable: bool
    reason: str | None = Field(default=None, max_length=1000)


class StageFileGroupRead(BaseModel):
    stage: StageRead
    files: list[StageFileRead] = Field(default_factory=list)


class ClinicalPhaseRead(BaseModel):
    phase: StageRead
    child_stages: list[StageRead] = Field(default_factory=list)
    files: list[StageFileRead] = Field(default_factory=list)
    file_groups: list[StageFileGroupRead] = Field(default_factory=list)
    subjects: list[SubjectRead] = Field(default_factory=list)


class ClinicalSsuProgressBase(BaseModel):
    project_id: int
    center_id: int
    stage_code: str = Field(min_length=1, max_length=80)
    status: str = Field(default="not_started", max_length=30)
    submitted_at: date | None = None
    approved_at: date | None = None
    completed_at: date | None = None
    version_info: str | None = Field(default=None, max_length=120)
    file_checklist: str | None = None
    summary: str | None = None
    fee_detail: str | None = None
    notes: str | None = None


class ClinicalSsuProgressCreate(ClinicalSsuProgressBase):
    pass


class ClinicalSsuProgressUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=30)
    submitted_at: date | None = None
    approved_at: date | None = None
    completed_at: date | None = None
    version_info: str | None = Field(default=None, max_length=120)
    file_checklist: str | None = None
    summary: str | None = None
    fee_detail: str | None = None
    notes: str | None = None


class ClinicalSsuProgressRead(ClinicalSsuProgressBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalStatusCountRead(BaseModel):
    complete: int = 0
    checking: int = 0
    incomplete: int = 0


class ClinicalReviewSummaryRead(BaseModel):
    unreviewed: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class ClinicalSsuSummaryRead(BaseModel):
    total: int = 0
    completed: int = 0
    blocked: int = 0
    active: int = 0


class ClinicalOptionalFileSummaryRead(BaseModel):
    total: int = 0
    not_applicable: int = 0
    uploaded: int = 0


class ClinicalStageGroupSummaryRead(BaseModel):
    stage_id: int
    stage_code: str
    stage_name: str
    phase_code: str | None = None
    total: int = 0
    complete: int = 0
    checking: int = 0
    incomplete: int = 0


class ClinicalDatasetSummaryRead(BaseModel):
    stage_files: ClinicalStatusCountRead = Field(default_factory=ClinicalStatusCountRead)
    subjects: ClinicalStatusCountRead = Field(default_factory=ClinicalStatusCountRead)
    reviews: ClinicalReviewSummaryRead = Field(default_factory=ClinicalReviewSummaryRead)
    ssu: ClinicalSsuSummaryRead = Field(default_factory=ClinicalSsuSummaryRead)
    optional_files: ClinicalOptionalFileSummaryRead = Field(
        default_factory=ClinicalOptionalFileSummaryRead
    )
    stage_groups: list[ClinicalStageGroupSummaryRead] = Field(default_factory=list)


class ClinicalDatasetRead(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    stages: list[StageRead] = Field(default_factory=list)
    child_stages: list[StageRead] = Field(default_factory=list)
    phases: list[ClinicalPhaseRead] = Field(default_factory=list)
    startup_file_groups: list[StageFileGroupRead] = Field(default_factory=list)
    startup_files: list[StageFileRead] = Field(default_factory=list)
    ssu_progress: list[ClinicalSsuProgressRead] = Field(default_factory=list)
    trial_stages: list[StageRead] = Field(default_factory=list)
    trial_file_groups: list[StageFileGroupRead] = Field(default_factory=list)
    trial_files: list[StageFileRead] = Field(default_factory=list)
    subjects: list[SubjectRead] = Field(default_factory=list)
    closeout_file_groups: list[StageFileGroupRead] = Field(default_factory=list)
    closeout_files: list[StageFileRead] = Field(default_factory=list)
    stage_file_count: int = 0
    subject_count: int = 0
    summary: ClinicalDatasetSummaryRead = Field(default_factory=ClinicalDatasetSummaryRead)
