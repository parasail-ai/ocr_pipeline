# Feature Roadmap - OCR Parasail Pipeline

## Overview
This document outlines the comprehensive feature expansion plan for the OCR Parasail Pipeline application.

## Current Status
- ✅ Database configured with PostgreSQL + asyncpg
- ✅ Azure Blob Storage integration
- ✅ Basic document upload/delete functionality
- ✅ Docling integration for table extraction
- ✅ Basic schema builder UI
- ✅ API authentication with API keys
- ⚠️ Parasail OCR integration (needs enhancement)
- ⚠️ Schema auto-generation (not implemented)
- ⚠️ Performance tracking (not implemented)

## Phase 1: Core OCR & Schema Generation (Priority: HIGH)

### 1.1 Fix Parasail API Integration
**Current Issue:** Upload endpoint may not be correctly calling Parasail API
**Tasks:**
- [ ] Update Parasail service to use correct API format (chat.completions or responses)
- [ ] Test with provided API key: `psk-parasail94Cl-qEFxp2RvEND7LiaUpBM7`
- [ ] Handle base64 document upload to Parasail
- [ ] Parse response and extract OCR text properly
- [ ] Add error handling and logging

### 1.2 Auto-Generate Schemas from OCR Output
**Goal:** Automatically create key-value schemas based on OCR extraction
**Tasks:**
- [ ] Create schema auto-generation service using LLM
- [ ] Analyze OCR output to identify document structure
- [ ] Extract key-value pairs automatically
- [ ] Generate schema definition with appropriate field types
- [ ] Map extracted values to schema fields
- [ ] Store both schema and extracted values

### 1.3 Add Response Time Tracking
**Goal:** Track latency and performance metrics for each OCR call
**Tasks:**
- [ ] Add timing metadata to DocumentOcrResult model
- [ ] Track: start_time, end_time, duration_ms, model_latency_ms
- [ ] Store in database for analytics
- [ ] Display in document detail view

## Phase 2: UI Reorganization (Priority: HIGH)

### 2.1 Create Staging Page After Upload
**Goal:** After upload, redirect to a staging page showing document processing
**Tasks:**
- [ ] Create `/staging/{document_id}` route/page
- [ ] Show document preview (PDF/image rendering)
- [ ] Display real-time processing status
- [ ] Show OCR extraction results as they arrive
- [ ] Display auto-generated schema with extracted values
- [ ] Allow schema editing before saving
- [ ] Provide "Save to Documents" or "Discard" actions

### 2.2 Move Documents to Separate Page
**Goal:** Documents should not be on homepage, but in dedicated section
**Tasks:**
- [ ] Create `/documents` page
- [ ] Implement folder/tree structure for organization
- [ ] Add folder creation and document organization
- [ ] Update navigation menu
- [ ] Keep homepage simple with just upload form

### 2.3 Document Folder Structure
**Goal:** Organize documents in folders/categories
**Tasks:**
- [ ] Add `folder_id` and `folder_path` to Document model
- [ ] Create Folder model (id, name, parent_id, path)
- [ ] Add folder CRUD operations
- [ ] Update UI with folder tree navigation
- [ ] Allow drag-and-drop to move documents between folders

## Phase 3: Advanced Features (Priority: MEDIUM)

### 3.1 Schema Management with Key Remapping
**Goal:** Allow renaming schema keys for display purposes
**Tasks:**
- [ ] Create `/schemas` page
- [ ] List all saved schemas
- [ ] Add schema editor with key remapping
- [ ] Add "display_name" field to schema fields
- [ ] Update UI to show display names instead of keys
- [ ] Allow editing schema metadata

### 3.2 JSON Sidecar Downloads
**Goal:** Generate downloadable JSON file for each document
**Tasks:**
- [ ] Create JSON export service
- [ ] Generate comprehensive JSON with:
  - Document metadata
  - OCR text
  - Extracted tables
  - Line items
  - Schema values
  - Classifications
- [ ] Add download button in document view
- [ ] Store JSON as sidecar in blob storage
- [ ] Add API endpoint: GET `/documents/{id}/export/json`

### 3.3 Dynamic Model Management
**Goal:** Allow users to add custom OCR models dynamically
**Tasks:**
- [ ] Create OcrModel table (id, name, endpoint, api_key, provider, config)
- [ ] Create `/models` management page
- [ ] Add model CRUD operations
- [ ] Update document upload to list available models
- [ ] Support multiple providers (Parasail, OpenAI, custom endpoints)
- [ ] Encrypt API keys in database

