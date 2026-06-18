from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SnapshotType = Literal["draft_snapshot", "released_snapshot"]


class SubjectSnapshotRead(BaseModel):
    id: int
    project_id: int
    center_id: int
    subject_id: int
    screening_no_snapshot: str
    schema_version: str
    snapshot_version: int
    snapshot_type: SnapshotType
    status: str
    storage_path: str | None = None
    file_hash: str | None = None
    file_size: int | None = None
    generated_by: int | None = None
    generated_at: datetime | None = None
    locked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubjectSnapshotHistoryItem(SubjectSnapshotRead):
    generated_by_name: str | None = None


class SnapshotGenerateResponse(BaseModel):
    snapshot: SubjectSnapshotRead
    check_run_id: str
    storage_path: str
    file_hash: str
    file_size: int
