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
    DocumentOcrResult,
    SchemaDefinition,
)
from app.db.session import AsyncSessionLocal
from app.services.blob_storage import BlobStorageService
from app.services.classifier import DocumentClassifier
from app.services.docling import DoclingProcessor, DoclingUnavailable
from app.services.parasail import ParasailOCRClient
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
    logger.info("Processing document %s", document_id)
    blob_service = BlobStorageService()

    try:
        file_bytes = await asyncio.to_thread(blob_service.download_document, blob_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to download document %s from blob storage", document_id, exc_info=exc)
        await _update_document_status(document_id, status="error", details={"error": str(exc)})
        return

    docling_extraction: dict[str, Any] | None = None
    docling_text: str | None = None

    try:
        processor = DoclingProcessor()
    except DoclingUnavailable:
        logger.info("Docling not available. Skipping structured extraction for %s", document_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected Docling initialization error", exc_info=exc)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(blob_path).suffix) as tmp_file:
            tmp_file.write(file_bytes)
            temp_path = Path(tmp_file.name)

        try:
            docling_extraction = await asyncio.to_thread(processor.extract_document_structure, temp_path)
            docling_text = _derive_docling_text(docling_extraction)
        except Exception as exc:  # pragma: no cover - docling failure
            logger.exception("Docling failed for document %s", document_id, exc_info=exc)
        finally:
            temp_path.unlink(missing_ok=True)

    parasail_response: dict[str, Any] | None = None
    parasail_text: str | None = None

    if model_name:
        try:
            client = ParasailOCRClient()
            parasail_response = await asyncio.to_thread(
                client.extract_document,
                content=file_bytes,
                filename=Path(blob_path).name,
                mime_type=content_type,
                model=model_name,
            )
            parasail_text = _extract_text_from_parasail_response(parasail_response)
        except Exception as exc:  # pragma: no cover - Parasail failure
            logger.exception("Parasail OCR failed for document %s", document_id, exc_info=exc)
            parasail_response = {"error": str(exc)}

    await _update_document_status(
        document_id,
        status="processed" if docling_extraction or parasail_response else "uploaded",
        details={
            "content_type": content_type,
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

    if initial_schema_id is None:
        base_text = parasail_text or docling_text
        if base_text:
            await _maybe_classify_document(
                document_id=document_id,
                base_text=base_text,
                snippets={"parasail": parasail_text, "docling": docling_text},
            )


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
        record = DocumentOcrResult(
            document_id=document_id,
            model_name=model_name,
            raw_response=raw_response or {},
            extracted_text=extracted_text,
            summary=summary,
        )
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
