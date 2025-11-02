import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Folder(Base):
    """Folders for organizing documents"""
    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)  # Full path for quick lookups
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # System folders like trash
    is_trash: Mapped[bool] = mapped_column(Boolean, default=False)  # Mark as trash folder
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent: Mapped["Folder | None"] = relationship("Folder", remote_side=[id], foreign_keys=[parent_id], back_populates="children")
    children: Mapped[list["Folder"]] = relationship("Folder", back_populates="parent", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="folder")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    selected_schema_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schema_definitions.id", ondelete="SET NULL"), nullable=True
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    blob_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    blob_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detected_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    detected_confidence: Mapped[float | None] = mapped_column(nullable=True)

    folder: Mapped["Folder | None"] = relationship(back_populates="documents")
    schemas: Mapped[list["DocumentSchema"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    ocr_results: Mapped[list["DocumentOcrResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentOcrResult.created_at)"
    )
    contents: Mapped[list["DocumentContent"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentContent.created_at)"
    )
    classifications: Mapped[list["DocumentClassification"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentClassification.created_at)"
    )
    extractions: Mapped[list["DocumentExtraction"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentExtraction.created_at)"
    )
    selected_schema: Mapped["SchemaDefinition | None"] = relationship("SchemaDefinition", foreign_keys=[selected_schema_id])
    metrics: Mapped[list["DocumentMetrics"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class SchemaDefinition(Base):
    __tablename__ = "schema_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_schema_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schema_definitions.id", ondelete="SET NULL"), nullable=True
    )

    document_schemas: Mapped[list["DocumentSchema"]] = relationship(back_populates="schema", cascade="all, delete-orphan")
    parent_schema: Mapped["SchemaDefinition | None"] = relationship("SchemaDefinition", remote_side=[id], foreign_keys=[parent_schema_id])


class DocumentSchema(Base):
    __tablename__ = "document_schemas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    schema_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schema_definitions.id", ondelete="CASCADE"), nullable=False
    )
    extracted_values: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="schemas")
    schema: Mapped[SchemaDefinition] = relationship(back_populates="document_schemas")


class DocumentContent(Base):
    __tablename__ = "document_contents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), default="ocr")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    fragment_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="contents")


class DocumentClassification(Base):
    __tablename__ = "document_classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    suggested_schema_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schema_definitions.id", ondelete="SET NULL"), nullable=True
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="classifications")
    suggested_schema: Mapped["SchemaDefinition | None"] = relationship("SchemaDefinition")


class DocumentOcrResult(Base):
    __tablename__ = "document_ocr_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="ocr_results")


class DocumentExtraction(Base):
    """Stores structured extractions including tables and line items"""
    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    extraction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'table', 'line_items', 'key_value'
    source: Mapped[str] = mapped_column(String(100), default="docling")  # 'docling', 'parasail', 'custom'
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="extractions")


class ApiProfile(Base):
    """User profiles for API access"""
    __tablename__ = "api_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class ApiKey(Base):
    """API keys for authentication"""
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_profiles.id", ondelete="CASCADE"), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # First few chars for identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped[ApiProfile] = relationship(back_populates="api_keys")


class OcrModel(Base):
    """Registry of available OCR models"""
    __tablename__ = "ocr_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)  # 'parasail', 'openai', 'custom'
    endpoint_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentMetrics(Base):
    """Track metrics for document processing."""
    
    __tablename__ = "document_metrics"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    
    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # OCR Model used
    ocr_model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    
    # Token usage
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Performance metrics
    ocr_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Document relationship
    document: Mapped["Document"] = relationship(back_populates="metrics")
