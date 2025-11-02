# Deployment Guide

## Quick Deploy to Azure (Manual)

The easiest way to deploy is using Azure CLI directly:

### Prerequisites
- Azure CLI installed: `az --version`
- Logged in: `az login`

### Deploy Command
```bash
# From the project root directory
az webapp up \
  --name parasail-ocr-pipeline \
  --resource-group parasail-ocr-pipeline-rg \
  --runtime "PYTHON:3.11" \
  --sku B1 \
  --location eastus
```

This command will:
1. Package your application
2. Upload to Azure
3. Install dependencies from requirements.txt
4. Start the application

### After Deployment

Run database migrations:
```bash
# SSH into the app service or use Kudu console
# https://parasail-ocr-pipeline.scm.azurewebsites.net/

cd /home/site/wwwroot
source antenv/bin/activate  # or antenv3.11/bin/activate
alembic upgrade head
```

### Manual Deployment Steps

1. **Make your code changes locally**
2. **Test locally:**
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```
3. **Commit and push to GitHub:**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin main
   ```
4. **Deploy to Azure:**
   ```bash
   az webapp up --name parasail-ocr-pipeline --resource-group parasail-ocr-pipeline-rg
   ```

## GitHub Actions (Automatic Deployment)

### Fix the Publish Profile Secret

1. **Download fresh publish profile:**
   - Go to: https://portal.azure.com
   - Find: `parasail-ocr-pipeline` App Service
   - Click: **"Get publish profile"** (top menu)
   - Save the `.PublishSettings` file

2. **Update GitHub Secret:**
   - Go to: https://github.com/parasail-ai/ocr_pipeline/settings/secrets/actions
   - Click on `AZURE_WEBAPP_PUBLISH_PROFILE` (or create new)
   - Click **"Update secret"**
   - Open the `.PublishSettings` file in a text editor
   - **Copy the entire XML content** (all of it)
   - **Paste into the secret value box**
   - Click **"Update secret"**

3. **Verify:**
   - Make a small change and push to main
   - Check: https://github.com/parasail-ai/ocr_pipeline/actions
   - Deployment should succeed

### Troubleshooting

**401 Unauthorized Error:**
- Publish profile has expired
- Download a fresh one from Azure Portal
- Update the GitHub secret

**Deployment hangs:**
- Check App Service logs in Azure Portal
- May need to restart the app service manually

**Database errors:**
- Run `alembic upgrade head` via SSH/Kudu console

## Quick Reference

- **App URL:** https://parasail-ocr-pipeline.azurewebsites.net
- **Kudu Console:** https://parasail-ocr-pipeline.scm.azurewebsites.net
- **GitHub Actions:** https://github.com/parasail-ai/ocr_pipeline/actions
- **Azure Portal:** https://portal.azure.com

## Environment Variables

Make sure these are set in Azure App Service → Configuration → Application settings:

```
DATABASE_URL=<your-postgres-connection-string>
AZURE_STORAGE_CONNECTION_STRING=<your-blob-storage-connection>
PARASAIL_API_KEY=<your-parasail-api-key>
```
