import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SchemaField(BaseModel):
    key: str
    query: str | None = None  # Query/prompt to extract this field from OCR text
    description: str | None = None
    value_type: str = "string"
    required: bool = False
    options: list[str] = Field(default_factory=list)


class SchemaCreate(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None
    fields: list[SchemaField]


class SchemaRead(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None = None
    description: str | None = None
    fields: list[SchemaField]
    created_at: datetime
    updated_at: datetime
    version: int

    class Config:
        from_attributes = True


class SchemaList(BaseModel):
    items: list[SchemaRead]


class SchemaApplyRequest(BaseModel):
    schema_id: uuid.UUID
    overrides: dict[str, Any] = Field(default_factory=dict)
