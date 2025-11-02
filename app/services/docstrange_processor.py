import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DocStrangeProcessor:
    """Wrapper around docstrange library for document preprocessing"""
    
    def __init__(self):
        try:
            import docstrange
            self.docstrange = docstrange
            logger.info("DocStrange processor initialized successfully")
        except ImportError as e:
            logger.error("docstrange library not available: %s", e)
            raise RuntimeError("docstrange library is not installed") from e
    
    def is_supported_file(self, filename: str) -> bool:
        """
        Check if file type is supported by DocStrange
        
        Supported formats: PDF, DOCX, PPTX, XLSX, HTML, CSV
        """
        if not filename:
            return False
        
        filename_lower = filename.lower()
        supported_extensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.html', '.htm', '.csv']
        
        return any(filename_lower.endswith(ext) for ext in supported_extensions)
    
    def process_document(self, file_path: str | Path) -> dict[str, Any]:
        """
        Process document with DocStrange
        
        Args:
            file_path: Path to the document file
            
        Returns:
            dict containing:
                - markdown: str - extracted markdown text
                - data: dict - structured data
                - tables: list - extracted tables
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not self.is_supported_file(file_path.name):
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
        
        logger.info("Processing document with DocStrange: %s", file_path.name)
        
        try:
            # Process document with docstrange
            result = self.docstrange.process(str(file_path))
            
            # Extract markdown text
            markdown = result.get("markdown", "")
            
            # Extract structured data
            data = result.get("data", {})
            
            # Extract tables
            tables = result.get("tables", [])
            
            logger.info(
                "DocStrange processing complete: %d chars, %d tables",
                len(markdown) if markdown else 0,
                len(tables) if tables else 0
            )
            
            return {
                "markdown": markdown,
                "data": data,
                "tables": tables,
            }
            
        except Exception as e:
            logger.exception("DocStrange processing failed for %s: %s", file_path.name, e)
            raise RuntimeError(f"DocStrange processing failed: {str(e)}") from e
