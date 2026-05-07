from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewActionRequest(BaseModel):
    target_type: str = Field(pattern="^(stage_file|subject_item)$")
    target_id: int
    comment: str | None = None

    @model_validator(mode="after")
    def trim_comment(self) -> "ReviewActionRequest":
        if self.comment is not None:
            self.comment = self.comment.strip() or None
        return self


class ReviewRecordRead(BaseModel):
    id: int
    target_type: str
    target_id: int
    action: str
    review_status: str
    reviewer_id: int | None = None
    comment: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewBatchApproveTarget(BaseModel):
    target_type: str = Field(pattern="^(stage_file|subject_item)$")
    target_id: int


class ReviewBatchApproveRequest(BaseModel):
    targets: list[ReviewBatchApproveTarget] = Field(min_length=1, max_length=200)


class ReviewBatchApproveResultItem(BaseModel):
    target_type: str
    target_id: int
    status: str
    message: str
    submitted: bool = False
    approved: bool = False


class ReviewBatchApproveRead(BaseModel):
    approved_count: int
    skipped_count: int
    results: list[ReviewBatchApproveResultItem]


class CompletenessRecalculateRequest(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    subject_id: int | None = None


class CompletenessStatusCount(BaseModel):
    complete: int = 0
    checking: int = 0
    incomplete: int = 0


class StageCompletenessRead(BaseModel):
    stage_id: int
    stage_name: str
    status: str
    required_count: int
    complete_count: int
    checking_count: int
    incomplete_count: int


class CenterCompletenessRead(BaseModel):
    center_id: int
    center_name: str
    status: str
    stage_files: CompletenessStatusCount
    subjects: CompletenessStatusCount


class CompletenessSummaryRead(BaseModel):
    project_id: int | None = None
    center_id: int | None = None
    status: str
    stage_files: CompletenessStatusCount
    subjects: CompletenessStatusCount
    centers: list[CenterCompletenessRead]
    stages: list[StageCompletenessRead]
