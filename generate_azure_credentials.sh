#!/bin/bash
# Generate Azure credentials for GitHub Actions

echo "🔧 Generating Azure Service Principal credentials for GitHub Actions"
echo ""
echo "This will create a service principal and output the credentials in the correct format."
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first:"
    echo "   https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login check
echo "Checking Azure login status..."
if ! az account show &> /dev/null; then
    echo "Please login to Azure first:"
    az login
fi

# Get current subscription
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)

echo ""
echo "📋 Current subscription:"
echo "   Name: $SUBSCRIPTION_NAME"
echo "   ID: $SUBSCRIPTION_ID"
echo ""

# Resource group
RESOURCE_GROUP="parasail-ocr-pipeline-rg"

echo "Creating service principal with contributor role..."
echo ""

# Create service principal
SP_OUTPUT=$(az ad sp create-for-rbac \
  --name "parasail-ocr-github-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Failed to create service principal:"
    echo "$SP_OUTPUT"
    exit 1
fi

echo "✅ Service principal created successfully!"
echo ""
echo "=================================================="
echo "📋 COPY THIS JSON TO GITHUB SECRET:"
echo "=================================================="
echo ""
echo "$SP_OUTPUT" | jq '.'
echo ""
echo "=================================================="
echo ""
echo "📝 Instructions:"
echo "1. Copy the JSON above (everything between the braces {})"
echo "2. Go to: https://github.com/parasail-ai/ocr_pipeline/settings/secrets/actions"
echo "3. Find or create secret named: AZURE_CREDENTIALS"
echo "4. Paste the JSON (make sure it's valid JSON with no extra spaces/newlines)"
echo "5. Save the secret"
echo ""
echo "⚠️  IMPORTANT: The JSON must be exactly as shown above - no extra text!"
echo ""
