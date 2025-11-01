# Parasail OCR Pipeline

FastAPI-based web application for ingesting contract documents, storing them in Azure Blob Storage, and orchestrating OCR extraction and schema management. Designed to align with Material Design 3 principles and deploy to Azure App Service.

## Features

- Upload contracts via Material 3-inspired interface with real-time status updates.
- Persist file metadata and processing status in PostgreSQL (Azure Database for PostgreSQL).
- Store raw documents in Azure Blob Storage with background Docling extraction scaffolding.
- Parasail OCR integration wired for OpenAI-compatible API key usage with selectable models.
- Persist OCR text fragments and classification suggestions for each document.
- Schema builder API and UI for defining reusable key-value mappings and reapplying them to documents.
- Automatic document-type heuristics suggest schemas and fields when none is selected.
- Swagger/OpenAPI documentation automatically exposed at `/docs` and compatible with Scalar.
- GitHub Actions workflow for CI/CD into Azure App Service.

## Local Development

1. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   # Optional Docling integration
   pip install 'docling>=0.6.0'
   ```

2. **Configure environment**
   - Copy `.env.example` to `.env` and update values, including:
     - `APP_DATABASE_URL`
     - `APP_PARASAIL_API_KEY`
     - `APP_AZURE_STORAGE_CONNECTION_STRING` *or* `APP_AZURE_STORAGE_ACCOUNT_URL`

3. **Initialize database schema**
   ```bash
   python app/db/init_db.py
   ```

4. **Run the API**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Open the UI**
- Navigate to `http://localhost:8000/` for the Material 3 front end.
- API docs available at `http://localhost:8000/docs` or compatible with [Scalar](https://scalar.com/).
- The `Documents` section shows current uploads, while the `Document History` table surfaces prior ingests along with detected types and schema selections.

## Project Structure

```
app/
  api/        # FastAPI routers for documents and schemas
  core/       # Configuration management
  db/         # SQLAlchemy models and session helpers
  services/   # Azure Blob, Docling, Parasail, heuristic classifier
  tasks/      # Background processing tasks
  templates/  # Material 3-aligned HTML template
  static/     # CSS assets
```

### Notable API Routes

- `POST /api/documents` – upload a document, optionally specifying an OCR model and a saved schema.
- `GET /api/documents/{id}` – retrieve full document detail, including OCR outputs, contents, and classifications.
- `GET /api/documents/{id}/classifications` – inspect heuristic suggestions for document type and schema.
- `POST /api/documents/{id}/schemas` – apply a named schema with extracted values.
- `GET /api/schemas` – list saved schemas (filterable by category).

## Azure Infrastructure

Infrastructure is defined via `infra/main.bicep` to provision:
- Azure Storage Account + `contracts` container.
- Linux App Service Plan + Web App (`parasail-ocr-pipeline`).
- System assigned managed identity with app settings pre-populated.

### Deploying the Bicep Template

```bash
# Authenticate and select subscription
az login
az account set --subscription "<subscription-id>"

# Create resource group if it does not exist
az group create --name parasail-ocr-pipeline-rg --location eastus

# Deploy infrastructure
az deployment group create \
  --resource-group parasail-ocr-pipeline-rg \
  --template-file infra/main.bicep \
  --parameters \
      storageAccountName=parasailocrstorage \
      databaseConnection='postgresql://dbadmin:Warbiscuit511!@azure-databoard-db.postgres.database.azure.com/ocr?sslmode=require' \
      parasailApiKey='psk-parasailcv6D-vzSrt6rj4t2co8iTmRcc'
```

> **Note:** Storage account names must be globally unique. Adjust `storageAccountName` and resource group names as needed.

After deployment, note the connection string surfaced in the outputs. You can override or remove `APP_AZURE_STORAGE_CONNECTION_STRING` if using managed identity/SAS tokens later.

## GitHub Actions Deployment

The workflow `.github/workflows/deploy.yml` packages the application and deploys it to Azure App Service on every push to `main`.

Configure repository secrets:
- `AZURE_WEBAPP_PUBLISH_PROFILE`: Publish profile XML exported from the Azure Portal for `parasail-ocr-pipeline`.

The workflow vendors Python dependencies into `.python_packages/lib/site-packages` before zipping the artifact so Azure App Service can run the app without rebuilding dependencies on each deployment.

Optional environment variables for configuration can be set in the App Service configuration blade or through infrastructure templates.

## Parasail OCR Models

The Parasail OCR client (`app/services/parasail.py`) is preconfigured for the following models:
- `parasail-matt-ocr-1-dots`
- `parasail-matt-ocr-2-deepseekocr`
- `parasail-mattc-ocr-4-lighton`

Update `APP_PARASAIL_DEFAULT_MODEL` in App Service settings or `.env` to switch defaults.

## Future Enhancements

- Integrate Parasail OCR responses into the document processing pipeline.
- Persist Docling extraction outputs into relational tables for richer querying.
- Add schema application endpoints and UI to map OCR output to structured objects.
- Introduce Queue-based background processing (e.g., Azure Storage Queues or Service Bus).
- Harden CI with unit/integration tests once models are available.
