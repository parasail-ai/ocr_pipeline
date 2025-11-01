import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Document, DocumentSchema, SchemaDefinition
from app.db.session import get_db
from app.models.document import (
    DocumentApplySchemaRequest,
    DocumentList,
    DocumentOcrResultRead,
    DocumentRead,
    DocumentSchemaAssignmentRead,
    DocumentClassificationRead,
    DocumentContentRead,
)
from app.services.blob_storage import BlobStorageService
from app.tasks.processing import process_document_task

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    model_name: str | None = Form(None),
    schema_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    blob_service = BlobStorageService()
    file_bytes = await file.read()

    blob_path, blob_url = blob_service.upload_document(
        content=file_bytes,
        filename=file.filename,
        content_type=file.content_type,
    )

    schema_uuid: uuid.UUID | None = None
    if schema_id:
        try:
            schema_uuid = uuid.UUID(schema_id)
        except ValueError as exc:  # pragma: no cover - validation guard
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid schema identifier") from exc

        schema_exists = await db.scalar(select(SchemaDefinition.id).where(SchemaDefinition.id == schema_uuid))
        if not schema_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")

    document = Document(
        original_filename=file.filename,
        selected_model=model_name,
        selected_schema_id=schema_uuid,
        blob_path=blob_path,
        blob_url=blob_url,
        details={"content_type": file.content_type},
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(
        process_document_task,
        document.id,
        blob_path,
        file.content_type,
        model_name,
        schema_uuid,
    )

    return DocumentRead.model_validate(document)


@router.get("", response_model=DocumentList)
async def list_documents(db: AsyncSession = Depends(get_db)) -> DocumentList:
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.selected_schema),
            selectinload(Document.ocr_results),
            selectinload(Document.schemas).selectinload(DocumentSchema.schema),
            selectinload(Document.contents),
            selectinload(Document.classifications),
        )
        .order_by(Document.uploaded_at.desc())
    )
    documents = list(result.scalars().all())
    return DocumentList(items=[DocumentRead.model_validate(item) for item in documents])


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> DocumentRead:
    document = await db.get(
        Document,
        document_id,
        options=(
            selectinload(Document.selected_schema),
            selectinload(Document.ocr_results),
            selectinload(Document.schemas).selectinload(DocumentSchema.schema),
            selectinload(Document.contents),
            selectinload(Document.classifications),
        ),
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/ocr-results", response_model=list[DocumentOcrResultRead])
async def list_ocr_results(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[DocumentOcrResultRead]:
    document = await db.get(Document, document_id, options=(selectinload(Document.ocr_results),))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return [DocumentOcrResultRead.model_validate(item) for item in document.ocr_results]


@router.get("/{document_id}/contents", response_model=list[DocumentContentRead])
async def list_document_contents(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[DocumentContentRead]:
    document = await db.get(Document, document_id, options=(selectinload(Document.contents),))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return [DocumentContentRead.model_validate(item) for item in document.contents]


@router.get("/{document_id}/classifications", response_model=list[DocumentClassificationRead])
async def list_document_classifications(
    document_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[DocumentClassificationRead]:
    document = await db.get(Document, document_id, options=(selectinload(Document.classifications),))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return [DocumentClassificationRead.model_validate(item) for item in document.classifications]


@router.post("/{document_id}/schemas", response_model=DocumentSchemaAssignmentRead)
async def apply_schema(
    document_id: uuid.UUID,
    payload: DocumentApplySchemaRequest,
    db: AsyncSession = Depends(get_db),
) -> DocumentSchemaAssignmentRead:
    document = await db.get(
        Document,
        document_id,
        options=(selectinload(Document.schemas).selectinload(DocumentSchema.schema),),
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    schema = await db.get(SchemaDefinition, payload.schema_id)
    if not schema:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")

    assignment = DocumentSchema(document=document, schema=schema, extracted_values=payload.values)
    db.add(assignment)
    document.selected_schema_id = schema.id
    if schema.category and not document.detected_type:
        document.detected_type = schema.category
        document.detected_confidence = 1.0
    await db.flush()
    await db.commit()
    await db.refresh(assignment, attribute_names=["schema"])
    await db.refresh(document, attribute_names=["selected_schema_id"])

    return DocumentSchemaAssignmentRead.model_validate(assignment)
