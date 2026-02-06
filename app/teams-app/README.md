# Teams App Package

This folder contains the Microsoft Teams app manifest and assets for the Banking Assistant bot.

## Contents

- `manifest.json` - Teams app manifest (template with placeholders)
- `color.png` - App icon (192x192, color version)
- `outline.png` - App icon (32x32, outline version)

## Configuration

The `manifest.json` uses placeholders that must be replaced with your actual values before creating the app package.

### Placeholders

| Placeholder | Description | How to Get |
|-------------|-------------|------------|
| `${{BOT_APP_ID}}` | Bot's Managed Identity Client ID | Run `azd env get-values \| grep M365_APP_ID` or find in Azure Portal under the bot's User Assigned Managed Identity |
| `${{BACKEND_DOMAIN}}` | Your backend Container App domain | Run `azd env get-values \| grep SERVICE_API_URI` and extract the domain (without `https://`) |

### Example Values

After running `azd provision`, you might have:
- `BOT_APP_ID`: `12345678-1234-1234-1234-123456789abc`
- `BACKEND_DOMAIN`: `ca-backend-abc123.region.azurecontainerapps.io`

## Creating the App Package

### Option 1: Manual Replacement

1. **Get your values**:
   ```bash
   # Get Bot App ID
   azd env get-values | grep M365_APP_ID
   
   # Get Backend URL and extract domain
   azd env get-values | grep SERVICE_API_URI
   ```

2. **Update manifest.json**:
   
   Replace all occurrences of:
   - `${{BOT_APP_ID}}` → your actual Bot App ID
   - `${{BACKEND_DOMAIN}}` → your backend domain (without https://)

3. **Create the ZIP package**:
   ```bash
   cd app/teams-app
   zip -r banking-assistant.zip manifest.json color.png outline.png
   ```

### Option 2: Using envsubst (Linux/Mac)

```bash
# Set your values (or get from azd)
export BOT_APP_ID=$(azd env get-values | grep M365_APP_ID | cut -d'"' -f2)
export BACKEND_DOMAIN=$(azd env get-values | grep SERVICE_API_URI | cut -d'"' -f2 | sed 's|https://||' | sed 's|/$||')

echo "Bot App ID: $BOT_APP_ID"
echo "Backend Domain: $BACKEND_DOMAIN"

# Create processed manifest
cd app/teams-app
envsubst < manifest.json > manifest-build.json

# Create the package (manifest must be named manifest.json in the zip)
zip -j banking-assistant.zip color.png outline.png
cd .. && zip -j teams-app/banking-assistant.zip <(cat teams-app/manifest-build.json) && cd teams-app
# Or simpler:
mv manifest-build.json manifest.json.bak
mv manifest.json manifest-template.json
mv manifest.json.bak manifest.json
zip -r banking-assistant.zip manifest.json color.png outline.png
mv manifest.json manifest.json.bak
mv manifest-template.json manifest.json
rm manifest.json.bak
```

### Option 3: Quick Script

Save this as `build-package.sh`:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

# Get values from azd
BOT_APP_ID=$(azd env get-values 2>/dev/null | grep M365_APP_ID | cut -d'"' -f2)
BACKEND_URL=$(azd env get-values 2>/dev/null | grep SERVICE_API_URI | cut -d'"' -f2)
BACKEND_DOMAIN=$(echo "$BACKEND_URL" | sed 's|https://||' | sed 's|/$||')

if [ -z "$BOT_APP_ID" ]; then
    echo "Error: Could not get BOT_APP_ID. Run 'azd provision' first."
    exit 1
fi

echo "Bot App ID: $BOT_APP_ID"
echo "Backend Domain: $BACKEND_DOMAIN"

# Process manifest
sed -e "s|\\\${{BOT_APP_ID}}|$BOT_APP_ID|g" \
    -e "s|\\\${{BACKEND_DOMAIN}}|$BACKEND_DOMAIN|g" \
    manifest.json > manifest-processed.json

# Create temp directory and package
rm -rf temp-package
mkdir temp-package
cp manifest-processed.json temp-package/manifest.json
cp color.png outline.png temp-package/

cd temp-package
zip -r ../banking-assistant.zip manifest.json color.png outline.png
cd ..
rm -rf temp-package manifest-processed.json

echo ""
echo "✅ Created: banking-assistant.zip"
echo ""
echo "To install in Teams:"
echo "1. Open Teams → Apps → Manage your apps"
echo "2. Upload an app → Upload a custom app"
echo "3. Select banking-assistant.zip"
```

Run it:
```bash
cd app/teams-app
chmod +x build-package.sh
./build-package.sh
```

## Installing the App

### For Development/Testing (Sideloading)

1. Open Microsoft Teams
2. Click **Apps** in the left sidebar
3. Click **Manage your apps** at the bottom
4. Click **Upload an app** → **Upload a custom app**
5. Select your `banking-assistant.zip` file
6. Click **Add** to install

### For Organization-Wide Deployment

1. Go to [Teams Admin Center](https://admin.teams.microsoft.com)
2. Navigate to **Teams apps** → **Manage apps**
3. Click **Upload new app**
4. Upload your `banking-assistant.zip`
5. Configure policies to make the app available to users

## Manifest Schema

The manifest follows the [Microsoft Teams manifest schema v1.22](https://learn.microsoft.com/en-us/microsoftteams/platform/resources/schema/manifest-schema).

### Key Sections

- **bots**: Configures the bot with scopes (personal, team, groupChat)
- **commandLists**: Defines suggested commands users can type
- **validDomains**: Domains the bot is allowed to communicate with
- **permissions**: Required permissions (identity for user info)

## Troubleshooting

### "App package not valid"
- Ensure all placeholders (`${{...}}`) are replaced with actual values
- Verify the ZIP contains exactly: `manifest.json`, `color.png`, `outline.png`
- Check that `manifest.json` is at the root of the ZIP (not in a subfolder)

### "Bot not responding"
- Verify the Bot's messaging endpoint is set to `https://<backend-domain>/api/messages`
- Check that the Bot's MSI is assigned to the Container App
- Review Container App logs for errors

### "Bot ID mismatch"
- The `id` and `botId` fields in manifest.json must match the MSI Client ID
- This must also match the `msaAppId` configured on the Azure Bot Service

## Related Documentation

- [M365 Teams Integration Guide](../../docs/m365-teams-integration.md)
- [Microsoft Teams App Manifest](https://learn.microsoft.com/en-us/microsoftteams/platform/resources/schema/manifest-schema)
- [Sideload apps in Teams](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/deploy-and-publish/apps-upload)
