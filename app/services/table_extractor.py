"""Table and line item extraction service using Docling"""
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


class TableExtractor:
    """Extract tables and structured data from documents using Docling"""

    def __init__(self) -> None:
        if DocumentConverter is None or StandardPdfPipeline is None:
            raise RuntimeError(
                "Docling is not installed. Install docling to enable table extraction (pip install docling)."
            )
        self.settings = get_settings()
        self.converter = DocumentConverter(pipeline=StandardPdfPipeline())

    def extract_tables(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Extract all tables from a document
        
        Args:
            file_path: Path to the document file
            
        Returns:
            List of table dictionaries with structure and data
        """
        try:
            doc = self.converter.convert(file_path)
            doc_dict = doc.as_dict()
            
            tables = []
            
            # Extract tables from pages
            if "pages" in doc_dict and isinstance(doc_dict["pages"], list):
                for page_idx, page in enumerate(doc_dict["pages"]):
                    if not isinstance(page, dict):
                        continue
                    
                    # Look for tables in page elements
                    elements = page.get("elements", [])
                    if not isinstance(elements, list):
                        continue
                    
                    for elem_idx, element in enumerate(elements):
                        if not isinstance(element, dict):
                            continue
                        
                        if element.get("type") == "table":
                            table_data = self._parse_table_element(element)
                            if table_data:
                                table_data["metadata"] = {
                                    "page": page_idx + 1,
                                    "element_index": elem_idx,
                                    "source": "docling"
                                }
                                tables.append(table_data)
            
            # Also check for tables at document level
            if "tables" in doc_dict and isinstance(doc_dict["tables"], list):
                for table_idx, table in enumerate(doc_dict["tables"]):
                    if isinstance(table, dict):
                        table_data = self._parse_table_element(table)
                        if table_data:
                            table_data["metadata"] = {
                                "table_index": table_idx,
                                "source": "docling"
                            }
                            tables.append(table_data)
            
            return tables
            
        except Exception as exc:
            logger.exception("Failed to extract tables from document", exc_info=exc)
            return []

    def _parse_table_element(self, element: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse a table element into structured data
        
        Args:
            element: Table element dictionary from Docling
            
        Returns:
            Structured table data or None if parsing fails
        """
        try:
            # Extract table structure
            rows = element.get("rows", [])
            if not rows:
                # Try alternative structure
                cells = element.get("cells", [])
                if cells:
                    return self._parse_table_from_cells(cells)
                return None
            
            # Convert rows to structured format
            headers = []
            data_rows = []
            
            for row_idx, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                
                cells = row.get("cells", [])
                if not cells:
                    continue
                
                row_data = []
                for cell in cells:
                    if isinstance(cell, dict):
                        cell_text = cell.get("text", "")
                    else:
                        cell_text = str(cell)
                    row_data.append(cell_text)
                
                # First row is typically headers
                if row_idx == 0:
                    headers = row_data
                else:
                    data_rows.append(row_data)
            
            return {
                "headers": headers,
                "rows": data_rows,
                "row_count": len(data_rows),
                "column_count": len(headers) if headers else 0,
            }
            
        except Exception as exc:
            logger.warning("Failed to parse table element: %s", exc)
            return None

    def _parse_table_from_cells(self, cells: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Parse table from a flat list of cells with position information
        
        Args:
            cells: List of cell dictionaries with position info
            
        Returns:
            Structured table data or None if parsing fails
        """
        try:
            # Group cells by row
            rows_dict: dict[int, list[tuple[int, str]]] = {}
            
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                
                row_idx = cell.get("row", 0)
                col_idx = cell.get("col", 0)
                text = cell.get("text", "")
                
                if row_idx not in rows_dict:
                    rows_dict[row_idx] = []
                
                rows_dict[row_idx].append((col_idx, text))
            
            # Sort rows and cells
            sorted_rows = sorted(rows_dict.items())
            
            headers = []
            data_rows = []
            
            for row_idx, (_, cells_in_row) in enumerate(sorted_rows):
                # Sort cells by column index
                sorted_cells = sorted(cells_in_row, key=lambda x: x[0])
                row_data = [text for _, text in sorted_cells]
                
                if row_idx == 0:
                    headers = row_data
                else:
                    data_rows.append(row_data)
            
            return {
                "headers": headers,
                "rows": data_rows,
                "row_count": len(data_rows),
                "column_count": len(headers) if headers else 0,
            }
            
        except Exception as exc:
            logger.warning("Failed to parse table from cells: %s", exc)
            return None

    def extract_line_items(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tables to line items format
        
        Args:
            tables: List of table dictionaries
            
        Returns:
            List of line items with key-value pairs
        """
        line_items = []
        
        for table in tables:
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            
            if not headers or not rows:
                continue
            
            for row_idx, row in enumerate(rows):
                item = {}
                for col_idx, header in enumerate(headers):
                    if col_idx < len(row):
                        item[header] = row[col_idx]
                
                if item:
                    item["_line_number"] = row_idx + 1
                    item["_table_metadata"] = table.get("metadata", {})
                    line_items.append(item)
        
        return line_items
