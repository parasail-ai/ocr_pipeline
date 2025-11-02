# GitHub Actions CI/CD Setup

This document explains how to set up automated deployments to Azure when you push to the `main` branch.

## Overview

The workflow will automatically:
1. Build a Docker image from your code
2. Push it to Azure Container Registry (ACR)
3. Restart the App Service to pull the new image
4. Run a health check to verify deployment

## Setup Instructions

### Step 1: Add Azure Credentials to GitHub Secrets

1. Go to your GitHub repository: https://github.com/parasail-ai/ocr_pipeline
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `AZURE_CREDENTIALS`
5. Value: Copy and paste the **entire JSON output** below:

```json
{
  "clientId": "df4901ba-06a3-4e2a-97a4-ba4b684d9760",
  "clientSecret": "wOt8Q~J3OUAalTS-G2VfRNGysHznfKulaGSWpc_U",
  "subscriptionId": "91bcb0b9-ba25-474b-b844-37436a53df55",
  "tenantId": "5955392b-bcf0-4c69-833b-ab683fb14a59",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

6. Click **Add secret**

### Step 2: Test the Workflow

**Option A: Push to main branch**
```bash
git add .
git commit -m "Enable automated CI/CD"
git push origin main
```

**Option B: Manual trigger**
1. Go to GitHub → **Actions** tab
2. Select "Build and Deploy to Azure" workflow
3. Click **Run workflow** → **Run workflow**

### Step 3: Monitor Deployment

1. Go to the **Actions** tab in GitHub
2. Click on the running workflow
3. Watch each step complete:
   - ✅ Checkout repository
   - ✅ Log in to Azure
   - ✅ Build and push Docker image to ACR
   - ✅ Restart Azure App Service
   - ✅ Health check

Expected output:
```
✅ Deployment successful!
🌐 Application URL: https://parasail-ocr-pipeline.azurewebsites.net
🐳 Docker image: parasailocrujxbwjwvmweea.azurecr.io/parasail-ocr:latest
📝 Git commit: <commit-sha>
```

## How It Works

### Workflow Triggers
- **Automatic**: Runs on every push to `main` branch
- **Manual**: Can be triggered from GitHub Actions UI

### Build Process
The workflow uses `az acr build` which:
- Builds the Docker image in Azure (no local Docker needed)
- Tags image with both `latest` and the git commit SHA
- Pushes directly to your Azure Container Registry

### Deployment Process
1. App Service automatically detects new `:latest` image
2. Workflow restarts the App Service to force immediate pull
3. Docker container starts with new code
4. Health check verifies successful deployment

## Troubleshooting

### Deployment fails at "Log in to Azure"
- Verify `AZURE_CREDENTIALS` secret is correctly set in GitHub
- Check that the JSON is valid (no extra spaces or line breaks)

### Deployment fails at "Build and push"
- Check that ACR name `parasailocrujxbwjwvmweea` exists
- Verify the service principal has contributor access to the resource group

### App doesn't update after deployment
- Check Azure Portal → Log Stream for errors
- Verify Docker image was pushed: `az acr repository show-tags --name parasailocrujxbwjwvmweea --repository parasail-ocr`
- Manually restart: `az webapp restart --resource-group parasail-ocr-pipeline-rg --name parasail-ocr-pipeline`

### Health check fails
- This is often non-critical if the app works
- Check if `/health` endpoint exists in your FastAPI app
- Visit https://parasail-ocr-pipeline.azurewebsites.net manually to verify

## Security Notes

⚠️ **IMPORTANT**: The Azure credentials above grant contributor access to your resource group. 

**Protect these credentials:**
- ✅ Stored as GitHub Secret (encrypted)
- ❌ Never commit to source control
- ❌ Never share publicly

**To revoke access if compromised:**
```bash
az ad sp delete --id df4901ba-06a3-4e2a-97a4-ba4b684d9760
```

Then create new credentials and update the GitHub secret.

## Manual Deployment (Alternative)

If you prefer to deploy manually instead of using GitHub Actions:

```bash
# Build and push to ACR
az acr build --registry parasailocrujxbwjwvmweea --image parasail-ocr:latest .

# Restart App Service
az webapp restart --resource-group parasail-ocr-pipeline-rg --name parasail-ocr-pipeline
```

## Resources

- **App Service**: https://parasail-ocr-pipeline.azurewebsites.net
- **Azure Portal**: https://portal.azure.com/#@/resource/subscriptions/91bcb0b9-ba25-474b-b844-37436a53df55/resourceGroups/parasail-ocr-pipeline-rg
- **Container Registry**: parasailocrujxbwjwvmweea.azurecr.io
- **Workflow File**: `.github/workflows/deploy.yml`
