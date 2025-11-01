import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    blob_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    blob_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    schemas: Mapped[list["DocumentSchema"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    ocr_results: Mapped[list["DocumentOcrResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="desc(DocumentOcrResult.created_at)"
    )


class SchemaDefinition(Base):
    __tablename__ = "schema_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document_schemas: Mapped[list["DocumentSchema"]] = relationship(back_populates="schema", cascade="all, delete-orphan")


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="ocr_results")
