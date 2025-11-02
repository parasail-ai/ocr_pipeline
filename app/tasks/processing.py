import asyncio
import json
import logging
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    DocumentClassification,
    DocumentContent,
    DocumentExtraction,
    DocumentMetrics,
    DocumentOcrResult,
    DocumentSchema,
    SchemaDefinition,
)
from app.db.session import AsyncSessionLocal
from app.services.ai_schema_generator import create_ai_schema_generator
from app.services.blob_storage import BlobStorageService
from app.services.classifier import DocumentClassifier
from app.services.docling import DoclingProcessor, DoclingUnavailable
from app.services.parasail import ParasailOCRClient
from app.services.pdf_splitter import PDFSplitterService
from app.services.schema_generator import SchemaGenerator
from app.services.table_extractor import TableExtractor

logger = logging.getLogger(__name__)


async def process_document_task(
    document_id: uuid.UUID,
    blob_path: str,
    content_type: str | None,
    model_name: str | None,
    initial_schema_id: uuid.UUID | None,
) -> None:
    """Background task that fetches a document from blob storage, runs Docling, and triggers Parasail OCR."""
    logger.info("=" * 80)
    logger.info(f"STARTING BACKGROUND PROCESSING FOR DOCUMENT {document_id}")
    logger.info(f"Blob path: {blob_path}")
    logger.info(f"Model: {model_name}")
    logger.info(f"Content type: {content_type}")
    logger.info("=" * 80)
    
    # Update status to show we're downloading from blob storage
    await _update_document_status(
        document_id,
        status="downloading",
        details={"stage": "downloading_from_blob", "blob_path": blob_path}
    )
    
    blob_service = BlobStorageService()

    try:
        logger.info(f"Downloading document from blob storage: {blob_path}")
        file_bytes = await asyncio.to_thread(blob_service.download_document, blob_path)
        logger.info(f"Downloaded {len(file_bytes)} bytes from blob storage")
        
        await _update_document_status(
            document_id,
            status="downloaded",
            details={"stage": "downloaded", "file_size": len(file_bytes)}
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to download document %s from blob storage", document_id, exc_info=exc)
        await _update_document_status(document_id, status="error", details={"error": str(exc), "stage": "download_failed"})
        return

    docling_extraction: dict[str, Any] | None = None
    docling_text: str | None = None
    
    # Only use Docling if no model is specified (disabled by default)
    # Users must select a Parasail model for OCR processing
    if not model_name:
        logger.info("No OCR model selected. Docling processing is disabled by default. Please select a model.")
    
    parasail_response: dict[str, Any] | None = None
    parasail_text: str | None = None

    if model_name:
        try:
            # Update status to show OCR is starting
            await _update_document_status(
                document_id,
                status="ocr_processing",
                details={"stage": "running_ocr", "model": model_name}
            )
            
            logger.info(f"Starting Parasail OCR with model: {model_name}")
            
            client = ParasailOCRClient()
            
            # Check if this is a multi-page PDF
            pdf_splitter = PDFSplitterService()
            if pdf_splitter.is_pdf(file_bytes):
                page_count = await asyncio.to_thread(pdf_splitter.get_page_count, file_bytes)
                logger.info(f"Detected PDF with {page_count} pages")
                
                if page_count > 1:
                    # Split PDF into individual page images
                    logger.info(f"Splitting PDF into {page_count} page images...")
                    page_images = await asyncio.to_thread(
                        pdf_splitter.split_pdf_to_images,
                        file_bytes,
                        dpi=200  # Good quality for OCR
                    )
                    logger.info(f"Split {len(page_images)} pages successfully")
                    
                    # Process all pages
                    parasail_response = await asyncio.to_thread(
                        client.extract_multi_page,
                        page_images=page_images,
                        filename=Path(blob_path).name,
                        model=model_name,
                    )
                    logger.info(f"Parasail multi-page OCR completed for {page_count} pages")
                    
                    # Extract combined text from multi-page response
                    parasail_text = parasail_response.get("combined_text", "")
                else:
                    # Single page PDF - process normally
                    logger.info(f"Processing single-page PDF")
                    parasail_response = await asyncio.to_thread(
                        client.extract_document,
                        content=file_bytes,
                        filename=Path(blob_path).name,
                        mime_type=content_type,
                        model=model_name,
                    )
                    parasail_text = _extract_text_from_parasail_response(parasail_response)
            else:
                # Not a PDF - process as single image/document
                logger.info(f"Processing non-PDF document ({content_type})")
                parasail_response = await asyncio.to_thread(
                    client.extract_document,
                    content=file_bytes,
                    filename=Path(blob_path).name,
                    mime_type=content_type,
                    model=model_name,
                )
                parasail_text = _extract_text_from_parasail_response(parasail_response)
            
            logger.info(f"Parasail OCR completed for document {document_id}")
            
            if parasail_text:
                logger.info(f"Extracted {len(parasail_text)} characters of text from Parasail response")
            else:
                logger.warning(f"No text extracted from Parasail response for document {document_id}")
                
        except Exception as exc:  # pragma: no cover - Parasail failure
            logger.exception("Parasail OCR failed for document %s", document_id, exc_info=exc)
            parasail_response = {"error": str(exc)}
            await _update_document_status(
                document_id,
                status="ocr_failed",
                details={"stage": "ocr_failed", "error": str(exc)}
            )

    # Update status to processing (OCR complete, but extraction still pending)
    await _update_document_status(
        document_id,
        status="processing",
        details={
            "content_type": content_type,
            "stage": "ocr_complete",
            "docling": docling_extraction,
            "docling_text": docling_text,
            "parasail": {
                "model": model_name,
                "response": parasail_response,
                "text": parasail_text,
            }
            if model_name
            else None,
        },
    )

    if model_name and parasail_response is not None:
        await _store_ocr_result(
            document_id=document_id,
            model_name=model_name,
            raw_response=parasail_response,
            extracted_text=parasail_text,
            summary=_build_summary(parasail_text, docling_text),
        )
        
        # Update metrics with token usage and duration
        await _update_metrics_with_ocr_data(
            document_id=document_id,
            parasail_response=parasail_response,
        )

    await _store_document_contents(
        document_id=document_id,
        contents={
            "parasail": parasail_text,
            "docling": docling_text,
        },
    )

    # Extract tables and line items if Docling was successful
    if docling_extraction:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(blob_path).suffix) as tmp_file:
            tmp_file.write(file_bytes)
            temp_path = Path(tmp_file.name)
        
        try:
            await _extract_and_store_tables(document_id, temp_path)
        except Exception as exc:
            logger.exception("Table extraction failed for document %s", document_id, exc_info=exc)
        finally:
            temp_path.unlink(missing_ok=True)

    # Extract key-value pairs and auto-generate schema (but don't save as reusable template)
    base_text = parasail_text or docling_text
    if base_text:
        if initial_schema_id is None:
            await _maybe_classify_document(
                document_id=document_id,
                base_text=base_text,
                snippets={"parasail": parasail_text, "docling": docling_text},
            )
            # Auto-generate schema for this document (not saved as reusable template)
            await _auto_generate_schema(
                document_id=document_id,
                ocr_text=base_text,
            )
        
        # Extract key-value pairs regardless of schema
        await _extract_key_value_pairs(
            document_id=document_id,
            ocr_text=base_text,
        )
    
    # Mark as fully processed after all extraction and classification is complete
    await _update_document_status(
        document_id,
        status="processed",
        details={"stage": "complete", "extraction_complete": True}
    )
    logger.info(f"Document {document_id} processing complete")


