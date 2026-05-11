from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    description: str | None = None
    status: str = Field(default="active", max_length=30)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    status: str | None = Field(default=None, max_length=30)


class ProjectRead(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CenterBase(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    contact_person: str | None = Field(default=None, max_length=100)
    status: str = Field(default="active", max_length=30)
    description: str | None = None


class CenterCreate(CenterBase):
    pass


class CenterUpdate(BaseModel):
    project_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    contact_person: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=30)
    description: str | None = None


class CenterRead(CenterBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageBase(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50)
    parent_id: int | None = None
    phase_code: str | None = Field(default=None, max_length=30)
    option_code: str | None = Field(default=None, max_length=80)
    is_system: bool = False
    enabled: bool = True
    sort_order: int = 0
    description: str | None = None


class StageCreate(BaseModel):
    project_id: int
    phase_code: str | None = Field(default=None, max_length=30)
    parent_id: int | None = None
    option_code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    sort_order: int | None = None
    enabled: bool = True
    description: str | None = None


class StageUpdate(BaseModel):
    project_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    parent_id: int | None = None
    phase_code: str | None = Field(default=None, max_length=30)
    option_code: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    sort_order: int | None = None
    description: str | None = None


class StageRead(StageBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageTemplateBase(BaseModel):
    project_id: int
    stage_id: int
    item_name: str = Field(min_length=1, max_length=150)
    item_code: str = Field(min_length=1, max_length=80)
    template_scope: str = Field(default="center_file", max_length=30)
    required: bool = True
    sort_order: int = 0
    recognition_keywords: str | None = None
    description: str | None = None


class StageTemplateCreate(StageTemplateBase):
    pass


class StageTemplateUpdate(BaseModel):
    project_id: int | None = None
    stage_id: int | None = None
    item_name: str | None = Field(default=None, min_length=1, max_length=150)
    item_code: str | None = Field(default=None, min_length=1, max_length=80)
    template_scope: str | None = Field(default=None, max_length=30)
    required: bool | None = None
    sort_order: int | None = None
    recognition_keywords: str | None = None
    description: str | None = None


class StageTemplateRead(StageTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageTemplateKeywordGenerateRequest(BaseModel):
    subject_id: int
    mode: Literal["replace", "merge"] = "replace"
    max_keywords_per_item: int = Field(default=12, ge=3, le=30)


class StageTemplateKeywordGenerateItemRead(BaseModel):
    subject_item_id: int
    stage_template_id: int | None = None
    item_name: str
    item_code: str
    status: str
    keywords: list[str] = []
    keyword_count: int = 0
    ocr_page_count: int = 0
    message: str | None = None


class StageTemplateKeywordGenerateRead(BaseModel):
    subject_id: int
    updated_count: int
    skipped_count: int
    items: list[StageTemplateKeywordGenerateItemRead]


class StageOptionRead(BaseModel):
    phase_code: str
    option_code: str
    name: str
    sort_order: int
    default_enabled: bool = True
    description: str | None = None


class StageOptionGroupRead(BaseModel):
    phase_code: str
    phase_name: str
    sort_order: int
    options: list[StageOptionRead]


class DictionaryBase(BaseModel):
    dict_type: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=30)
    sort_order: int = 0
    enabled: bool = True


class DictionaryCreate(DictionaryBase):
    pass


class DictionaryUpdate(BaseModel):
    dict_type: str | None = Field(default=None, min_length=1, max_length=80)
    value: str | None = Field(default=None, min_length=1, max_length=80)
    label: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=30)
    sort_order: int | None = None
    enabled: bool | None = None


class DictionaryRead(DictionaryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
