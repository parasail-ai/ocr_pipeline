import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class DocumentConverterService:
    """Service for converting multi-page documents (PDF, DOCX, PPTX) to individual page images."""

    @staticmethod
    def is_pdf(content: bytes) -> bool:
        """Check if the content is a PDF file."""
        return content.startswith(b'%PDF')
    
    @staticmethod
    def is_docx(content: bytes) -> bool:
        """Check if the content is a DOCX file."""
        # DOCX files are ZIP archives starting with PK
        return content.startswith(b'PK') and b'word/' in content[:1000]
    
    @staticmethod
    def is_pptx(content: bytes) -> bool:
        """Check if the content is a PPTX file."""
        # PPTX files are ZIP archives starting with PK
        return content.startswith(b'PK') and b'ppt/' in content[:1000]
    
    @staticmethod
    def is_multi_page_document(content: bytes) -> bool:
        """Check if the content is a multi-page document that needs conversion."""
        return (
            DocumentConverterService.is_pdf(content) or 
            DocumentConverterService.is_docx(content) or
            DocumentConverterService.is_pptx(content)
        )

    @staticmethod
    def convert_to_images(content: bytes, filename: str, dpi: int = 200) -> List[bytes]:
        """
        Convert a multi-page document to individual page images (PNG format).
        
        Supports: PDF, DOCX, PPTX
        
        Args:
            content: Document file content as bytes
            filename: Original filename (used to determine type)
            dpi: Resolution for rendering pages (default 200 DPI for good OCR quality)
            
        Returns:
            List of PNG image bytes, one per page
        """
        # Try PDF first
        if DocumentConverterService.is_pdf(content):
            return DocumentConverterService._convert_pdf_to_images(content, dpi)
        
        # Try DOCX/PPTX conversion
        if DocumentConverterService.is_docx(content) or DocumentConverterService.is_pptx(content):
            return DocumentConverterService._convert_office_to_images(content, filename, dpi)
        
        raise ValueError(f"Unsupported document type: {filename}")

    @staticmethod
    def _convert_pdf_to_images(content: bytes, dpi: int = 200) -> List[bytes]:
        """Convert PDF pages to images."""
        page_images = []
        
        try:
            pdf_document = fitz.open(stream=content, filetype="pdf")
            logger.info(f"PDF has {pdf_document.page_count} pages")
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                zoom = dpi / 72
                matrix = fitz.Matrix(zoom, zoom)
                pixmap = page.get_pixmap(matrix=matrix)
                png_bytes = pixmap.tobytes("png")
                page_images.append(png_bytes)
                logger.info(f"Rendered PDF page {page_num + 1}/{pdf_document.page_count}")
            
            pdf_document.close()
            return page_images
            
        except Exception as exc:
            logger.exception("Failed to convert PDF to images", exc_info=exc)
            raise RuntimeError(f"PDF conversion failed: {str(exc)}")

    @staticmethod
    def _convert_office_to_images(content: bytes, filename: str, dpi: int = 200) -> List[bytes]:
        """
        Convert DOCX/PPTX to images by first converting to PDF, then to images.
        
        This requires libreoffice or similar office suite to be installed.
        """
        try:
            # Try to import required libraries
            try:
                from docx2pdf import convert as docx2pdf_convert
                use_docx2pdf = True
            except ImportError:
                use_docx2pdf = False
                logger.warning("docx2pdf not available, will try LibreOffice")
            
            import subprocess
            
            # Save to temp file
            suffix = Path(filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
                tmp_input.write(content)
                input_path = tmp_input.name
            
            try:
                # Convert to PDF first
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                    pdf_path = tmp_pdf.name
                
                try:
                    if use_docx2pdf:
                        # Use docx2pdf for Windows/Mac
                        docx2pdf_convert(input_path, pdf_path)
                        logger.info(f"Converted {filename} to PDF using docx2pdf")
                    else:
                        # Use LibreOffice for Linux
                        result = subprocess.run(
                            ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', 
                             Path(pdf_path).parent, input_path],
                            capture_output=True,
                            timeout=60
                        )
                        if result.returncode != 0:
                            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr.decode()}")
                        logger.info(f"Converted {filename} to PDF using LibreOffice")
                    
                    # Read PDF and convert to images
                    with open(pdf_path, 'rb') as f:
                        pdf_content = f.read()
                    
                    return DocumentConverterService._convert_pdf_to_images(pdf_content, dpi)
                    
                finally:
                    Path(pdf_path).unlink(missing_ok=True)
            finally:
                Path(input_path).unlink(missing_ok=True)
                
        except Exception as exc:
            logger.warning(f"Office document conversion failed: {str(exc)}, will process as single file")
            # If conversion fails, return original content as a single "page"
            # The OCR service will handle it as a single document
            return [content]

    @staticmethod
    def get_page_count(content: bytes, filename: str = "") -> int:
        """Get the number of pages in a document."""
        try:
            if DocumentConverterService.is_pdf(content):
                pdf_document = fitz.open(stream=content, filetype="pdf")
                page_count = pdf_document.page_count
                pdf_document.close()
                return page_count
            elif DocumentConverterService.is_docx(content) or DocumentConverterService.is_pptx(content):
                # For office documents, we'd need to convert to know page count
                # Return 1 as estimate (will be determined during conversion)
                return 1
            else:
                return 1
        except Exception as exc:
            logger.exception("Failed to get page count", exc_info=exc)
            return 1
