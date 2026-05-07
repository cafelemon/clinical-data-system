from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperationLogRead(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    target_type: str | None = None
    target_id: int | None = None
    project_id: int | None = None
    center_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    detail_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationLogListRead(BaseModel):
    items: list[OperationLogRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
