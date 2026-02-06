#!/bin/bash
# =============================================================================
# M365 Agent SDK - Azure AD App Registration Setup Script
# =============================================================================
# This script creates the Azure AD App Registration required for the M365 Agent SDK.
# Azure AD Apps cannot be created via Bicep (Azure AD is not an ARM resource).
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Appropriate permissions to create Azure AD applications
#
# Usage:
#   ./scripts/setup-m365-bot.sh [APP_NAME] [ENVIRONMENT]
#
# Example:
#   ./scripts/setup-m365-bot.sh "Banking Assistant Bot" "dev"
# =============================================================================

set -e

# Configuration
APP_NAME="${1:-Banking Assistant Bot}"
ENVIRONMENT="${2:-dev}"
FULL_APP_NAME="${APP_NAME} - ${ENVIRONMENT}"

echo "=============================================="
echo "M365 Agent SDK - Azure AD App Registration"
echo "=============================================="
echo "App Name: ${FULL_APP_NAME}"
echo ""

# Check if logged in
echo "Checking Azure CLI login status..."
az account show > /dev/null 2>&1 || {
    echo "Error: Not logged in to Azure CLI. Please run 'az login' first."
    exit 1
}

TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Tenant ID: ${TENANT_ID}"
echo ""

# Create the Azure AD App Registration
echo "Creating Azure AD App Registration..."
APP_RESULT=$(az ad app create \
    --display-name "${FULL_APP_NAME}" \
    --sign-in-audience "AzureADMultipleOrgs" \
    --query "{appId:appId, id:id}" \
    -o json)

APP_ID=$(echo $APP_RESULT | jq -r '.appId')
OBJECT_ID=$(echo $APP_RESULT | jq -r '.id')

echo "App ID (Client ID): ${APP_ID}"
echo "Object ID: ${OBJECT_ID}"
echo ""

# Create a client secret
echo "Creating client secret..."
SECRET_RESULT=$(az ad app credential reset \
    --id "${APP_ID}" \
    --display-name "M365 Agent SDK Secret" \
    --years 2 \
    --query "{password:password}" \
    -o json)

APP_PASSWORD=$(echo $SECRET_RESULT | jq -r '.password')

echo ""
echo "=============================================="
echo "SUCCESS! Azure AD App Registration Created"
echo "=============================================="
echo ""
echo "Save these values securely - you'll need them for configuration:"
echo ""
echo "  M365_APP_ID=${APP_ID}"
echo "  M365_APP_PASSWORD=${APP_PASSWORD}"
echo "  M365_APP_TENANT_ID=${TENANT_ID}"
echo ""
echo "=============================================="
echo "Next Steps:"
echo "=============================================="
echo ""
echo "1. Add these environment variables to your .env file or Azure Key Vault"
echo ""
echo "2. Deploy the Azure Bot Service using azd:"
echo "   azd provision"
echo ""
echo "3. Update the messaging endpoint in Azure Bot Service:"
echo "   - Go to Azure Portal > Bot Services > ${FULL_APP_NAME}"
echo "   - Set Messaging endpoint to: https://<your-backend-url>/api/messages"
echo ""
echo "4. Create Teams App Package:"
echo "   - Update app/teams-app/manifest.json with the App ID"
echo "   - Create icons (color.png 192x192, outline.png 32x32)"
echo "   - Zip the manifest and icons"
echo "   - Upload to Teams Admin Center or M365 Admin Center"
echo ""
echo "=============================================="

# Save to .env.m365 file for convenience
ENV_FILE=".env.m365"
echo "Saving configuration to ${ENV_FILE}..."
cat > "${ENV_FILE}" << EOF
# M365 Agent SDK Configuration
# Generated on $(date)
# App Name: ${FULL_APP_NAME}

M365_APP_ID=${APP_ID}
M365_APP_PASSWORD=${APP_PASSWORD}
M365_APP_TENANT_ID=${TENANT_ID}
EOF

echo "Configuration saved to ${ENV_FILE}"
echo ""
echo "Done!"
