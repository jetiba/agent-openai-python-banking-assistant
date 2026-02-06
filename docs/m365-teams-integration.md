# M365 Agent SDK - Teams Integration

This document describes the implementation of Microsoft Teams channel support for the Banking Assistant using the M365 Agent SDK.

## Overview

The M365 Agent SDK integration enables the Banking Assistant to receive and respond to messages from Microsoft Teams (and potentially Microsoft 365 Copilot) using the Bot Framework protocol. This adds a second channel alongside the existing ChatKit web frontend, with both channels sharing the same backend orchestrator.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  ChatKit Web    │     │  Microsoft      │
│  Frontend       │     │  Teams          │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │ /chat/stream          │ Bot Framework
         │                       │ Protocol
         ▼                       ▼
┌─────────────────────────────────────────┐
│           FastAPI Backend               │
├─────────────────┬───────────────────────┤
│ chat_routers    │   m365_router         │
│ (ChatKit)       │   (/api/messages)     │
└────────┬────────┴───────────┬───────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────┐
│         HandoffOrchestrator             │
│    (Shared Agent Framework Workflow)    │
└─────────────────────────────────────────┘
```

## Components Added

### 1. M365 Router (`app/backend/app/routers/m365_router.py`)

The main entry point for Bot Framework messages. Key features:

- **Endpoint**: `POST /api/messages` - Receives activities from Azure Bot Service
- **GET /api/messages** - Health check endpoint showing M365 SDK status
- **Authentication**: Uses `MsalConnectionManager` with User Assigned Managed Identity
- **Adapter**: `CloudAdapter` from `microsoft-agents-hosting-fastapi`

```python
# Key configuration
service_connection_config = AgentAuthConfiguration(
    client_id=bot_app_id,
    tenant_id=tenant_id,
    auth_type=AuthTypes.user_managed_identity,
    connection_name="SERVICE_CONNECTION",
)
```

### 2. Banking Activity Handler (`app/backend/app/agents/m365/banking_activity_handler.py`)

Handles incoming Bot Framework activities and bridges them to the HandoffOrchestrator:

- **on_message_activity**: Processes user messages
- **on_members_added_activity**: Sends welcome message when user joins
- **Thread ID mapping**: Maps Teams conversation IDs to orchestrator thread IDs
- **Orchestrator integration**: Calls `processMessageStream()` and streams responses back

Key implementation detail - the handler maintains a mapping between Teams conversation IDs and orchestrator thread IDs:

```python
# First message: pass None to start new workflow
thread_id = self._get_thread_id(conversation_id)  # Returns None for new conversations

# Orchestrator returns the thread_id which we store for future messages
async for content, is_final, tid in orchestrator.processMessageStream(message, thread_id):
    if tid:
        self._set_thread_id(conversation_id, tid)
```

### 3. M365 Events Handler (`app/backend/app/agents/m365/m365_events_handler.py`)

Converts Agent Framework workflow events to M365-compatible responses (currently not used since we simplified to text-only responses).

### 4. Adaptive Cards (`app/backend/app/agents/m365/adaptive_cards.py`)

Builders for Teams Adaptive Cards including:
- Welcome card
- Error card
- Progress indicators
- Approval cards (available but not actively used)

### 5. Teams App Manifest (`app/teams-app/`)

Teams application package containing:
- `manifest.json` - App definition with bot configuration
- `color.png` / `outline.png` - App icons
- `banking-assistant-simple.zip` - Installable Teams app package

## Infrastructure Changes

### Azure Bot Service (`infra/shared/bot/`)

New Bicep modules for Bot Service with MSI authentication:

- **bot-identity.bicep**: Creates User Assigned Managed Identity for the bot
- **azure-bot-msi.bicep**: Deploys Azure Bot Service with MSI authentication

### Main Bicep Updates (`infra/main.bicep`)

Added:
- `enableAzureBot` parameter (default: true)
- Bot MSI creation and assignment
- M365_APP_ID and M365_APP_TENANT_ID environment variables for backend
- Bot messaging endpoint configuration

### Container App Configuration

- Backend Container App has `external: true` ingress (required for Bot Framework)
- Bot's MSI must be assigned to the Container App for token acquisition

## Authentication Flow

The integration uses **User Assigned Managed Identity** for authentication:

1. **Bot Registration**: Azure Bot Service registered with MSI App ID
2. **MSI Assignment**: The bot's MSI (`id-bot-*`) is assigned to the Container App
3. **Token Acquisition**: M365 SDK acquires tokens using the MSI when responding to messages
4. **No Secrets**: No client secrets or passwords required

```
Teams → Azure Bot Service → Container App (/api/messages)
                                    │
                                    ▼
                         MsalConnectionManager
                         (AuthTypes.user_managed_identity)
                                    │
                                    ▼
                         Token acquired via MSI
                                    │
                                    ▼
                         Response sent to Teams