async def _update_document_status(document_id: uuid.UUID, *, status: str, details: dict) -> None:
    async with AsyncSessionLocal() as session:  # type: AsyncSession
        document = await session.get(Document, document_id)
        if not document:
            logger.warning("Document %s not found during processing status update", document_id)
            return

        document.status = status
        cleaned_details = {key: value for key, value in details.items() if value is not None}
        document.details = {**(document.details or {}), **cleaned_details}
        document.last_processed_at = datetime.utcnow()
        await session.commit()


async def _store_ocr_result(
    *,
    document_id: uuid.UUID,
    model_name: str,
    raw_response: dict[str, Any],
    extracted_text: str | None,
    summary: str | None,
) -> None:
    async with AsyncSessionLocal() as session:
        # Extract timing information from response if available
        timing = raw_response.get('_timing', {})
        started_at = None
        completed_at = None
        duration_ms = None
        
        if timing:
            from datetime import datetime
            if timing.get('start_time'):
                started_at = datetime.fromtimestamp(timing['start_time'])
            if timing.get('end_time'):
                completed_at = datetime.fromtimestamp(timing['end_time'])
            duration_ms = timing.get('duration_ms')
        
        record = DocumentOcrResult(
            document_id=document_id,
            model_name=model_name,
            raw_response=raw_response or {},
            extracted_text=extracted_text,
            summary=summary,
        )
        
        # Add timing fields if they exist in the model
        if hasattr(record, 'started_at'):
            record.started_at = started_at
        if hasattr(record, 'completed_at'):
            record.completed_at = completed_at
        if hasattr(record, 'duration_ms'):
            record.duration_ms = duration_ms
            
        session.add(record)
        await session.commit()


