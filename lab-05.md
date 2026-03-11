# Lab 5 – Security: Azure Key Vault & Built-in Authentication

## Objectives

- Deploy **Azure Key Vault** alongside the existing Container Apps environment
- Store sensitive configuration (Application Insights connection string) as a **Key Vault secret** instead of passing it inline
- Grant each service's **managed identity** access to Key Vault via **access policies**
- Add a Python **Key Vault SDK helper** to each API so it can retrieve secrets at runtime
- Optionally enable **built-in authentication (Easy Auth)** on the web frontend using **Microsoft Entra ID**

## Architecture

Lab 5 introduces a Key Vault that acts as the central secret store. Each Container App's user-assigned managed identity is granted access to the vault, and a lightweight Python helper uses `DefaultAzureCredential` to read secrets. An optional Easy Auth layer can be activated on the web frontend.

```
                    ┌────────────────────────────────────────────────────┐
                    │  Azure Container Apps Environment                  │
                    │                                                    │
                    │  ┌───────────┐  ┌──────────────┐                  │
  Internet ──────►  │  │  Account  │  │ Transaction  │                  │
   (Easy Auth)      │  │   API     │  │     API      │                  │
                    │  └─────┬─────┘  └──────┬───────┘                  │
                    │        │               │                          │
                    │  ┌─────┴─────┐  ┌──────┴───────┐                  │
                    │  │  Payment  │  │     Web      │◄── Easy Auth     │
                    │  │   API     │  │   Frontend   │   (optional)     │
                    │  └─────┬─────┘  └──────┬───────┘                  │
                    └────────┼───────────────┼──────────────────────────┘
                             │               │
                    ┌────────▼───────────────▼───────────────────┐
                    │            Azure Key Vault                 │
                    │  ┌─────────────────────────────────────┐  │
                    │  │ appinsights-connection-string        │  │
                    │  │ (+ any future secrets)              │  │
                    │  └─────────────────────────────────────┘  │
                    │                                           │
                    │  Access Policies:                         │
                    │   • account-identity  → get, list         │
                    │   • transaction-identity → get, list      │
                    │   • payment-identity  → get, list         │
                    │   • web-identity      → get, list         │
                    └───────────────────────────────────────────┘
```

## Concepts

| Concept | Description |
|---------|-------------|
| **Azure Key Vault** | Managed service for securely storing secrets, keys, and certificates. Eliminates hard-coded credentials in config or environment variables. |
| **Access Policies** | Key Vault can be configured with access policies that grant specific principals (e.g., managed identities) permissions to get/list secrets. |
| **Managed Identity** | Each Container App has a user-assigned managed identity (created in Lab 1). Lab 5 grants these identities permission to read secrets from Key Vault. |
| **DefaultAzureCredential** | Azure Identity SDK class that automatically discovers the best credential: managed identity in Azure, Azure CLI locally. No secrets in code. |
| **SecretClient** | Azure Key Vault Secrets SDK client for reading, listing, and managing secrets programmatically. |
| **Easy Auth** | Azure Container Apps' built-in authentication layer. Configured via `authConfigs` — no code changes required. Supports Microsoft Entra ID, Google, GitHub, etc. |
| **Microsoft Entra ID** | Microsoft's identity platform (formerly Azure AD). Used here as the identity provider for Easy Auth on the web frontend. |

## Files in this Lab (delta from Labs 1–4)

From the previous labs, the following files will be added or modified to integrate Azure Key Vault for secret management and optionally enable Easy Auth on the web frontend:

