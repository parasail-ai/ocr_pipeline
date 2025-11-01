import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings

try:
    from docling.document_converter import DocumentConverter
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
except ImportError:  # pragma: no cover - optional dependency
    DocumentConverter = None
    StandardPdfPipeline = None

logger = logging.getLogger(__name__)


class DoclingUnavailable(RuntimeError):
    pass


class DoclingProcessor:
    """Facade over Docling to keep integration points isolated."""

    def __init__(self) -> None:
        if DocumentConverter is None or StandardPdfPipeline is None:
            raise DoclingUnavailable(
                "Docling is not installed. Install docling to enable document parsing (pip install docling)."
            )
        self.settings = get_settings()
        self.converter = DocumentConverter(pipeline=StandardPdfPipeline())

    def extract_document_structure(self, file_path: Path) -> dict[str, Any]:
        doc = self.converter.convert(file_path)
        return doc.as_dict()

