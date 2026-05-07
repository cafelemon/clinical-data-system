from pydantic import BaseModel, Field


class ExcelImportErrorRead(BaseModel):
    row: int
    field: str
    message: str


class ExcelImportResultRead(BaseModel):
    total_rows: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    errors: list[ExcelImportErrorRead] = Field(default_factory=list)