| File | Status | Purpose |
|------|--------|---------|
| `infra/main.bicep` | Modified | Deploys Key Vault, stores App Insights connection string as secret, grants access policies to all services, optional Easy Auth for web |
| `infra/main.parameters.json` | Modified | Adds `webAuthClientId` and `webAuthClientSecret` parameters (empty by default) |
| `infra/app/account.bicep` | Modified | Accepts `keyVaultEndpoint` param, injects `AZURE_KEY_VAULT_ENDPOINT` env var |
| `infra/app/transaction.bicep` | Modified | Same Key Vault endpoint changes |
| `infra/app/payment.bicep` | Modified | Same Key Vault endpoint changes |
| `infra/app/web.bicep` | Modified | Same Key Vault endpoint changes |
| `infra/shared/security/container-app-auth.bicep` | **New** | Bicep module that configures Easy Auth (Entra ID) on a Container App |
| `app/business-api/python/account/keyvault_helper.py` | **New** | Python helper: `get_secret()`, `verify_keyvault_access()` using managed identity |
| `app/business-api/python/transaction/keyvault_helper.py` | **New** | Same helper for the transaction service |
| `app/business-api/python/payment/keyvault_helper.py` | **New** | Same helper for the payment service |
| `app/business-api/python/account/main.py` | Modified | Imports `keyvault_helper`, calls `verify_keyvault_access()` at startup |
| `app/business-api/python/transaction/main.py` | Modified | Same startup verification |
| `app/business-api/python/payment/main.py` | Modified | Same startup verification |
| `app/business-api/python/account/pyproject.toml` | Modified | Adds `azure-identity` and `azure-keyvault-secrets` dependencies |
| `app/business-api/python/transaction/pyproject.toml` | Modified | Same dependency additions |
| `app/business-api/python/payment/pyproject.toml` | Modified | Same dependency additions |

## Prerequisites

- Labs 1–4 completed and deployed
- Working project at the repository root

---

## Step 1 – Apply Lab 5 Files

From the repository root:

```bash
./setup-lab.sh 5
```

This copies all Lab 5 delta files into your workspace: updated Bicep modules, new `keyvault_helper.py` files, updated `main.py` and `pyproject.toml` for each service.

## Step 2 – Review the Infrastructure Changes

### Key Vault Deployment

Instead of passing sensitive values like connection strings directly as environment variables, we now store them securely in **Azure Key Vault**. The container apps will use their **managed identity** to retrieve secrets at runtime — no credentials stored in code or configuration.

Open `infra/main.bicep`. The new Key Vault section deploys the vault and stores the Application Insights connection string as a secret:

```bicep
module keyVault './shared/security/keyvault.bicep' = {
  name: 'key-vault'
  scope: resourceGroup
  params: {
    name: kvName
    location: location
    tags: tags
  }
}

// Store Application Insights connection string in Key Vault
module appInsightsSecret './shared/security/keyvault-secret.bicep' = {
  name: 'appinsights-secret'
  scope: resourceGroup
  params: {
    name: 'appinsights-connection-string'
    keyVaultName: keyVault.outputs.name
    secretValue: monitoring.outputs.applicationInsightsConnectionString
    contentType: 'text/plain'
  }
}
```

Key points:
- The Key Vault name follows the `kv-<token>` naming convention from `abbreviations.json`
- The Application Insights connection string — previously only injected as a plain environment variable — is now also stored as a Key Vault secret named `appinsights-connection-string`
- This pattern can be extended to store any future secrets (API keys, database connection strings, etc.)

### Access Policies

For each container app to read secrets from Key Vault, we need to grant its **managed identity** the right permissions. Each service gets `get` and `list` access on secrets — following the principle of least privilege:

```bicep
module accountKeyVaultAccess './shared/security/keyvault-access.bicep' = {
  name: 'account-keyvault-access'
  scope: resourceGroup
  params: {
    keyVaultName: keyVault.outputs.name
    principalId: account.outputs.SERVICE_API_IDENTITY_PRINCIPAL_ID
  }
}
```

This is repeated for all four services (account, transaction, payment, web).

### Key Vault Endpoint Environment Variable

The application code needs to know where to find the Key Vault. Rather than hardcoding the URL, each service Bicep file (`infra/app/*.bicep`) now injects the vault's endpoint as an environment variable. The Python helper uses this to connect to Key Vault using the managed identity:

```bicep
param keyVaultEndpoint string = ''

// In the env array:
{ name: 'AZURE_KEY_VAULT_ENDPOINT', value: keyVaultEndpoint }
```

### Easy Auth (Optional)

