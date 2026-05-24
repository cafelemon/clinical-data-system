from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.review import CompletenessStatusCount


class DashboardProjectSummaryRead(BaseModel):
    project_id: int
    project_name: str
    completed_subject_count: int
    visible_center_count: int
    project_days: int
    average_days_per_subject: float
    median_days_per_subject: float
    subject_count: int


class DashboardCenterRead(BaseModel):
    center_id: int
    center_name: str
    subject_count: int
    completed_subject_count: int
    completion_rate: float
    completeness_status: str
    pending_review_count: int
    rejected_review_count: int


class DashboardTrendPointRead(BaseModel):
    period: str
    completed_count: int


class DashboardReviewStatusRead(BaseModel):
    unreviewed: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0


class DashboardCompletenessRead(BaseModel):
    stage_files: CompletenessStatusCount
    subjects: CompletenessStatusCount


class DashboardV31ScopedBase(BaseModel):
    project_id: int
    center_id: int | None = None


class DashboardV31RecordRead(DashboardV31ScopedBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardMilestoneBase(DashboardV31ScopedBase):
    milestone_name: str = Field(min_length=1, max_length=120)
    planned_date: date | None = None
    actual_date: date | None = None
    status: str = Field(default="not_started", max_length=30)
    owner: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class DashboardMilestoneCreate(DashboardMilestoneBase):
    pass


class DashboardMilestoneUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    milestone_name: str | None = Field(default=None, min_length=1, max_length=120)
    planned_date: date | None = None
    actual_date: date | None = None
    status: str | None = Field(default=None, max_length=30)
    owner: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class DashboardMilestoneRead(DashboardMilestoneBase, DashboardV31RecordRead):
    pass


class DashboardEnrollmentPlanBase(DashboardV31ScopedBase):
    contract_count: int | None = None
    screening_count: int | None = None
    current_enrolled_count: int | None = None
    positive_enrolled_count: int | None = None
    identified_polyp_count: int | None = None
    unidentified_polyp_count: int | None = None
    whole_colon_completed_count: int | None = None
    whole_colon_incomplete_count: int | None = None
    sigmoid_unidentified_count: int | None = None
    next_week_plan_count: int | None = None
    eligible_count: int | None = None
    enrollment_arrangement: str | None = None
    notes: str | None = None


class DashboardEnrollmentPlanCreate(DashboardEnrollmentPlanBase):
    pass


class DashboardEnrollmentPlanUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    contract_count: int | None = None
    screening_count: int | None = None
    current_enrolled_count: int | None = None
    positive_enrolled_count: int | None = None
    identified_polyp_count: int | None = None
    unidentified_polyp_count: int | None = None
    whole_colon_completed_count: int | None = None
    whole_colon_incomplete_count: int | None = None
    sigmoid_unidentified_count: int | None = None
    next_week_plan_count: int | None = None
    eligible_count: int | None = None
    enrollment_arrangement: str | None = None
    notes: str | None = None


class DashboardEnrollmentPlanRead(DashboardEnrollmentPlanBase, DashboardV31RecordRead):
    pass


class DashboardSubjectOverviewBase(DashboardV31ScopedBase):
    screening_no: str = Field(min_length=1, max_length=80)
    informed_at: datetime | None = None
    swallow_time: datetime | None = None
    swallow_time_2: datetime | None = None
    gastric_transit_time: str | None = Field(default=None, max_length=80)
    colon_entry_duration: str | None = Field(default=None, max_length=80)
    capsule_batch_no: str | None = Field(default=None, max_length=80)
    capsule_serial_no: str | None = Field(default=None, max_length=80)
    recorder_batch_no: str | None = Field(default=None, max_length=80)
    recorder_serial_no: str | None = Field(default=None, max_length=80)
    image_count: int | None = None
    video_duration: str | None = Field(default=None, max_length=80)
    colon_work_duration: str | None = Field(default=None, max_length=80)
    condition_description: str | None = None
    capsule_excreted_at: datetime | None = None


class DashboardSubjectOverviewCreate(DashboardSubjectOverviewBase):
    pass


class DashboardSubjectOverviewUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    screening_no: str | None = Field(default=None, min_length=1, max_length=80)
    informed_at: datetime | None = None
    swallow_time: datetime | None = None
    swallow_time_2: datetime | None = None
    gastric_transit_time: str | None = Field(default=None, max_length=80)
    colon_entry_duration: str | None = Field(default=None, max_length=80)
    capsule_batch_no: str | None = Field(default=None, max_length=80)
    capsule_serial_no: str | None = Field(default=None, max_length=80)
    recorder_batch_no: str | None = Field(default=None, max_length=80)
    recorder_serial_no: str | None = Field(default=None, max_length=80)
    image_count: int | None = None
    video_duration: str | None = Field(default=None, max_length=80)
    colon_work_duration: str | None = Field(default=None, max_length=80)
    condition_description: str | None = None
    capsule_excreted_at: datetime | None = None


class DashboardSubjectOverviewRead(DashboardSubjectOverviewBase, DashboardV31RecordRead):
    pass


class DashboardDeviceHandoverBase(DashboardV31ScopedBase):
    device_name: str = Field(min_length=1, max_length=120)
    batch_no: str | None = Field(default=None, max_length=80)
    device_serial_no: str = Field(min_length=1, max_length=120)
    handed_over_at: date | None = None
    returned_at: date | None = None
    handover_status: str = Field(default="in_use", max_length=30)
    handover_person: str | None = Field(default=None, max_length=100)
    receiver: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class DashboardDeviceHandoverCreate(DashboardDeviceHandoverBase):
    pass


class DashboardDeviceHandoverUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    device_name: str | None = Field(default=None, min_length=1, max_length=120)
    batch_no: str | None = Field(default=None, max_length=80)
    device_serial_no: str | None = Field(default=None, min_length=1, max_length=120)
    handed_over_at: date | None = None
    returned_at: date | None = None
    handover_status: str | None = Field(default=None, max_length=30)
    handover_person: str | None = Field(default=None, max_length=100)
    receiver: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class DashboardDeviceHandoverRead(DashboardDeviceHandoverBase, DashboardV31RecordRead):
    pass


class DashboardSubjectResultBase(DashboardV31ScopedBase):
    reading_no: str | None = Field(default=None, max_length=80)
    screening_no: str = Field(min_length=1, max_length=80)
    enrollment_no: str | None = Field(default=None, max_length=80)
    whole_colon_completed: str | None = Field(default=None, max_length=30)
    is_positive: str | None = Field(default=None, max_length=30)
    max_polyp_size: str | None = Field(default=None, max_length=80)
    capsule_polyp_count: int | None = None
    colonoscopy_polyp_count: int | None = None
    matched_polyp_count: int | None = None
    is_fully_matched: str | None = Field(default=None, max_length=30)
    max_polyp_matched: str | None = Field(default=None, max_length=30)
    other_diagnosis: str | None = None
    result_notes: str | None = None


class DashboardSubjectResultCreate(DashboardSubjectResultBase):
    pass


class DashboardSubjectResultUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    reading_no: str | None = Field(default=None, max_length=80)
    screening_no: str | None = Field(default=None, min_length=1, max_length=80)
    enrollment_no: str | None = Field(default=None, max_length=80)
    whole_colon_completed: str | None = Field(default=None, max_length=30)
    is_positive: str | None = Field(default=None, max_length=30)
    max_polyp_size: str | None = Field(default=None, max_length=80)
    capsule_polyp_count: int | None = None
    colonoscopy_polyp_count: int | None = None
    matched_polyp_count: int | None = None
    is_fully_matched: str | None = Field(default=None, max_length=30)
    max_polyp_matched: str | None = Field(default=None, max_length=30)
    other_diagnosis: str | None = None
    result_notes: str | None = None


class DashboardSubjectResultRead(DashboardSubjectResultBase, DashboardV31RecordRead):
    pass


class DashboardClinicalEventBase(DashboardV31ScopedBase):
    event_name: str = Field(min_length=1, max_length=160)
    occurred_at: datetime | None = None
    event_type: str | None = Field(default=None, max_length=80)
    severity: str | None = Field(default=None, max_length=30)
    status: str = Field(default="open", max_length=30)
    notes: str | None = None


class DashboardClinicalEventCreate(DashboardClinicalEventBase):
    pass


class DashboardClinicalEventUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    event_name: str | None = Field(default=None, min_length=1, max_length=160)
    occurred_at: datetime | None = None
    event_type: str | None = Field(default=None, max_length=80)
    severity: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None, max_length=30)
    notes: str | None = None


