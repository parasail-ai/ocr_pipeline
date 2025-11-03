import base64
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import get_api_key_required
from app.db.models import Document, DocumentExtraction, DocumentMetrics, DocumentSchema, SchemaDefinition, Folder, User
from app.db.session import get_db
from app.services.auth import AuthService
from app.models.document import (
    DocumentApplySchemaRequest,
    DocumentBase64Upload,
    DocumentExtractionRead,
    DocumentList,
    DocumentOcrResultRead,
    DocumentRead,
    DocumentSchemaAssignmentRead,
    DocumentClassificationRead,
    DocumentContentRead,
)
from app.services.blob_storage import BlobStorageService
from app.tasks.processing import process_document_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    model_name: str | None = Form(None),
    schema_id: str | None = Form(None),
    preprocessing: str = Form("automatic"),
    display_name: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    try:
        logger.info(f"Starting upload for file: {file.filename}, model: {model_name}")
        
        # Read file content
        file_bytes = await file.read()
        logger.info(f"Read {len(file_bytes)} bytes from uploaded file")
        
        # Validate PDF page count (max 5 pages)
        if file.content_type == 'application/pdf':
            from app.services.document_converter import DocumentConverterService
            converter = DocumentConverterService()
            if converter.is_pdf(file_bytes):
                page_count = converter.get_page_count(file_bytes)
                if page_count > 5:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sorry, no PDFs larger than 5 pages. This PDF has {page_count} pages."
                    )
        
        # Upload to blob storage
        blob_service = BlobStorageService()
        blob_path, blob_url = blob_service.upload_document(
            content=file_bytes,
            filename=file.filename,
            content_type=file.content_type,
        )
        logger.info(f"Uploaded to blob storage: {blob_path}")

        # Validate schema if provided
        schema_uuid: uuid.UUID | None = None
        if schema_id:
            try:
                schema_uuid = uuid.UUID(schema_id)
            except ValueError as exc:
                logger.error(f"Invalid schema ID format: {schema_id}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
                    detail="Invalid schema identifier"
                ) from exc

            schema_exists = await db.scalar(select(SchemaDefinition.id).where(SchemaDefinition.id == schema_uuid))
            if not schema_exists:
                logger.error(f"Schema not found: {schema_uuid}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schema not found")

        # Get current user from session (None for anonymous uploads)
        session_token = request.cookies.get("session_token")
        user_id_uuid = None
        user_home_folder_id = None
        
        if session_token:
            user_data = AuthService.get_user_from_session(session_token)
            if user_data and user_data.get("user_id"):
                try:
                    user_id_uuid = uuid.UUID(user_data.get("user_id"))
                    
                    # Get user's home folder
                    home_folder_result = await db.execute(
                        select(Folder.id).where(
                            Folder.user_id == user_id_uuid,
                            Folder.is_home == True
                        )
                    )
                    user_home_folder_id = home_folder_result.scalar_one_or_none()
                except (ValueError, TypeError):
                    pass
        
        # Create document record
        details = {
            "content_type": file.content_type,
            "preprocessing": preprocessing,
        }
        if display_name:
            details["custom_name"] = display_name.strip()

        document = Document(
            original_filename=file.filename,
            user_id=user_id_uuid,  # None for anonymous
            folder_id=user_home_folder_id,  # Assign to user's Home folder if logged in
            selected_model=model_name,
            selected_schema_id=schema_uuid,
            blob_path=blob_path,
            blob_url=blob_url,
            status="processing",
            details=details,
        )
        db.add(document)
        await db.flush()
        
        # Create metrics record (optional - skip if table doesn't exist)
        try:
            # Get real client IP (behind Azure proxy/load balancer)
            client_ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
                request.headers.get("x-real-ip") or
                (request.client.host if request.client else None)
            )
            user_agent = request.headers.get("user-agent")
            
            metrics = DocumentMetrics(
                document_id=document.id,
                ip_address=client_ip,
                user_agent=user_agent,
                ocr_model=model_name,
            )
            db.add(metrics)
        except Exception as e:
            logger.warning(f"Metrics table not available, skipping: {e}")
        
        await db.commit()
        await db.refresh(
            document,
            attribute_names=["id", "original_filename", "selected_model", "blob_path", "blob_url", "uploaded_at", "status"]
        )
        
        logger.info(f"Created document record: {document.id} from IP: {client_ip}")

        # Queue background processing
        logger.info(
            "Queuing background processing for document %s with model=%s, schema=%s, preprocessing=%s",
            document.id,
            model_name,
            schema_uuid,
            preprocessing
        )
        background_tasks.add_task(
            process_document_task,
            document.id,
            blob_path,
            file.content_type,
            model_name,
            schema_uuid,
            preprocessing,
        )

        # Return document with empty relationships since it was just created
        return DocumentRead(
            id=document.id,
            original_filename=document.original_filename,
            user_id=document.user_id,
            selected_model=document.selected_model,
            selected_schema_id=document.selected_schema_id,
            folder_id=document.folder_id,
            blob_path=document.blob_path,
            blob_url=document.blob_url,
            uploaded_at=document.uploaded_at,
            status=document.status,
            details=document.details,
            last_processed_at=document.last_processed_at,
            detected_type=document.detected_type,
            detected_confidence=document.detected_confidence,
            ocr_results=[],
            schemas=[],
            contents=[],
            classifications=[],
            extractions=[],
            selected_schema=None,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as exc:
        logger.exception(f"Upload failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(exc)}"
        )


@router.get("/{document_id}/extractions", response_model=list[DocumentExtractionRead])
async def list_document_extractions(
    document_id: uuid.UUID,
    extraction_type: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[DocumentExtractionRead]:
    """
    Get all extractions (tables, line items) for a document
    
    Args:
        document_id: Document UUID
        extraction_type: Optional filter by type ('table', 'line_items', 'key_value')
    """
    document = await db.get(Document, document_id, options=(selectinload(Document.extractions),))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    extractions = document.extractions
    
    # Filter by type if specified
    if extraction_type:
        extractions = [e for e in extractions if e.extraction_type == extraction_type]
    
    return [DocumentExtractionRead.model_validate(item) for item in extractions]


@router.get("/{document_id}/extractions/json", response_model=dict)
async def get_document_extractions_json(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get all extractions as a consolidated JSON output
    
    Returns a structured JSON with all extracted data including:
    - OCR text
    - Tables
    - Line items
    - Key-value pairs
    - Classifications
    """
    document = await db.get(
        Document,
        document_id,
        options=(
            selectinload(Document.extractions),
            selectinload(Document.ocr_results),
            selectinload(Document.contents),
            selectinload(Document.classifications),
            selectinload(Document.schemas).selectinload(DocumentSchema.schema),
        ),
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    # Build consolidated JSON output
    output = {
        "document_id": str(document.id),
        "filename": document.original_filename,
        "detected_type": document.detected_type,
        "detected_confidence": document.detected_confidence,
        "processed_at": document.last_processed_at.isoformat() if document.last_processed_at else None,
        "ocr_text": None,
        "tables": [],
        "line_items": [],
        "key_value_pairs": {},
        "classifications": [],
        "applied_schemas": [],
    }
    
    # Add OCR text - prefer docstrange over parasail over docling
    if document.contents:
        docstrange_content = next((c for c in document.contents if c.source == "docstrange"), None)
        parasail_content = next((c for c in document.contents if c.source == "parasail"), None)
        docling_content = next((c for c in document.contents if c.source == "docling"), None)
        
        preferred_content = docstrange_content or parasail_content or docling_content
        if preferred_content:
            output["ocr_text"] = preferred_content.text
    
    # Add extractions
    for extraction in document.extractions:
        if extraction.extraction_type == "table":
            output["tables"].append({
                "table_index": extraction.metadata.get("table_index"),
                "page": extraction.metadata.get("page"),
                "headers": extraction.data.get("headers", []),
                "rows": extraction.data.get("rows", []),
                "row_count": extraction.data.get("row_count", 0),
                "column_count": extraction.data.get("column_count", 0),
            })
        elif extraction.extraction_type == "line_items":
            output["line_items"] = extraction.data.get("items", [])
        elif extraction.extraction_type == "key_value":
            output["key_value_pairs"].update(extraction.data)
    
    # Add classifications
    for classification in document.classifications:
        output["classifications"].append({
            "label": classification.label,
            "confidence": classification.confidence,
            "rationale": classification.rationale,
            "suggested_fields": classification.extra.get("suggested_fields", []),
        })
    
    # Add applied schemas
    for schema_assignment in document.schemas:
        output["applied_schemas"].append({
            "schema_name": schema_assignment.schema.name if schema_assignment.schema else None,
            "schema_category": schema_assignment.schema.category if schema_assignment.schema else None,
            "extracted_values": schema_assignment.extracted_values,
            "applied_at": schema_assignment.created_at.isoformat(),
        })
    
    return output


@router.get("", response_model=DocumentList)
async def list_documents(request: Request, db: AsyncSession = Depends(get_db)) -> DocumentList:
    # Get current user from session
    session_token = request.cookies.get("session_token")
    is_admin = AuthService.is_admin(session_token)
    current_user_id = None
    
    if session_token:
        user_data = AuthService.get_user_from_session(session_token)
        if user_data and user_data.get("user_id"):
            try:
                current_user_id = uuid.UUID(user_data.get("user_id"))
            except (ValueError, TypeError):
                pass
    
    # Build query
    query = select(Document).options(
        selectinload(Document.selected_schema),
    ).order_by(Document.uploaded_at.desc())
    
    result = await db.execute(query)
    documents = list(result.scalars().all())
    
    # Get trash folder ID (safely handle if is_trash column doesn't exist yet)
    trash_folder_id = None
    try:
        trash_folder_result = await db.execute(
            select(Folder.id).where(Folder.is_trash == True).limit(1)
        )
        trash_folder_id = trash_folder_result.scalar()
    except Exception as e:
        logger.warning(f"Could not query trash folder: {e}")
    
    # Filter documents based on user permissions
    filtered_documents = []
    for doc in documents:
        # Always exclude trash for non-admins
        if not is_admin and trash_folder_id and doc.folder_id == trash_folder_id:
            continue
        
        # Admin sees everything
        if is_admin:
            filtered_documents.append(doc)
        # Logged-in user sees their own documents + guest documents
        elif current_user_id:
            if doc.user_id == current_user_id or doc.user_id is None:
                filtered_documents.append(doc)
        # Guests (not logged in) see only guest documents
        else:
            if doc.user_id is None:
                filtered_documents.append(doc)
    
    documents = filtered_documents
    
    logger.info(
        f"Returning {len(documents)} documents for user_id={current_user_id}, "
        f"is_admin={is_admin}, trash_folder_id={trash_folder_id}"
    )
    
    # Return documents with empty collections for heavy relationships
    return DocumentList(items=[
        DocumentRead(
            id=doc.id,
            original_filename=doc.original_filename,
            user_id=doc.user_id,
            selected_model=doc.selected_model,
            selected_schema_id=doc.selected_schema_id,
            blob_path=doc.blob_path,
            blob_url=doc.blob_url,
            uploaded_at=doc.uploaded_at,
            status=doc.status,
            details=doc.details,
            last_processed_at=doc.last_processed_at,
            detected_type=doc.detected_type,
            detected_confidence=doc.detected_confidence,
            selected_schema=doc.selected_schema,
            folder_id=doc.folder_id,
            # Empty collections - will be loaded on-demand for individual document view
            ocr_results=[],
            schemas=[],
            contents=[],
            classifications=[],
            extractions=[],
        )
        for doc in documents
    ])


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
            selectinload(Document.extractions),
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


@router.get("/{document_id}/content")
async def get_document_content(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """
    Stream the original document file from blob storage
    This endpoint serves the actual document file (PDF, image, etc.) for preview/download
    
    For CSV files, converts to HTML table for easy browser preview
    """
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    try:
        # Download the document from blob storage
        blob_service = BlobStorageService()
        file_content = blob_service.download_document(document.blob_path)
        
        # Determine content type based on filename extension
        content_type = "application/octet-stream"
        filename_lower = document.original_filename.lower() if document.original_filename else ""
        
        # Handle different file types
        if filename_lower.endswith('.pdf'):
            content_type = "application/pdf"
        elif filename_lower.endswith(('.png', '.jpg', '.jpeg')):
            content_type = f"image/{filename_lower.split('.')[-1].replace('jpg', 'jpeg')}"
        elif filename_lower.endswith(('.tiff', '.tif')):
            content_type = "image/tiff"
        elif filename_lower.endswith('.csv'):
            # Convert CSV to HTML table for browser preview
            import csv
            from io import StringIO, BytesIO
            
            try:
                csv_text = file_content.decode('utf-8')
                csv_reader = csv.reader(StringIO(csv_text))
                rows = list(csv_reader)
                
                # Generate HTML table
                html = '''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>CSV Preview</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                            margin: 0;
                            padding: 20px;
                            background: #f5f5f5;
                        }
                        .container {
                            max-width: 1400px;
                            margin: 0 auto;
                            background: white;
                            border-radius: 8px;
                            padding: 20px;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            overflow-x: auto;
                        }
                        h1 {
                            margin: 0 0 20px 0;
                            font-size: 24px;
                            color: #333;
                        }
                        table {
                            width: 100%;
                            border-collapse: collapse;
                            font-size: 14px;
                        }
                        th, td {
                            padding: 12px;
                            text-align: left;
                            border: 1px solid #ddd;
                        }
                        th {
                            background: #673ab7;
                            color: white;
                            font-weight: 600;
                            position: sticky;
                            top: 0;
                            z-index: 10;
                        }
                        tr:nth-child(even) {
                            background: #f9f9f9;
                        }
                        tr:hover {
                            background: #f0f0f0;
                        }
                        .stats {
                            margin-bottom: 15px;
                            padding: 10px;
                            background: #e3f2fd;
                            border-radius: 4px;
                            font-size: 13px;
                            color: #1976d2;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>📊 CSV Preview: ''' + document.original_filename + '''</h1>
                        <div class="stats">
                            📈 Rows: ''' + str(len(rows)) + ''' | 📋 Columns: ''' + (str(len(rows[0])) if rows else '0') + '''
                        </div>
                        <table>
                '''
                
                # Add header row
                if rows:
                    html += '<thead><tr>'
                    for cell in rows[0]:
                        html += f'<th>{cell}</th>'
                    html += '</tr></thead>'
                    
                    # Add data rows
                    html += '<tbody>'
                    for row in rows[1:]:
                        html += '<tr>'
                        for cell in row:
                            html += f'<td>{cell}</td>'
                        html += '</tr>'
                    html += '</tbody>'
                
                html += '''
                        </table>
                    </div>
                </body>
                </html>
                '''
                
                file_content = html.encode('utf-8')
                content_type = "text/html; charset=utf-8"
            except Exception as csv_error:
                logger.warning(f"Failed to convert CSV to HTML: {csv_error}, serving as text")
                content_type = "text/csv"
        elif filename_lower.endswith(('.html', '.htm')):
            content_type = "text/html"
        elif filename_lower.endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename_lower.endswith('.xlsx'):
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename_lower.endswith('.pptx'):
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        
        # Return as streaming response
        from io import BytesIO
        return StreamingResponse(
            BytesIO(file_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{document.original_filename}"',
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        logger.error(f"Failed to retrieve document content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document content"
        )


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


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document permanently (trash folder functionality temporarily disabled)
    
    This will:
    - Delete the document record from the database
    - Delete all related data (OCR results, contents, classifications, extractions, schema assignments)
    - Delete the document from blob storage
    """
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    # TEMPORARILY DISABLED - trash folder functionality until migration runs
    # # Get or create trash folder
    # result = await db.execute(
    #     select(Folder).where(Folder.is_trash == True)
    # )
    # trash_folder = result.scalar_one_or_none()
    # 
    # if not trash_folder:
    #     trash_folder = Folder(
    #         name="🗑️ Trash",
    #         path="🗑️ Trash",
    #         is_system=True,
    #         is_trash=True
    #     )
    #     db.add(trash_folder)
    #     await db.flush()
    # 
    # # Move document to trash
    # document.folder_id = trash_folder.id
    # await db.commit()
    
    # Permanently delete for now
    blob_path = document.blob_path
    
    # Delete from database (cascading deletes will handle related records)
    await db.delete(document)
    await db.commit()
    
    # Delete from blob storage
    if blob_path:
        try:
            blob_service = BlobStorageService()
            blob_service.delete_document(blob_path)
        except Exception as e:
            # Log error but don't fail the request since DB record is already deleted
            logger.error("Failed to delete blob %s: %s", blob_path, str(e))


# TEMPORARILY DISABLED - trash folder functionality until migration runs
# @router.delete("/{document_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
# async def permanent_delete_document(
#     document_id: uuid.UUID,
#     request: Request,
#     db: AsyncSession = Depends(get_db),
# ) -> None:
#     """
#     Permanently delete a document from the trash folder (admin only)
#     
#     This will:
#     - Verify user is admin
#     - Verify document is in trash folder
#     - Delete the document record from the database
#     - Delete all related data (OCR results, contents, classifications, extractions, schema assignments)
#     - Delete the document from blob storage
#     """
#     # Check admin permission
#     session_token = request.cookies.get("session_token")
#     if not AuthService.is_admin(session_token):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN, 
#             detail="Only administrators can permanently delete documents"
#         )
#     
#     document = await db.get(Document, document_id)
#     if not document:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
#     
#     # Verify document is in trash folder
#     if document.folder_id:
#         folder = await db.get(Folder, document.folder_id)
#         if not folder or not folder.is_trash:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Document must be in trash folder to permanently delete"
#             )
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Document must be in trash folder to permanently delete"
#         )
#     
#     blob_path = document.blob_path
#     
#     # Delete from database (cascading deletes will handle related records)
#     await db.delete(document)
#     await db.commit()
#     
#     # Delete from blob storage
#     if blob_path:
#         try:
#             blob_service = BlobStorageService()
#             blob_service.delete_document(blob_path)
#         except Exception as e:
#             # Log error but don't fail the request since DB record is already deleted
#             logger.error("Failed to delete blob %s: %s", blob_path, str(e))


# TEMPORARILY DISABLED - trash folder functionality until migration runs
# @router.post("/{document_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
# async def restore_document(
#     document_id: uuid.UUID,
#     db: AsyncSession = Depends(get_db),
# ) -> None:
#     """
#     Restore a document from trash to uncategorized
#     """
#     document = await db.get(Document, document_id)
#     if not document:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
#     
#     # Verify document is in trash
#     if document.folder_id:
#         folder = await db.get(Folder, document.folder_id)
#         if not folder or not folder.is_trash:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Document is not in trash folder"
#             )
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Document is not in trash folder"
#         )
#     
#     # Move to uncategorized (set folder_id to None)
#     document.folder_id = None
#     await db.commit()


@router.post("/base64", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document_base64(
    background_tasks: BackgroundTasks,
    payload: DocumentBase64Upload,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_api_key_required),
) -> DocumentRead:
    """
    Upload a document via base64 encoding (requires API key authentication)
    
    This endpoint allows programmatic document submission with base64 encoded content.
    Requires a valid API key in the Authorization header as Bearer token.
    """
    # Decode base64 content
    try:
        file_bytes = base64.b64decode(payload.content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid base64 content: {str(exc)}"
        ) from exc
    
    # Validate schema if provided
    schema_uuid: uuid.UUID | None = None
    if payload.schema_id:
        schema_exists = await db.scalar(
            select(SchemaDefinition.id).where(SchemaDefinition.id == payload.schema_id)
        )
        if not schema_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schema not found"
            )
        schema_uuid = payload.schema_id
    
    # Upload to blob storage
    blob_service = BlobStorageService()
    blob_path, blob_url = blob_service.upload_document(
        content=file_bytes,
        filename=payload.filename,
        content_type=payload.content_type or "application/octet-stream",
    )
    
    # Create document record
    document = Document(
        original_filename=payload.filename,
        user_id=user.id,
        selected_model=payload.model_name,
        selected_schema_id=schema_uuid,
        blob_path=blob_path,
        blob_url=blob_url,
        details={
            "content_type": payload.content_type or "application/octet-stream",
            "uploaded_via": "api_base64",
            "user_id": str(user.id),
            "user_email": user.email,
        },
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Queue background processing
    background_tasks.add_task(
        process_document_task,
        document.id,
        blob_path,
        payload.content_type,
        payload.model_name,
        schema_uuid,
        "automatic",  # Default preprocessing for API uploads
    )
    
    return DocumentRead.model_validate(document)
