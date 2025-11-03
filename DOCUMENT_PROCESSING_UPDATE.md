# Document Processing Pipeline Update

## Summary
Updated the document processing pipeline to disable direct text extraction for DOCX, XLSX, and HTML files. All these document types now go through image conversion followed by OCR processing, ensuring consistency across all document types.

## Changes Made

### 1. Document Converter Service (`app/services/document_converter.py`)

#### Added Detection Methods:
- `is_xlsx(content: bytes)` - Detects Excel XLSX files
- `is_html(content: bytes)` - Detects HTML files

#### Updated Conversion Support:
- `convert_to_images()` now supports DOCX, PPTX, XLSX, and HTML files
- All office document types (DOCX, PPTX, XLSX) and HTML are converted to PDF first using LibreOffice, then converted to images
- Graceful fallback if conversion fails

### 2. Document Processing Task (`app/tasks/processing.py`)

#### Removed Direct Text Extraction:
- Completely removed the text extraction block that used `TextExtractionService`
- No more direct text extraction from DOCX, XLSX, HTML, or CSV files

#### Added Image-Based OCR Processing for All Document Types:
- **PDF**: Splits multi-page PDFs into individual page images
- **PPTX**: Converts slides to images
- **DOCX**: Converts pages to images (NEW)
- **XLSX**: Converts sheets to images (NEW)
- **HTML**: Converts to images (NEW)

#### Processing Flow:
1. Document downloaded from blob storage
2. File type detected using magic bytes
3. Document converted to images (if applicable)
4. Each image/page sent to Parasail OCR
5. Multi-page responses combined into single text output
6. Text used for AI schema generation and data extraction

## Benefits

### Consistency
- All document types now go through the same OCR pipeline
- Uniform processing eliminates inconsistencies between text extraction and OCR

### Quality
- OCR models can see the actual visual layout of documents
- Better handling of complex formatting, tables, and graphics
- Consistent quality regardless of document type

### Simplicity
- Single code path for all document types
- Easier to maintain and debug
- Consistent error handling

## Technical Details

### Document Type Detection
Documents are detected using magic bytes:
- **PDF**: Starts with `%PDF`
- **DOCX**: ZIP archive (`PK`) containing `word/` folder
- **PPTX**: ZIP archive (`PK`) containing `ppt/` folder  
- **XLSX**: ZIP archive (`PK`) containing `xl/` folder
- **HTML**: Contains `<html`, `<!doctype html`, or `<head` tags

### Conversion Process
1. **DOCX/PPTX/XLSX/HTML**: 
   - Saved to temporary file
   - Converted to PDF using LibreOffice (or docx2pdf on Windows/Mac)
   - PDF converted to images using PyMuPDF at 200 DPI
   
2. **PDF**: 
   - Directly converted to images using PyMuPDF at 200 DPI

### Multi-Page Handling
- Single-page documents: Processed directly
- Multi-page documents: Each page processed individually, results combined
- Combined text stored in `combined_text` field

## Dependencies

### Required:
- `PyMuPDF` (fitz) - PDF rendering
- `LibreOffice` - Office document conversion (Linux/Azure)
- `docx2pdf` - Office document conversion (Windows/Mac, optional)

### Configuration:
No configuration changes required. The system automatically detects available conversion tools and uses the appropriate method.

## Backward Compatibility

### Preserved:
- All API endpoints remain unchanged
- Database schema unchanged
- Existing processed documents not affected

### Changed:
- New document uploads will use image-based OCR
- Text extraction quality may improve for complex documents
- Processing time may increase slightly due to image conversion

## Testing Recommendations

1. **Upload Test Documents**:
   - Multi-page PDF
   - PowerPoint presentation (PPTX)
   - Word document (DOCX)
   - Excel spreadsheet (XLSX)
   - HTML file

2. **Verify**:
   - All documents convert successfully to images
   - OCR extracts text correctly
   - Multi-page documents combine text properly
   - Error handling works for unsupported formats

3. **Performance**:
   - Monitor processing times
   - Check memory usage during conversion
   - Verify LibreOffice availability in production

## Rollback Plan

If issues arise, revert these commits:
1. `app/services/document_converter.py` - Add back original conversion support
2. `app/tasks/processing.py` - Re-enable direct text extraction block

## Date
November 2, 2025