async def _store_document_contents(document_id: uuid.UUID, contents: dict[str, str | None]) -> None:
    entries = [
        DocumentContent(
            document_id=document_id,
            source=source,
            text=text,
            fragment_metadata={"length": len(text)} if text else {},
        )
        for source, text in contents.items()
        if text
    ]
    if not entries:
        return

    async with AsyncSessionLocal() as session:
        session.add_all(entries)
        await session.commit()


async def _maybe_classify_document(
    *,
    document_id: uuid.UUID,
    base_text: str,
    snippets: dict[str, str | None],
) -> None:
    classifier = DocumentClassifier()
    suggestion = await asyncio.to_thread(classifier.classify, base_text, snippets=snippets)

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        document = await session.get(Document, document_id, with_for_update=True)
        if not document:
            return

        suggested_schema_id: uuid.UUID | None = None
        if suggestion.suggested_schema_name:
            stmt = select(SchemaDefinition.id).where(
                func.lower(SchemaDefinition.name) == suggestion.suggested_schema_name.lower()
            )
            schema_id = await session.scalar(stmt)
            if schema_id:
                suggested_schema_id = schema_id

        classification = DocumentClassification(
            document_id=document_id,
            label=suggestion.label,
            confidence=suggestion.confidence,
            rationale=suggestion.rationale,
            suggested_schema_id=suggested_schema_id,
            extra={
                "suggested_fields": list(suggestion.suggested_fields),
                **(suggestion.metadata or {}),
            },
        )
        session.add(classification)

        if document.selected_schema_id is None and suggested_schema_id:
            document.selected_schema_id = suggested_schema_id
        if suggestion.label and suggestion.label != "unknown":
            document.detected_type = suggestion.label
            document.detected_confidence = suggestion.confidence

        await session.commit()


def _derive_docling_text(extraction: dict[str, Any] | None) -> str | None:
    if not extraction:
        return None

    if isinstance(extraction, dict):
        if "text" in extraction and isinstance(extraction["text"], str):
            return extraction["text"]
        if "pages" in extraction and isinstance(extraction["pages"], list):
            texts = []
            for page in extraction["pages"]:
                if isinstance(page, dict):
                    text = page.get("text")
                    if isinstance(text, str):
                        texts.append(text)
            if texts:
                return "\n\n".join(texts)

    try:
        return json.dumps(extraction, ensure_ascii=False)
    except Exception:  # pragma: no cover - fallback
        return None


def _extract_text_from_parasail_response(response: dict[str, Any] | None) -> str | None:
    if not response:
        return None

    # Handle OpenAI-style responses
    choices = response.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or {}
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    text_segments = [segment.get("text") for segment in content if isinstance(segment, dict)]
                    text_segments = [segment for segment in text_segments if isinstance(segment, str)]
                    if text_segments:
                        return "\n".join(text_segments)

    data = response.get("data")
    if isinstance(data, list):
        text_segments = []
        for item in data:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    text_segments.append(item["text"])
                elif isinstance(item.get("embedding"), list):
                    continue
        if text_segments:
            return "\n".join(text_segments)

    if isinstance(response.get("text"), str):
        return response["text"]

    return None


def _build_summary(parasail_text: str | None, docling_text: str | None) -> str | None:
    corpus = parasail_text or docling_text
    if not corpus:
        return None
    corpus = corpus.strip()
    if len(corpus) <= 500:
        return corpus
    return corpus[:500] + "…"


