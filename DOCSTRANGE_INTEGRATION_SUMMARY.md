# DocStrange Preprocessing Integration Summary

## Overview
Successfully integrated DocStrange preprocessing for office documents (DOCX, PPTX, XLSX, HTML, CSV) into the OCR pipeline.

## Implementation Details

### 1. Frontend Changes (index.html)

#### File Validation
- **Added MIME types**:
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (DOCX)
  - `application/vnd.openxmlformats-officedocument.presentationml.presentation` (PPTX)
  - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (XLSX)
  - `text/html` (HTML)
  - `text/csv` (CSV)

- **Added file extensions**: `.docx`, `.pptx`, `.xlsx`, `.html`, `.htm`, `.csv`

- **Updated validation logic**: Checks both MIME type AND file extension for compatibility

- **Updated error messages**: Now mentions all supported file types

#### Preprocessing Dropdown
- Added new option: `<option value="docstrange">DocStrange (PDF, DOCX, PPTX, XLSX, HTML, CSV)</option>`

#### Auto-Selection Logic
- When user selects office documents (DOCX, PPTX, XLSX, HTML, CSV), the system:
  1. Automatically sets `preprocessingSelect.value = 'docstrange'`
  2. Shows info message: "DocStrange preprocessing auto-selected for office document"
  3. Auto-hides message after 3 seconds

#### Form Submission
- Form now sends `preprocessing` parameter with formData
- Reset button includes preprocessing dropdown reset

### 2. Backend Changes (documents.py)

#### Upload Endpoint
- Added `preprocessing: str = Form("automatic")` parameter
- Stored preprocessing choice in `document.details`
- Passed preprocessing to background task
- Updated logging to include preprocessing method

#### JSON Extraction Endpoint
- Updated OCR text preference order: **docstrange > parasail > docling**
- Uses `next()` generator for efficient content lookup

### 3. DocStrange Service (docstrange_processor.py)

Created new service wrapper: `app/services/docstrange_processor.py`

```python
class DocStrangeProcessor:
    """Wrapper around docstrange library for document preprocessing"""
    
    def __init__(self):
        # Initializes docstrange library
        # Raises RuntimeError if not installed
    
    def is_supported_file(self, filename: str) -> bool:
        # Checks if file type is supported
        # Returns True for: PDF, DOCX, PPTX, XLSX, HTML, CSV
    
    def process_document(self, file_path: str | Path) -> dict[str, Any]:
        # Processes document with DocStrange
        # Returns:
        #   - markdown: extracted markdown text
        #   - data: structured data
        #   - tables: extracted tables
```

### 4. Processing Pipeline (processing.py)

#### Task Signature Updated
- Added `preprocessing: str = "automatic"` parameter to `process_document_task`

#### DocStrange Preprocessing Flow
1. **Runs BEFORE OCR** when `preprocessing == "docstrange"`
2. Saves file to temp location
3. Updates document status to "preprocessing"
4. Calls `DocStrangeProcessor.process_document()`
5. Extracts markdown text
6. Stores in `docstrange_markdown` variable
7. Cleans up temp file

#### Error Handling
- Catches exceptions during DocStrange processing
- Updates status to "preprocessing_failed" with error details
- Logs full exception traceback

#### Text Priority
- **Extraction priority**: `docstrange_markdown > parasail_text > docling_text`
- Used as `base_text` for:
  - Document classification
  - Schema generation
  - Key-value extraction

#### Content Storage
- Stores DocStrange output with `source="docstrange"` in `document_contents` table
- Stored alongside parasail and docling content

### 5. Staging Display (staging.html)

#### OCR Text Display
- **Preference order**: docstrange > parasail > docling
- Updated in `updateUI()` function

#### JSON Output Tab
- Updated to prefer docstrange content in OCR results
- Shows source type in output

## File Changes Summary

| File | Changes |
|------|---------|
| `app/templates/index.html` | Updated file validation, added preprocessing dropdown, auto-selection logic |
| `app/api/routes/documents.py` | Added preprocessing parameter, updated task calls, OCR preference |
| `app/services/docstrange_processor.py` | **NEW** - DocStrange service wrapper |
| `app/tasks/processing.py` | Integrated preprocessing flow, updated text priority |
| `app/templates/staging.html` | Updated OCR display preference, JSON output |

## Processing Flow

```
User uploads office document (.docx, .pptx, etc.)
    ↓
Frontend auto-selects "docstrange" preprocessing
    ↓
Upload endpoint stores preprocessing choice
    ↓
Background task starts
    ↓
Document downloaded from blob storage
    ↓
DocStrange preprocessing (if selected)
    - Saves to temp file
    - Processes with docstrange library
    - Extracts markdown, tables, data
    - Stores in document_contents (source="docstrange")
    ↓
Parasail OCR (if model selected)
    - Runs on original file
    - Stores in document_contents (source="parasail")
    ↓
Document classification & schema generation
    - Uses docstrange output as base_text
    ↓
Display results
    - Prefers docstrange over parasail over docling
```

## Testing Checklist

- [ ] Upload DOCX file - verify auto-selection of DocStrange
- [ ] Upload PPTX file - verify auto-selection of DocStrange
- [ ] Upload XLSX file - verify auto-selection of DocStrange
- [ ] Upload HTML file - verify auto-selection of DocStrange
- [ ] Upload CSV file - verify auto-selection of DocStrange
- [ ] Upload PDF file - verify no auto-selection (user choice)
- [ ] Verify preprocessing parameter saved in document.details
- [ ] Verify DocStrange content stored with source="docstrange"
- [ ] Verify OCR text display shows docstrange content
- [ ] Verify JSON output prefers docstrange content
- [ ] Test error handling when DocStrange fails
- [ ] Verify extraction uses docstrange text as base_text

## Dependencies

**Required**: Install docstrange library
```bash
pip install docstrange
```

## Configuration

No additional configuration needed. The integration uses:
- Default preprocessing: `"automatic"`
- Auto-selection for office documents
- Fallback to parasail/docling if docstrange not available

## Notes

1. **DocStrange runs BEFORE OCR**: This allows preprocessing of office documents before OCR processing
2. **Content preference order**: docstrange > parasail > docling throughout the system
3. **Error resilience**: If DocStrange fails, processing continues with status update
4. **Storage**: All content sources stored separately in document_contents table
5. **Backward compatibility**: Existing documents without docstrange content work unchanged
