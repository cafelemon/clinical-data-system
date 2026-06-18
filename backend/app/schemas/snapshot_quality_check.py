from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SnapshotCheckStatus = Literal["pass", "warn", "fail", "not_supported"]


class SnapshotQualityCheckRead(BaseModel):
    id: int
    check_run_id: str
    project_id: int
    center_id: int
    subject_id: int
    snapshot_id: int | None = None
    schema_version: str
    snapshot_type: str
    check_code: str
    check_status: SnapshotCheckStatus
    blocking: bool
    message: str
    payload_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SnapshotPrecheckResponse(BaseModel):
    subject_id: int
    snapshot_type: str
    schema_version: str
    check_run_id: str
    eligible: bool
    blocking_failure_count: int
    warning_count: int
    checks: list[SnapshotQualityCheckRead]