async def _extract_and_store_tables(document_id: uuid.UUID, file_path: Path) -> None:
    """Extract tables and line items from document and store them"""
    try:
        extractor = TableExtractor()
    except RuntimeError:
        logger.info("Table extractor not available for document %s", document_id)
        return
    
    # Extract tables
    tables = await asyncio.to_thread(extractor.extract_tables, file_path)
    
    if not tables:
        logger.info("No tables found in document %s", document_id)
        return
    
    # Extract line items from tables
    line_items = await asyncio.to_thread(extractor.extract_line_items, tables)
    
    # Store extractions
    async with AsyncSessionLocal() as session:
        extractions = []
        
        # Store each table
        for table_idx, table in enumerate(tables):
            extraction = DocumentExtraction(
                document_id=document_id,
                extraction_type="table",
                source="docling",
                data=table,
                extraction_metadata={
                    "table_index": table_idx,
                    "row_count": table.get("row_count", 0),
                    "column_count": table.get("column_count", 0),
                }
            )
            extractions.append(extraction)
        
        # Store line items as a single extraction
        if line_items:
            extraction = DocumentExtraction(
                document_id=document_id,
                extraction_type="line_items",
                source="docling",
                data={"items": line_items},
                extraction_metadata={
                    "item_count": len(line_items),
                    "source_tables": len(tables),
                }
            )
            extractions.append(extraction)
        
        if extractions:
            session.add_all(extractions)
            await session.commit()
            logger.info("Stored %d extractions for document %s", len(extractions), document_id)


async def _auto_generate_schema(
    document_id: uuid.UUID,
    ocr_text: str,
) -> None:
    """
    Auto-generate schema from OCR text using AI and apply to document.
    Creates a DocumentSchema with extracted values but does NOT save as reusable template.
    """
    logger.info("Auto-generating schema with AI for document %s", document_id)
    
    try:
        # Use the new AI schema generator (parasail-glm-46)
        ai_generator = create_ai_schema_generator()
    except RuntimeError as exc:
        logger.warning("AI schema generator not available: %s", exc)
        # Fallback to old generator if AI not available
        try:
            generator = SchemaGenerator()
            logger.info("Using fallback SchemaGenerator for document %s", document_id)
        except RuntimeError:
            logger.warning("No schema generators available")
            return
        # Use old logic as fallback
        return await _auto_generate_schema_fallback(document_id, ocr_text, generator)
    
    async with AsyncSessionLocal() as session:
        # Get document
        document = await session.get(Document, document_id)
        if not document:
            return
        
        # Generate schema using AI
        try:
            schema_data = await asyncio.to_thread(
                ai_generator.generate_schema_from_ocr,
                ocr_text,
                document_type=document.detected_type,
                schema_name=None  # Let AI decide the name
            )
            
            if not schema_data:
                logger.warning("AI schema generation returned no data for document %s", document_id)
                return
            
            schema_name = schema_data.get("schema_name", "Auto-Generated Schema")
            category = schema_data.get("category", "unknown")
            description = schema_data.get("description", "Automatically generated by AI from OCR")
            fields = schema_data.get("fields", [])
            extracted_values = schema_data.get("extracted_values", {})
            
            logger.info(
                "AI generated schema '%s' with %d fields and %d extracted values",
                schema_name,
                len(fields),
                len(extracted_values)
            )
            
            # Create or get the ad-hoc schema template
            # This is a special internal schema that marks auto-generated (non-saved) schemas
            AD_HOC_SCHEMA_NAME = "__ad_hoc_auto_generated__"
            
            stmt = select(SchemaDefinition).where(
                SchemaDefinition.name == AD_HOC_SCHEMA_NAME
            )
            ad_hoc_schema = await session.scalar(stmt)
            
            if not ad_hoc_schema:
                # Create the ad-hoc schema placeholder
                ad_hoc_schema = SchemaDefinition(
                    name=AD_HOC_SCHEMA_NAME,
                    category="system",
                    description="Internal placeholder for auto-generated schemas (not user-visible)",
                    fields=fields,
                    is_template=False,
                )
                session.add(ad_hoc_schema)
                await session.flush()
                logger.info("Created ad-hoc schema placeholder")
            else:
                # Update fields if needed
                ad_hoc_schema.fields = fields
            
            # Apply schema to document with extracted values
            if extracted_values:
                assignment = DocumentSchema(
                    document_id=document_id,
                    schema_id=ad_hoc_schema.id,
                    extracted_values=extracted_values
                )
                session.add(assignment)
                    
                # Update detected type if not set
                if not document.detected_type and category != "unknown":
                    document.detected_type = category
                    document.detected_confidence = 0.9  # AI-generated confidence
                
                logger.info(
                    "Created document-specific schema with %d extracted fields for document %s",
                    len(extracted_values),
                    document_id
                )
            
            await session.commit()
            
        except Exception as exc:
            logger.exception("Failed to auto-generate schema with AI for document %s: %s", document_id, exc)


