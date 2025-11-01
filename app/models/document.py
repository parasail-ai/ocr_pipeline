import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    page_count: Optional[int] = None
    content_type: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DocumentCreate(BaseModel):
    filename: str
    content_type: Optional[str] = None
    selected_model: Optional[str] = None


class DocumentRead(BaseModel):
    id: uuid.UUID
    original_filename: str
    selected_model: Optional[str] = None
    blob_url: str
    status: str
    uploaded_at: datetime
    details: dict[str, Any]
    last_processed_at: Optional[datetime] = None
    ocr_results: list["DocumentOcrResultRead"] = Field(default_factory=list)
    schemas: list["DocumentSchemaAssignmentRead"] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    items: list[DocumentRead]


class DocumentOcrResultRead(BaseModel):
    id: uuid.UUID
    model_name: str
    summary: Optional[str] = None
    extracted_text: Optional[str] = None
    raw_response: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSchemaAssignmentRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    schema_id: uuid.UUID
    extracted_values: dict[str, Any]
    created_at: datetime
    schema: Optional["SchemaRead"] = None

    class Config:
        from_attributes = True


class DocumentApplySchemaRequest(BaseModel):
    schema_id: uuid.UUID
    values: dict[str, Any] = Field(default_factory=dict)


from app.models.schema_definition import SchemaRead


DocumentOcrResultRead.model_rebuild()
DocumentSchemaAssignmentRead.model_rebuild(_types_namespace={"SchemaRead": SchemaRead})
DocumentRead.model_rebuild(
    _types_namespace={
        "DocumentOcrResultRead": DocumentOcrResultRead,
        "DocumentSchemaAssignmentRead": DocumentSchemaAssignmentRead,
        "SchemaRead": SchemaRead,
    }
)
