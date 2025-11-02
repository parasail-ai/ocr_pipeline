# Text Extraction Integration Summary

## Overview
Integrated direct text extraction for structured document formats (HTML, CSV, DOCX, XLSX, PPTX, TXT, JSON, XML) to skip OCR and pass extracted text/JSON directly to schema extraction service.

## Changes Made

### 1. Created `app/services/text_extractor.py`
A new service that extracts text from structured documents without requiring OCR:

**Key Features:**
- **`can_extract_text(content_type, filename)`** - Detects if a file can skip OCR
- **`extract_text(file_bytes, content_type, filename)`** - Extracts text and structured data

**Supported Formats:**
- **CSV**: Parses into rows/columns with DictReader format
- **HTML**: Extracts clean text using BeautifulSoup
- **DOCX**: Extracts paragraphs and tables from Word documents
- **XLSX**: Extracts all sheets and data from Excel
- **PPTX**: Extracts text from PowerPoint slides
- **TXT**: Plain text extraction with multiple encoding support
- **JSON**: Parses and formats JSON data
- **XML**: Basic XML text extraction

**Return Format:**
```python
{
    "text": "extracted text content",
    "structured_data": {...},  # Parsed data structure
    "format": "csv"  # Detected format type
}
```

### 2. Modified `app/tasks/processing.py`
Integrated TextExtractionService into the document processing pipeline:

**Processing Flow:**
1. **Download** document from blob storage
2. **Check format**: Use `can_extract_text()` to detect structured formats
3. **Extract or OCR**:
   - **Structured files** → Direct text extraction (no OCR)
   - **Images/PDFs** → Parasail OCR (existing flow)
4. **Store results**: Save extracted text and structured data
5. **Schema extraction**: AI processes the text (same for both paths)

**Key Code Changes:**
```python
# Check if we can extract text directly without OCR
text_extractor = TextExtractionService()
if text_extractor.can_extract_text(content_type, filename):
    # Extract text directly - skip OCR
    extraction_result = text_extractor.extract_text(...)
    parasail_text = extraction_result.get("text", "")
    
    # Store structured data if available
    if structured_data:
        # Save as DocumentExtraction
```

### 3. Updated `requirements.txt`
Added dependencies for text extraction:
```
beautifulsoup4>=4.12.0,<5.0  # HTML parsing
python-docx>=1.1.0,<2.0      # DOCX extraction
openpyxl>=3.1.0,<4.0         # XLSX extraction
python-pptx>=0.6.23,<1.0     # PPTX extraction
```

## Benefits

### 1. **Cost Savings**
- No OCR API calls for structured documents
- No token usage for files that already have text

### 2. **Speed Improvements**
- Direct text extraction is much faster than OCR
- No image conversion required

### 3. **Better Accuracy**
- Structured formats retain their original text (no OCR errors)
- CSV/Excel data maintains column structure
- JSON/HTML preserve formatting

### 4. **Schema Extraction Ready**
- Extracted text is passed to AI schema generation
- Structured data available for enhanced processing
- Same downstream pipeline for all document types

## Processing Status Flow

### For Structured Documents (CSV, HTML, DOCX, etc.):
1. `downloading` → Fetching from blob storage
2. `downloaded` → File downloaded successfully
3. `extracting_text` → Direct text extraction in progress
4. `processing` → Text extracted, running schema extraction
5. `processed` → Complete

### For Images/PDFs:
1. `downloading` → Fetching from blob storage
2. `downloaded` → File downloaded successfully
3. `ocr_processing` → Running Parasail OCR
4. `processing` → OCR complete, running schema extraction
5. `processed` → Complete

## Database Storage

### DocumentContent Table
- **Source**: `"text_extraction"` for structured documents
- **Text**: Extracted text content
- **Metadata**: Includes text length

### DocumentExtraction Table
- **Type**: `"structured_data"`
- **Source**: `"text_extraction"`
- **Data**: Parsed structured content (CSV rows, JSON objects, etc.)
- **Metadata**: Format type, text length

## Error Handling

### Graceful Fallbacks:
- If text extraction fails → Document status set to "error"
- If optional libraries missing → Returns empty result with error message
- Multiple encoding attempts for text files (UTF-8, Latin-1, CP1252, ISO-8859-1)

### Dependencies:
All extraction methods check for required libraries and fail gracefully if not installed:
- BeautifulSoup4 for HTML
- python-docx for DOCX
- openpyxl for XLSX
- python-pptx for PPTX

## Testing

### Test Cases to Verify:

1. **CSV Upload**:
   - Upload a CSV file
   - Verify status goes: downloading → downloaded → extracting_text → processing → processed
   - Check logs for "extracting text directly without OCR"
   - Verify structured_data contains parsed rows

2. **HTML Upload**:
   - Upload HTML file
   - Verify clean text extraction (no HTML tags)
   - Check structured_data contains title and raw HTML

3. **DOCX Upload**:
   - Upload Word document
   - Verify paragraphs extracted
   - Check if tables are captured in structured_data

4. **XLSX Upload**:
   - Upload Excel file
   - Verify all sheets extracted
   - Check structured_data contains sheet names and data

5. **PDF Upload** (should still use OCR):
   - Upload PDF
   - Verify status includes "ocr_processing"
   - Confirm Parasail OCR is still used

## Configuration

No configuration changes required. The system automatically detects file formats and chooses the appropriate extraction method.

## Monitoring

### Log Messages to Watch:
```
"Document {filename} is a structured format - extracting text directly without OCR"
"Text extraction completed for {filename}: format={format_type}, text_length={length}"
"Extracted text directly and stored {X} characters"
```

### Error Indicators:
```
"Text extraction failed for document {id}"
"extraction_method" missing from document details
```

## Future Enhancements

1. **Add more formats**: RTF, ODT, PDF with text layer
2. **Enhanced CSV parsing**: Auto-detect delimiters, handle malformed CSV
3. **Table extraction**: Better table structure preservation from DOCX/HTML
4. **Metadata extraction**: File properties, author, creation date
5. **Content validation**: Verify extracted text quality before proceeding

## Backward Compatibility

✅ **Fully backward compatible**:
- Existing image/PDF processing unchanged
- OCR flow still works identically
- No database schema changes required
- No API changes needed

All existing documents will continue to process through OCR. Only new uploads of structured formats will use the direct text extraction path.
