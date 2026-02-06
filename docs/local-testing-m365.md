# Local Testing Guide: M365 Agent SDK (Teams/Copilot)

This guide explains how to test the M365 Agent SDK integration locally before deploying to Azure.

## Prerequisites

- Python 3.11+
- Azure CLI (`az`) installed and logged in
- VS Code with Dev Tunnels extension OR ngrok installed
- An Azure subscription (for Azure AD App Registration)

## Step 1: Install Dependencies

```bash
cd app/backend
pip install microsoft-agents-hosting-fastapi microsoft-agents-authentication-msal microsoft-agents-hosting-core aiohttp
```

Or using uv (after the packages are available):
```bash
uv sync
```

This installs the M365 SDK packages:
- `microsoft-agents-hosting-fastapi` (v0.7.0+)
- `microsoft-agents-authentication-msal` (v0.7.0+)
- `microsoft-agents-hosting-core` (v0.7.0+)
- `microsoft-agents-activity` (v0.7.0+)
- `aiohttp` (required by the SDK)

## Step 2: Create Azure AD App Registration

Even for local testing, you need an Azure AD App Registration because Teams/Copilot validates the bot identity.

### Option A: Use the setup script
```bash
./scripts/setup-m365-bot.sh "Banking Assistant Local" "local"
```

### Option B: Manual creation in Azure Portal
1. Go to **Azure Portal** → **Microsoft Entra ID** → **App registrations**
2. Click **New registration**
3. Name: `Banking Assistant Local`
4. Supported account types: **Accounts in any organizational directory (Multitenant)**
5. Click **Register**
6. Copy the **Application (client) ID**
7. Go to **Certificates & secrets** → **New client secret**
8. Copy the secret value immediately (shown only once)

## Step 3: Configure Environment

Create a `.env` file in `app/backend/`:

```bash
cp .env.dev.example .env
```

Edit `.env` and add your M365 credentials:

```dotenv
# M365 Agent SDK Settings
M365_APP_ID=<your-app-id-from-step-2>
M365_APP_PASSWORD=<your-client-secret-from-step-2>
M365_APP_TENANT_ID=  # Leave empty for multi-tenant
```

## Step 4: Expose Local Endpoint

Teams/Copilot need to reach your local server. Use one of these options:

### Option A: VS Code Dev Tunnels (Recommended)

1. Open VS Code Command Palette (`Ctrl+Shift+P`)
2. Run: **Dev Tunnels: Create Tunnel**
3. Select port `8080` (or your backend port)
4. Choose **Persistent** and **Public** access
5. Copy the tunnel URL (e.g., `https://abc123.devtunnels.ms`)

### Option B: ngrok

```bash
# Install ngrok if needed
# brew install ngrok  # macOS
# snap install ngrok  # Linux

# Start tunnel
ngrok http 8080
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

## Step 5: Create Azure Bot Service (for local testing)

You need an Azure Bot Service even for local testing - it routes messages from Teams to your tunnel.

### Using Azure CLI:

```bash
# Set variables
BOT_NAME="banking-assistant-local"
RESOURCE_GROUP="rg-banking-local"
TUNNEL_URL="https://your-tunnel-url.devtunnels.ms"  # From Step 4
APP_ID="your-m365-app-id"  # From Step 2

# Create resource group
az group create --name $RESOURCE_GROUP --location eastus

# Create bot
az bot create \
    --resource-group $RESOURCE_GROUP \
    --name $BOT_NAME \
    --kind azurebot \
    --sku F0 \
    --app-id $APP_ID \
    --endpoint "${TUNNEL_URL}/api/messages"

# Enable Teams channel
az bot msteams create \
    --resource-group $RESOURCE_GROUP \
    --name $BOT_NAME
```

## Step 6: Start the Backend

```bash
cd app/backend

# Activate virtual environment (if using uv)
source .venv/bin/activate

# Run the server
python -m uvicorn app.main_chatkit_server:app --host 0.0.0.0 --port 8080 --reload
```

The server should start with the M365 router enabled at `/api/messages`.

## Step 7: Test in Teams

### Option A: Upload Teams App Package

1. Update `app/teams-app/manifest.json`:
   - Set `id` to your `M365_APP_ID`
   - Set `bots[0].botId` to your `M365_APP_ID`

2. Create app package:
   ```bash
   cd app/teams-app
   # Create placeholder icons if not present
   convert -size 192x192 xc:blue color.png 2>/dev/null || echo "Create 192x192 color.png manually"
   convert -size 32x32 xc:white outline.png 2>/dev/null || echo "Create 32x32 outline.png manually"
   
   zip -r banking-assistant.zip manifest.json color.png outline.png
   ```

3. Upload to Teams:
   - Open Microsoft Teams
   - Go to **Apps** → **Manage your apps** → **Upload an app**
   - Select **Upload a custom app**
   - Choose `banking-assistant.zip`

### Option B: Use Bot Framework Emulator (Quick Test)

For quick testing without Teams:

1. Download [Bot Framework Emulator](https://github.com/microsoft/BotFramework-Emulator/releases)
2. Open Emulator
3. Click **Open Bot**
4. Enter: `http://localhost:8080/api/messages`
5. Enter your `M365_APP_ID` and `M365_APP_PASSWORD`
6. Click **Connect**

## Step 8: Test Conversations

Once connected, try these messages:

```
Hi
What's my account balance?
Show me recent transactions
Transfer $50 to John
```

The bot should respond with:
- Text messages for queries
- Adaptive Cards for approval requests (transfers)

## Troubleshooting

### "Unauthorized" errors
- Verify `M365_APP_ID` and `M365_APP_PASSWORD` are correct
- Check the Azure AD app hasn't expired
- Ensure the app is multi-tenant or your tenant matches

### Tunnel not working
- Ensure the tunnel is running and accessible
- Try accessing `https://your-tunnel/health` in a browser
- Check firewall settings

### Bot not responding in Teams
- Verify the messaging endpoint in Azure Bot Service matches your tunnel URL
- Check the backend logs for incoming requests
- Ensure the Teams channel is enabled in Azure Bot Service

### "Activity type not supported"
- The bot only handles `message` activities by default
- Other activity types (typing, reactions) are logged but not processed

## Local Testing Checklist

- [ ] Azure AD App Registration created
- [ ] `.env` file configured with M365 credentials
- [ ] Dev Tunnel or ngrok running
- [ ] Azure Bot Service created with tunnel endpoint
- [ ] Teams channel enabled on Bot Service
- [ ] Backend server running on port 8080
- [ ] Teams app package uploaded (or Emulator connected)

## Next Steps

Once local testing is complete:

1. Run `azd provision` to deploy to Azure
2. Update the Bot Service messaging endpoint to the Azure Container App URL
3. Re-upload the Teams app package for production