## Phase 4: Analytics Dashboard (Priority: MEDIUM)

### 4.1 Performance Dashboard
**Goal:** Visualize OCR performance and usage metrics
**Tasks:**
- [ ] Create `/analytics` page
- [ ] Display charts/graphs:
  - Documents processed over time
  - Average processing time by model
  - Success/error rates
  - Storage usage
  - API cost estimates
- [ ] Add date range filters
- [ ] Export analytics to CSV

### 4.2 Model Comparison
**Goal:** Compare performance of different OCR models
**Tasks:**
- [ ] Show side-by-side model performance
- [ ] Metrics: latency, accuracy estimate, cost
- [ ] Add model usage statistics
- [ ] Recommend optimal model based on document type

## Phase 5: Additional Enhancements (Priority: LOW)

### 5.1 Batch Upload
- [ ] Support multiple file uploads at once
- [ ] Queue processing for batch jobs
- [ ] Show batch progress

### 5.2 Document Search
- [ ] Full-text search across OCR content
- [ ] Filter by document type, schema, date
- [ ] Advanced search with multiple criteria

### 5.3 Collaboration Features
- [ ] Share documents with other users
- [ ] Add comments/annotations
- [ ] Track document history/versions

### 5.4 Export Options
- [ ] Export to CSV (for tabular data)
- [ ] Export to Excel
- [ ] Bulk export selected documents

## Database Schema Changes Required

### New Tables
```sql
-- Folders
CREATE TABLE folders (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES folders(id),
    path TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- OcrModels
CREATE TABLE ocr_models (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    provider VARCHAR(100),
    endpoint TEXT,
    api_key_encrypted TEXT,
    config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Document metadata additions
ALTER TABLE documents ADD COLUMN folder_id UUID REFERENCES folders(id);
ALTER TABLE documents ADD COLUMN json_export_path TEXT;

-- OCR result timing
ALTER TABLE document_ocr_results ADD COLUMN started_at TIMESTAMP;
ALTER TABLE document_ocr_results ADD COLUMN completed_at TIMESTAMP;
ALTER TABLE document_ocr_results ADD COLUMN duration_ms INTEGER;
ALTER TABLE document_ocr_results ADD COLUMN model_latency_ms INTEGER;

-- Schema field display names
ALTER TABLE schema_definitions ADD COLUMN field_display_names JSONB;
```

## API Endpoints to Add

### Models
- GET /api/models - List available OCR models
- POST /api/models - Add new model
- PUT /api/models/{id} - Update model
- DELETE /api/models/{id} - Delete model

### Folders
- GET /api/folders - List folders
- POST /api/folders - Create folder
- PUT /api/folders/{id} - Update folder
- DELETE /api/folders/{id} - Delete folder
- PUT /api/documents/{id}/folder - Move document to folder

### Export
- GET /api/documents/{id}/export/json - Export document as JSON
- GET /api/documents/{id}/export/csv - Export tables as CSV
- POST /api/documents/bulk-export - Export multiple documents

### Analytics
- GET /api/analytics/summary - Overall statistics
- GET /api/analytics/models - Model performance metrics
- GET /api/analytics/usage - Usage over time

## Implementation Priority Order

1. **CRITICAL (Do First)**
   - Fix Parasail API integration and upload error
   - Add response time tracking
   - Create staging page after upload

2. **HIGH (Do Next)**
   - Auto-generate schemas from OCR output
   - Move documents to separate page
   - JSON sidecar downloads

3. **MEDIUM (After Core Features)**
   - Schema management with key remapping
   - Dynamic model management
   - Folder structure
   - Analytics dashboard

4. **LOW (Future Enhancements)**
   - Batch upload
   - Search
   - Collaboration
   - Additional exports

## Estimated Timeline

- Phase 1 (Core OCR): 2-3 days
- Phase 2 (UI Reorganization): 3-4 days  
- Phase 3 (Advanced Features): 4-5 days
- Phase 4 (Analytics): 2-3 days

**Total: 11-15 days for full implementation**

## Next Steps

Please review this roadmap and let me know:
1. Which phase/features should I prioritize first?
2. Are there any features missing that you need?
3. Are there any features we can defer or skip?

I recommend starting with Phase 1.1 (Fix Parasail API) since that's blocking uploads.