```

## Dependencies Added

In `pyproject.toml`:

```toml
"microsoft-agents-core>=0.7.0",
"microsoft-agents-hosting-fastapi>=0.7.0",
"microsoft-agents-authentication-msal>=0.7.0",
```

## Deployment

### Prerequisites

1. Azure subscription with permissions to create Bot Service
2. Container Apps environment deployed
3. M365 tenant for Teams app installation

### Deploy Infrastructure

```bash
azd provision
```

This creates:
- User Assigned Managed Identity for bot
- Azure Bot Service with MSI authentication
- Updates Container App with bot MSI assignment

### Deploy Backend

```bash
azd deploy --service backend
```

### Build and Install Teams App

The Teams app manifest uses placeholders that must be replaced with your deployment values.

1. **Build the app package**:
   ```bash
   cd app/teams-app
   
   # Get values from your deployment
   export BOT_APP_ID=$(azd env get-values | grep M365_APP_ID | cut -d'"' -f2)
   export BACKEND_DOMAIN=$(azd env get-values | grep SERVICE_API_URI | cut -d'"' -f2 | sed 's|https://||' | sed 's|/$||')
   
   # Process manifest and create package
   sed -e "s|\${{BOT_APP_ID}}|$BOT_APP_ID|g" \
       -e "s|\${{BACKEND_DOMAIN}}|$BACKEND_DOMAIN|g" \
       manifest.json > manifest-build.json
   
   zip -j banking-assistant.zip manifest-build.json color.png outline.png
   # Rename manifest inside zip
   printf "@ manifest-build.json\n@=manifest.json\n" | zipnote -w banking-assistant.zip
   ```

2. **Install in Teams**:
   - Open Microsoft Teams → Apps → Manage your apps
   - Click "Upload an app" → "Upload a custom app"
   - Select `banking-assistant.zip`

See [app/teams-app/README.md](../app/teams-app/README.md) for detailed instructions.

### Manual MSI Assignment (if needed)

If the bot MSI isn't automatically assigned to the Container App:

```bash
az containerapp identity assign \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --user-assigned <bot-msi-resource-id>
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `M365_APP_ID` | Bot's MSI Client ID |
| `M365_APP_TENANT_ID` | Azure AD Tenant ID |

### Bot Messaging Endpoint

The bot's messaging endpoint must be set to:
```
https://<container-app-url>/api/messages
```

This is configured automatically in `main.bicep`:
```bicep
messagingEndpoint: '${backend.outputs.SERVICE_API_URI}/api/messages'
```

## User Identity

Currently, the user identity is **hardcoded** as `bob.user@contoso.com` in the agent instructions. This matches the demo data in the business APIs.

Teams provides user identity via the activity context:
- `turn_context.activity.from_property.name` - Display name
- `turn_context.activity.from_property.aad_object_id` - Azure AD Object ID

To use real Teams identities, the agent instructions would need to be updated to accept dynamic user context.

## Limitations

1. **No Adaptive Card interception**: Responses are returned as plain text. Payment confirmations use conversational approval ("yes"/"no") rather than button cards.

2. **Hardcoded user**: Demo uses `bob.user@contoso.com` regardless of Teams user identity.

3. **In-memory state**: Conversation thread mappings are stored in-memory. For production, use persistent storage.

4. **Single tenant**: Bot is configured for single-tenant authentication within your organization.

## Testing

### Verify M365 SDK Status

```bash
curl https://<container-app-url>/api/messages
```

Expected response:
```json
{
  "status": "OK",
  "channel": "M365 Agent SDK",
  "capabilities": ["teams", "messages"]
}
```

### Check Container Logs

```bash
az containerapp logs show \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --type console \
  --tail 100
```

### Test in Teams

1. Open Teams and find the "Banking Assistant" app
2. Send a message like "What's my account balance?"
3. The bot should respond with account information

## Troubleshooting

### "No User Assigned Managed Identity found"

The bot's MSI is not assigned to the Container App. Run:
```bash
az containerapp identity assign --name <app> --resource-group <rg> --user-assigned <msi-id>
```

### "No checkpoint found for thread_id"

The handler was passing Teams conversation ID directly as thread_id. Fixed by mapping Teams conversations to orchestrator threads.

### Bot not responding in Teams

1. Check the messaging endpoint is correct: `/api/messages` (not `/api/m365/messages`)
2. Verify bot MSI is assigned to Container App
3. Check Container App logs for errors

## Files Changed/Added

### New Files
- `app/backend/app/routers/m365_router.py`
- `app/backend/app/agents/m365/__init__.py`
- `app/backend/app/agents/m365/banking_activity_handler.py`
- `app/backend/app/agents/m365/m365_events_handler.py`
- `app/backend/app/agents/m365/adaptive_cards.py`
- `app/teams-app/manifest.json`
- `app/teams-app/color.png`
- `app/teams-app/outline.png`
- `infra/shared/bot/bot-identity.bicep`
- `infra/shared/bot/azure-bot-msi.bicep`

### Modified Files
- `app/backend/pyproject.toml` - Added M365 SDK dependencies
- `app/backend/app/main_chatkit_server.py` - Included m365_router
- `infra/main.bicep` - Added bot infrastructure and environment variables
- `infra/app/backend.bicep` - Set `external: true` for ingress

## Future Enhancements

1. **Dynamic user identity**: Pass Teams user info to orchestrator
2. **Adaptive Cards**: Implement structured cards for approvals and rich responses
3. **Proactive messaging**: Send notifications to users
4. **SSO integration**: Use Teams SSO for accessing user-specific resources
5. **Copilot integration**: Enable as a Microsoft 365 Copilot plugin
