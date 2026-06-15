from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrialProtocolItemDraft(BaseModel):
    ordinal: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=150)
    required: bool = True
    enabled: bool = True


class TrialProtocolVisitDraft(BaseModel):
    ordinal: int = Field(ge=1)
    source_visit_code: str | None = Field(default=None, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    window: str | None = Field(default=None, max_length=120)
    enabled: bool = True
    items: list[TrialProtocolItemDraft] = Field(default_factory=list)


class TrialProtocolCenterDraft(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    filing_no: str | None = Field(default=None, max_length=80)
    principal_investigator: str | None = Field(default=None, max_length=100)
    enabled: bool = True
    confidence: float | None = Field(default=None, ge=0, le=1)
    requires_confirmation: bool = False
    confirmed: bool = True
    evidence: dict | None = None


class TrialProtocolDeactivateMissing(BaseModel):
    visits: bool = False
    items: bool = False
    centers: bool = False


class TrialProtocolDraft(BaseModel):
    visits: list[TrialProtocolVisitDraft] = Field(default_factory=list)
    centers: list[TrialProtocolCenterDraft] = Field(default_factory=list)
    deactivate_missing: TrialProtocolDeactivateMissing = Field(
        default_factory=TrialProtocolDeactivateMissing
    )
    parse_meta: dict | None = None


class TrialProtocolVersionRead(BaseModel):
    id: int
    project_id: int
    version_number: int
    original_name: str
    file_hash: str
    file_size: int
    page_count: int
    parsing_status: str
    protocol_no: str | None
    protocol_version: str | None
    protocol_date: str | None
    draft_json: TrialProtocolDraft
    apply_result_json: dict | None
    uploaded_by: int | None
    applied_by: int | None
    uploaded_at: datetime
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrialProtocolVersionSummary(BaseModel):
    id: int
    project_id: int
    version_number: int
    original_name: str
    file_hash: str
    file_size: int
    page_count: int
    parsing_status: str
    protocol_no: str | None
    protocol_version: str | None
    protocol_date: str | None
    apply_result_json: dict | None
    uploaded_at: datetime
    applied_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TrialProtocolApplyResult(BaseModel):
    version: TrialProtocolVersionRead
    result: dict
