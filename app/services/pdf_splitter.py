import logging
from io import BytesIO
from typing import List

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFSplitterService:
    """Service for splitting multi-page PDFs into individual pages."""

    @staticmethod
    def is_pdf(content: bytes) -> bool:
        """Check if the content is a PDF file."""
        return content.startswith(b'%PDF')

    @staticmethod
    def split_pdf_to_images(content: bytes, dpi: int = 200) -> List[bytes]:
        """
        Split a PDF into individual page images (PNG format).
        
        Args:
            content: PDF file content as bytes
            dpi: Resolution for rendering pages (default 200 DPI for good OCR quality)
            
        Returns:
            List of PNG image bytes, one per page
        """
        page_images = []
        
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=content, filetype="pdf")
            logger.info(f"PDF has {pdf_document.page_count} pages")
            
            # Convert each page to an image
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # Render page to pixmap (image)
                # Higher DPI = better quality but larger files
                zoom = dpi / 72  # 72 DPI is default
                matrix = fitz.Matrix(zoom, zoom)
                pixmap = page.get_pixmap(matrix=matrix)
                
                # Convert pixmap to PNG bytes
                png_bytes = pixmap.tobytes("png")
                page_images.append(png_bytes)
                
                logger.info(f"Rendered page {page_num + 1}/{pdf_document.page_count} at {dpi} DPI")
            
            pdf_document.close()
            return page_images
            
        except Exception as exc:
            logger.exception("Failed to split PDF into pages", exc_info=exc)
            raise RuntimeError(f"PDF splitting failed: {str(exc)}")

    @staticmethod
    def get_page_count(content: bytes) -> int:
        """Get the number of pages in a PDF."""
        try:
            pdf_document = fitz.open(stream=content, filetype="pdf")
            page_count = pdf_document.page_count
            pdf_document.close()
            return page_count
        except Exception as exc:
            logger.exception("Failed to get PDF page count", exc_info=exc)
            return 0
