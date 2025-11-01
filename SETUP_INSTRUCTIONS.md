# Setup Instructions for OCR Parasail Pipeline

## Prerequisites
- Python 3.10+
- PostgreSQL database
- Azure Blob Storage account
- Parasail API key (optional)

## Installation Steps

### 1. Create Virtual Environment
```bash
cd /Users/matthewcarnali/Desktop/OCR_Parasail_Pipeline

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies
```bash
# Install all requirements
pip install -r requirements.txt

# Optional: Install Docling for advanced table extraction
pip install docling>=0.6.0
```

### 3. Configure Environment Variables
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env  # or use your preferred editor
```

Required environment variables:
```bash
APP_DATABASE_URL=postgresql://user:password@host:port/database
APP_AZURE_STORAGE_CONNECTION_STRING=your_azure_connection_string
APP_AZURE_BLOB_CONTAINER=contracts
APP_PARASAIL_API_KEY=your_parasail_api_key  # Optional
APP_PARASAIL_BASE_URL=https://api.parasail.io/v1
```

### 4. Initialize Database with Alembic

```bash
# Initialize Alembic (first time only)
alembic init alembic

# This creates:
# - alembic/ directory
# - alembic.ini configuration file
```

### 5. Configure Alembic

Edit `alembic/env.py` to import your models:

```python
# Add at the top after imports
from app.db.models import Base
from app.core.config import get_settings

# Update target_metadata
target_metadata = Base.metadata

# Update sqlalchemy.url in config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
```

Edit `alembic.ini` to set the database URL (or use env.py as shown above):
```ini
sqlalchemy.url = postgresql://user:password@host:port/database
```

### 6. Create and Apply Migrations

```bash
# Generate migration for new tables
alembic revision --autogenerate -m "Add API auth and document extractions"

# Review the generated migration in alembic/versions/

# Apply the migration
alembic upgrade head
```

### 7. Run the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 8. Access the Application

- **Web UI**: http://localhost:8000
- **API Documentation (Swagger)**: http://localhost:8000/docs
- **API Reference (Scalar)**: http://localhost:8000/reference

## Testing the New Features

### 1. Create an API Profile and Key

```bash
# Create profile
curl -X POST http://localhost:8000/api/auth/profiles \
  -H "Content-Type: application/json" \
  -d '{"name": "Test App", "email": "test@example.com"}'

# Save the profile ID from response

# Generate API key
curl -X POST http://localhost:8000/api/auth/profiles/{profile_id}/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Key"}'

# IMPORTANT: Save the returned API key - it won't be shown again!
```

### 2. Upload a Document via Base64

```bash
# Encode a test document
BASE64_CONTENT=$(base64 -i test_document.pdf)

# Upload with API key
curl -X POST http://localhost:8000/api/documents/base64 \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test_invoice.pdf",
    "content": "'$BASE64_CONTENT'",
    "content_type": "application/pdf",
    "model_name": "parasail-matt-ocr-1-dots"
  }'

# Save the document_id from response
```

### 3. Check Extraction Results

```bash
# Get all extractions
curl http://localhost:8000/api/documents/{document_id}/extractions

# Get consolidated JSON output
curl http://localhost:8000/api/documents/{document_id}/extractions/json
```

## Troubleshooting

### Database Connection Issues
```bash
# Test database connection
psql -h host -U user -d database

# Check if tables exist
psql -h host -U user -d database -c "\dt"
```

### Migration Issues
```bash
# Check current migration version
alembic current

# View migration history
alembic history

# Downgrade if needed
alembic downgrade -1

# Upgrade to specific version
alembic upgrade <revision_id>
```

### Virtual Environment Issues
```bash
# Deactivate current environment
deactivate

# Remove and recreate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Import Errors
```bash
# Ensure you're in the project root
cd /Users/matthewcarnali/Desktop/OCR_Parasail_Pipeline

# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Development Workflow

### Making Database Changes

1. Modify models in `app/db/models.py`
2. Generate migration: `alembic revision --autogenerate -m "Description"`
3. Review generated migration in `alembic/versions/`
4. Apply migration: `alembic upgrade head`
5. Test changes

### Adding New API Endpoints

1. Create/modify route file in `app/api/routes/`
2. Add Pydantic models in `app/models/`
3. Update router in `app/api/routes/__init__.py`
4. Test endpoint at `/docs`

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## Production Deployment

### Using Docker

```bash
# Build image
docker build -t ocr-pipeline .

# Run container
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name ocr-pipeline \
  ocr-pipeline
```

### Using Azure Container Apps

See `infra/main.bicep` for infrastructure as code deployment.

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Docling Documentation](https://github.com/docling-project/docling)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