**Easy Auth** (built-in authentication) allows you to protect your web frontend with Microsoft Entra ID login — without writing any authentication code in your application. It's configured entirely at the infrastructure level. The `container-app-auth.bicep` module is conditionally deployed only when an Entra ID app registration client ID is provided:

```bicep
module webAuth './shared/security/container-app-auth.bicep' = if (!empty(webAuthClientId)) {
  name: 'web-auth'
  scope: resourceGroup
  params: {
    containerAppName: web.outputs.SERVICE_WEB_NAME
    clientId: webAuthClientId
    clientSecretValue: webAuthClientSecret
    issuerUrl: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
  }
}
```

By default, `webAuthClientId` is empty, so Easy Auth is **not** deployed unless you explicitly configure it.

## Step 3 – Review the Application Code Changes

### Key Vault Helper

Open `app/business-api/python/account/keyvault_helper.py`. This module provides three functions:

```python
def get_keyvault_client():
    """Return a SecretClient backed by DefaultAzureCredential, or None."""

def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """Fetch a single secret value from Azure Key Vault."""

def verify_keyvault_access() -> bool:
    """Quick smoke-test that the managed identity can reach Key Vault."""
```

Key design decisions:
- **Graceful fallback:** If `AZURE_KEY_VAULT_ENDPOINT` is not set (e.g., local development), the helper logs a warning and returns `None` — your app still starts
- **`DefaultAzureCredential`:** Automatically uses the user-assigned managed identity in Azure or Azure CLI credentials locally
- **Non-blocking verification:** `verify_keyvault_access()` lists up to one secret to prove connectivity without crashing the app if it fails

### Updated `main.py`

Each service's `main.py` now calls `verify_keyvault_access()` during startup:

```python
from keyvault_helper import verify_keyvault_access

def create_app() -> FastAPI:
    configure_logging()
    verify_keyvault_access()  # Non-blocking Key Vault smoke test
    # ...rest of app setup
```

### Updated Dependencies

Each `pyproject.toml` adds two new packages:

```toml
"azure-identity",
"azure-keyvault-secrets",
```

## Step 4 – Deploy

```bash
azd up
```

This will:
1. Provision the Azure Key Vault and store the App Insights connection string secret
2. Create access policies for all four managed identities
3. Rebuild all API container images (with the new `azure-identity` and `azure-keyvault-secrets` dependencies)
4. Redeploy all container apps with the `AZURE_KEY_VAULT_ENDPOINT` environment variable

## Step 5 – Verify Key Vault in the Azure Portal

1. Go to **Azure Portal** → your **Resource Group**
2. Find the **Key Vault** resource (named `kv-<token>`)
3. Click **Secrets** in the left nav

> **⚠️ Note:** If you see an "Access denied" or "Unauthorized" message when trying to list secrets, you need to add an access policy for your user. Go to the Key Vault → **Access policies** → **Create**, select the **Get** and **List** permissions under **Secret permissions**, then click **Next** and search for your user account. Complete the wizard to save the policy. Wait a moment for it to take effect, then refresh the Secrets page.

4. You should see `appinsights-connection-string` listed
5. Click on it → click the current version → click **Show Secret Value** to confirm it matches your Application Insights connection string

## Step 6 – Verify Key Vault Access from Service Logs

Check the container logs to confirm Key Vault connectivity:

```bash
ACCOUNT_URL=$(azd env get-value ACCOUNT_API_URL)

# Trigger the app to verify it started and connected to Key Vault
curl -s "$ACCOUNT_URL/api/accounts/1010/cards" | head -20
```

Then check the logs using the Azure Portal or the CLI:

```bash
az containerapp logs show \
  --name $(echo "$ACCOUNT_URL" | sed 's|https://\([^.]*\)\..*|\1|') \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --type console \
  --tail 20
```

Look for these log messages:
- `"Key Vault client initialised for https://kv-xxx.vault.azure.net/"` — client created successfully
- `"Key Vault access verified successfully"` — managed identity can read secrets

If you see `"AZURE_KEY_VAULT_ENDPOINT not set – Key Vault integration disabled"`, the environment variable was not injected — check your Bicep deployment.

