import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: uuid.UUID
    original_filename: str
    selected_model: Optional[str]
    selected_schema_id: Optional[uuid.UUID]
    folder_id: Optional[uuid.UUID] = None
    blob_path: str
    blob_url: str
    uploaded_at: datetime
    status: str
    details: dict[str, Any]
    last_processed_at: Optional[datetime]
    detected_type: Optional[str]
    detected_confidence: Optional[float]
    selected_schema: Optional["SchemaRead"] = None
    ocr_results: list["DocumentOcrResultRead"] = []
    schemas: list["DocumentSchemaAssignmentRead"] = []
    contents: list["DocumentContentRead"] = []
    classifications: list["DocumentClassificationRead"] = []
    extractions: list["DocumentExtractionRead"] = []

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    items: list[DocumentRead]


class DocumentOcrResultRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    model_name: str
    raw_response: dict[str, Any]
    extracted_text: Optional[str]
    summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentContentRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    source: str
    text: str
    fragment_metadata: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentClassificationRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    label: str
    confidence: Optional[float]
    suggested_schema_id: Optional[uuid.UUID]
    rationale: Optional[str]
    extra: dict[str, Any]
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


class DocumentExtractionRead(BaseModel):
    """Response model for document extractions"""
    id: uuid.UUID
    document_id: uuid.UUID
    extraction_type: str
    source: str
    data: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentBase64Upload(BaseModel):
    """Request model for uploading a document via base64"""
    filename: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., description="Base64 encoded document content")
    content_type: Optional[str] = Field(None, description="MIME type of the document")
    model_name: Optional[str] = Field(None, description="OCR model to use")
    schema_id: Optional[uuid.UUID] = Field(None, description="Schema to apply")


# Forward references
from app.models.schema_definition import SchemaRead

DocumentRead.model_rebuild()
DocumentSchemaAssignmentRead.model_rebuild()
