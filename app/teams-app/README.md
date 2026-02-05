# Teams App Package

This folder contains the Microsoft Teams app package for the Banking Assistant.

## Contents

- `manifest.json` - The app manifest (v1.22) with Bot and Copilot Agent support
- `color.png` - 192x192 color icon (required)
- `outline.png` - 32x32 outline icon (required)

## Configuration

Before deploying, replace the placeholders in `manifest.json`:

| Placeholder | Description |
|-------------|-------------|
| `{{BOT_ID}}` | Your Azure AD App Registration Client ID (same as M365_APP_ID) |

## Creating the App Package

1. Replace `{{BOT_ID}}` with your actual Bot/App ID
2. Ensure you have the icon files (`color.png` and `outline.png`)
3. Zip the contents (not the folder):
   ```bash
   cd app/teams-app
   zip -r banking-assistant.zip manifest.json color.png outline.png
   ```

## Deploying to Teams

### Option 1: Sideload (Development)
1. Go to Teams → Apps → Manage your apps
2. Click "Upload an app" → "Upload a custom app"
3. Select the `banking-assistant.zip` file

### Option 2: Admin Center (Organization)
1. Go to Teams Admin Center
2. Navigate to Teams apps → Manage apps
3. Click "Upload" and select the zip file
4. Configure policies to allow the app

### Option 3: Partner Center (Public)
1. Go to Partner Center
2. Submit for certification

## Azure Bot Service Setup

Before the app will work, you need:

1. **Azure AD App Registration**
   - Create in Azure Portal → Azure Active Directory → App Registrations
   - Note the Application (client) ID - this is your `BOT_ID`
   - Create a client secret - this is your `M365_APP_PASSWORD`

2. **Azure Bot Service**
   - Create in Azure Portal → Create resource → Azure Bot
   - Use the App Registration from step 1
   - Set messaging endpoint to: `https://your-app.azurewebsites.net/api/messages`
   - Enable the Microsoft Teams channel

3. **Environment Variables**
   Set these on your backend service:
   ```
   MicrosoftAppId=<your-bot-id>
   MicrosoftAppPassword=<your-client-secret>
   MicrosoftAppTenantId=<your-tenant-id-or-common>
   ```

## Features

This app supports:

- ✅ **Teams Bot** - Personal, Team, and Group Chat scopes
- ✅ **Copilot Agent** - Appears in Microsoft 365 Copilot sidebar
- ✅ **Adaptive Cards** - Rich interactive UI for approvals
- ✅ **Multi-agent orchestration** - Account, Transaction, and Payment agents