async def _auto_generate_schema_fallback(
    document_id: uuid.UUID,
    ocr_text: str,
    generator: SchemaGenerator,
) -> None:
    """Fallback schema generation using old SchemaGenerator."""
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if not document:
            return
        
        stmt = select(SchemaDefinition)
        result = await session.execute(stmt)
        existing_schemas = [
            {"id": str(s.id), "name": s.name, "category": s.category, "fields": s.fields}
            for s in result.scalars().all()
        ]
        
        try:
            schema_data = await asyncio.to_thread(
                generator.generate_schema_from_text,
                ocr_text,
                document_type=document.detected_type,
                existing_schemas=existing_schemas if existing_schemas else None
            )
            
            if not schema_data:
                return
            
            schema_name = schema_data.get("schema_name", "Auto-Generated Schema")
            category = schema_data.get("category", "unknown")
            description = schema_data.get("description", "Automatically generated from OCR")
            fields = schema_data.get("fields", [])
            extracted_values = schema_data.get("extracted_values", {})
            
            stmt = select(SchemaDefinition).where(func.lower(SchemaDefinition.name) == schema_name.lower())
            existing_schema = await session.scalar(stmt)
            
            if existing_schema:
                schema = existing_schema
            else:
                schema = SchemaDefinition(
                    name=schema_name,
                    category=category,
                    description=description,
                    fields={"fields": fields},
                )
                session.add(schema)
                await session.flush()
            
            if extracted_values:
                assignment = DocumentSchema(
                    document_id=document_id,
                    schema_id=schema.id,
                    extracted_values=extracted_values
                )
                session.add(assignment)
                
                if not document.selected_schema_id:
                    document.selected_schema_id = schema.id
                if not document.detected_type and category != "unknown":
                    document.detected_type = category
                    document.detected_confidence = 0.8
            
            await session.commit()
        except Exception as exc:
            logger.exception("Failed to auto-generate schema for document %s: %s", document_id, exc)


async def _extract_key_value_pairs(
    document_id: uuid.UUID,
    ocr_text: str,
) -> None:
    """Extract key-value pairs from OCR text using AI and store as extraction."""
    logger.info("Extracting key-value pairs with AI for document %s", document_id)
    
    # This function is now handled by _auto_generate_schema which uses AI
    # and includes both schema generation and key-value extraction
    # We don't need a separate extraction step since AI does both at once
    logger.info("Key-value extraction handled by AI schema generation for document %s", document_id)
    return


async def _update_metrics_with_ocr_data(
    document_id: uuid.UUID,
    parasail_response: dict[str, Any],
) -> None:
    """Update DocumentMetrics with token usage and duration from parasail_response."""
    async with AsyncSessionLocal() as session:
        stmt = select(DocumentMetrics).where(DocumentMetrics.document_id == document_id)
        metrics = await session.scalar(stmt)
        
        if not metrics:
            logger.warning("No metrics record found for document %s", document_id)
            return
        
        # Extract token counts from usage field
        usage = parasail_response.get("usage", {})
        if usage:
            metrics.prompt_tokens = usage.get("prompt_tokens")
            metrics.completion_tokens = usage.get("completion_tokens")
            metrics.total_tokens = usage.get("total_tokens")
        
        # Extract duration from timing
        timing = parasail_response.get("_timing", {})
        if timing:
            metrics.ocr_duration_ms = timing.get("duration_ms")
        
        metrics.processed_at = datetime.utcnow()
        await session.commit()
        
        logger.info(
            "Updated metrics for document %s: tokens=%s, duration=%s ms",
            document_id,
            metrics.total_tokens,
            metrics.ocr_duration_ms
        )