class DashboardClinicalEventRead(DashboardClinicalEventBase, DashboardV31RecordRead):
    pass


class DashboardDeviceIssueBase(DashboardV31ScopedBase):
    problem_time: datetime | None = None
    problem_description: str = Field(min_length=1)
    is_resolved: str = Field(default="no", max_length=30)
    problem_type: str | None = Field(default=None, max_length=80)
    center_institution: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class DashboardDeviceIssueCreate(DashboardDeviceIssueBase):
    pass


class DashboardDeviceIssueUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    problem_time: datetime | None = None
    problem_description: str | None = Field(default=None, min_length=1)
    is_resolved: str | None = Field(default=None, max_length=30)
    problem_type: str | None = Field(default=None, max_length=80)
    center_institution: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class DashboardDeviceIssueRead(DashboardDeviceIssueBase, DashboardV31RecordRead):
    pass


class DashboardImportantTaskBase(DashboardV31ScopedBase):
    title: str = Field(min_length=1, max_length=180)
    owner: str | None = Field(default=None, max_length=100)
    planned_due_date: date | None = None
    actual_completed_date: date | None = None
    status: str = Field(default="open", max_length=30)
    importance: str = Field(default="important", max_length=30)
    urgency: str = Field(default="urgent", max_length=30)
    notes: str | None = None


class DashboardImportantTaskCreate(DashboardImportantTaskBase):
    pass


class DashboardImportantTaskUpdate(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=180)
    owner: str | None = Field(default=None, max_length=100)
    planned_due_date: date | None = None
    actual_completed_date: date | None = None
    status: str | None = Field(default=None, max_length=30)
    importance: str | None = Field(default=None, max_length=30)
    urgency: str | None = Field(default=None, max_length=30)
    notes: str | None = None


class DashboardImportantTaskRead(DashboardImportantTaskBase, DashboardV31RecordRead):
    pass


class DashboardV31WarningRead(BaseModel):
    source: str
    id: int
    title: str
    center_id: int | None = None
    planned_date: date
    status: str
    warning_level: str


class DashboardV31OverviewRead(BaseModel):
    project_id: int
    counts: dict[str, int]
    enrollment: dict[str, int]
    important_task_status: dict[str, int]
    deviation_warnings: list[DashboardV31WarningRead]


class DashboardV31ImportErrorRead(BaseModel):
    row: int
    field: str
    message: str


class DashboardV31ImportResultRead(BaseModel):
    total_rows: int
    created_count: int
    updated_count: int
    errors: list[DashboardV31ImportErrorRead] = []
    rows: list[dict[str, Any]] = []
