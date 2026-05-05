from pydantic import BaseModel

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