## Step 7 – Use the Key Vault Helper in Your Code

Now that Key Vault is connected, you can retrieve secrets programmatically. To try this, go to the Azure Portal → your **Container App (account)** → **Console**, select the running container, and open a **Python** shell. Then run the following commands:

```python
from keyvault_helper import get_secret

# Read from Key Vault (falls back to env var if KV is unavailable)
connection_string = get_secret("appinsights-connection-string")
if connection_string:
    print(f"Got connection string from Key Vault: {connection_string[:30]}...")
```

You can also add your own secrets to Key Vault and retrieve them the same way:

```bash
# Add a custom secret via Azure CLI
az keyvault secret set \
  --vault-name $(azd env get-value AZURE_KEY_VAULT_NAME) \
  --name "my-api-key" \
  --value "super-secret-value"
```

```python
# Read it from your service code
api_key = get_secret("my-api-key", default="fallback-value")
```

## Step 8 – (Optional) Enable Easy Auth on the Web Frontend

> **Note:** This step requires you to create a **Microsoft Entra ID App Registration** in your tenant. If you don't have permission to do this, you can skip this section. If this lab is run on a Microsoft-provided tenant (e.g., a workshop or hackathon environment), there is a high chance that this optional part won't work due to security restrictions on the tenant.

### 8a – Create an App Registration

1. Go to **Azure Portal** → **Microsoft Entra ID** → **App registrations** → **New registration**
2. Name: `banking-web-auth-<your-username>` (use your Azure username without the domain as a suffix, e.g., `banking-web-auth-gd-GZENV-1-2`)
3. Supported account types: **Accounts in this organizational directory only**
4. Redirect URI: Choose **Web** and enter your web app URL + `/.auth/login/aad/callback`
   ```
   https://<your-web-app-url>/.auth/login/aad/callback
   ```
   You can find your web URL with:
   ```bash
   azd env get-value WEB_APP_URL
   ```
5. Click **Register**
6. Copy the **Application (client) ID**
7. Go to **Certificates & secrets** → **New client secret** → copy the **Value**

### 8b – Set the azd Environment Variables

```bash
azd env set WEB_AUTH_CLIENT_ID "<your-client-id>"
azd env set WEB_AUTH_CLIENT_SECRET "<your-client-secret>"
```

### 8c – Redeploy

```bash
azd provision
```

This deploys the `container-app-auth.bicep` module, which configures Entra ID authentication on the web frontend Container App.

### 8d – Test

Open your web app URL in a browser. You should be redirected to the Microsoft login page. After signing in, you'll be redirected back to the app.

To verify the auth configuration in the portal:
1. Go to your **Web** Container App → **Authentication** in the left nav
2. You should see **Microsoft** listed as an identity provider

### Removing Easy Auth

To remove Easy Auth, clear the environment variables and redeploy:

```bash
azd env set WEB_AUTH_CLIENT_ID ""
azd env set WEB_AUTH_CLIENT_SECRET ""
azd provision
```

## Key Takeaways

- **Azure Key Vault** is the recommended place to store application secrets — it is access-controlled for managed identities and supports versioning, rotation, and auditing
- **Access Policies** grant fine-grained permissions (get, list, set, delete) to specific identities per secret type (secrets, keys, certificates)
- **`DefaultAzureCredential`** from the Azure Identity SDK automatically discovers the right credential: managed identity in Azure, Azure CLI locally — no secrets in your code
- The **Key Vault Helper** pattern (graceful fallback + startup verification) ensures your services work both in Azure and local development
- **Easy Auth** provides authentication at the platform level without modifying application code — it is configured entirely in Bicep and can be toggled on/off with a parameter
- Separating infrastructure security (Key Vault, access policies) from application code (SDK helper) follows the **principle of least privilege** and **defense in depth**

## Next Steps 

In [Lab 6](lab-06.md), you'll set up **CI/CD with GitHub Actions** — configuring OIDC federation, automating deployments with `azd`, and building per-service pipelines with change detection.
