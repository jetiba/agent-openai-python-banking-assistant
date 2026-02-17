# Lab 6 – CI/CD with GitHub Actions

## Objectives

- Configure **federated credentials (OIDC)** so GitHub Actions can deploy to Azure without storing secrets
- Deploy infrastructure and application code using `azd` from a **GitHub Actions workflow**
- Add **Bicep validation CI** to catch infrastructure issues on pull requests
- Understand **reusable workflows** for building Docker images and deploying to Azure Container Apps
- Implement **per-service change detection** so only modified services are rebuilt and deployed

## Architecture

Lab 6 adds a CI/CD pipeline layer on top of the existing application architecture. GitHub Actions authenticates to Azure via OIDC federation and uses `azd` (or per-service Docker build/deploy) to push changes.

```
 ┌────────────────────────────────────────────────────────────────┐
 │  GitHub                                                        │
 │                                                                │
 │  ┌──────────────────────────────────────────────────────────┐  │
 │  │  GitHub Actions                                          │  │
 │  │                                                          │  │
 │  │  ┌─────────────────┐   ┌──────────────────────────────┐  │  │
 │  │  │ Infra CI         │   │  App CI/CD                   │  │  │
 │  │  │ (Bicep lint +    │   │  (detect changes → build →   │  │  │
 │  │  │  security scan)  │   │   push to ACR → deploy ACA)  │  │  │
 │  │  └─────────────────┘   └──────────┬───────────────────┘  │  │
 │  │                                   │                      │  │
 │  │  ┌─────────────────┐              │                      │  │
 │  │  │ azd Workflow     │──────┐      │                      │  │
 │  │  │ (provision +     │      │      │                      │  │
 │  │  │  deploy all)     │      │      │                      │  │
 │  │  └─────────────────┘      │      │                      │  │
 │  └───────────────────────────┼──────┼──────────────────────┘  │
 └──────────────────────────────┼──────┼──────────────────────────┘
                    OIDC Token  │      │  Docker push + ACA deploy
                    Exchange    │      │
 ┌──────────────────────────────▼──────▼──────────────────────────┐
 │  Azure                                                         │
 │                                                                │
 │  ┌──────────────┐   ┌──────────────────────────────────────┐  │
 │  │ Entra ID     │   │  Container Apps Environment          │  │
 │  │ (App Reg +   │   │  ┌─────────┐  ┌──────────────────┐  │  │
 │  │  Federated   │   │  │ Account │  │ Transaction API  │  │  │
 │  │  Credential) │   │  │   API   │  └──────────────────┘  │  │
 │  └──────────────┘   │  └─────────┘                        │  │
 │                     │  ┌─────────┐  ┌──────────────────┐  │  │
 │  ┌──────────────┐   │  │ Payment │  │ Web Frontend     │  │  │
 │  │ Container    │   │  │   API   │  └──────────────────┘  │  │
 │  │ Registry     │   │  └─────────┘                        │  │
 │  │ (ACR)        │   └──────────────────────────────────────┘  │
 │  └──────────────┘                                             │
 └───────────────────────────────────────────────────────────────┘
```

## Concepts

| Concept | Description |
|---------|-------------|
| **GitHub Actions** | CI/CD platform built into GitHub. Workflows are YAML files in `.github/workflows/` that run on events (push, PR, manual dispatch). |
| **Federated Credentials (OIDC)** | Instead of storing Azure credentials as GitHub secrets, GitHub Actions obtains a short-lived OIDC token that Azure Entra ID trusts. No secrets to rotate or leak. |
| **`azd pipeline config`** | The Azure Developer CLI command that creates a service principal, configures federated credentials, and sets up GitHub repository variables — all in one step. |
| **Reusable Workflows** | GitHub Actions workflows defined with `workflow_call` that can be invoked by other workflows. Promotes DRY (Don't Repeat Yourself) CI/CD. |
| **Change Detection** | Using `dorny/paths-filter` to detect which files changed and only build/deploy the affected services. |
| **Microsoft Security DevOps** | A GitHub Action that runs security scanners (Template Analyzer for Bicep/ARM) and uploads results to the GitHub Security tab. |

## Files in this Lab (delta from Labs 1–5)

| File | Status | Purpose |
|------|--------|---------|
| `.github/workflows/azure-dev.yml` | New | azd-based workflow: provision + deploy via manual trigger |
| `.github/workflows/infra-ci.yaml` | New | Bicep linting and security scanning on infrastructure changes |
| `.github/workflows/app-ci.yaml` | New | Per-service CI/CD with change detection |
| `.github/workflows/acr-build-push.yaml` | New | Reusable workflow: build Docker image and push to ACR |
| `.github/workflows/aca-deploy.yaml` | New | Reusable workflow: deploy image to Azure Container Apps |

> **Note:** This lab adds workflow files only — no changes to application code or Bicep infrastructure.

## Prerequisites

- Labs 1–5 completed and deployed
- A **GitHub account** with access to create repositories
- The **Azure CLI** authenticated (`az login`)

---

## Step 1 – Apply Lab 6 Files

From the repository root:

```bash
./setup-lab.sh 6
```

This copies five GitHub Actions workflow files into `.github/workflows/`.

Verify:

```bash
ls .github/workflows/
```

You should see:

```
aca-deploy.yaml
acr-build-push.yaml
app-ci.yaml
azure-dev.yml
infra-ci.yaml
```

## Step 2 – Push to Your GitHub Repository

If you haven't already, create a GitHub repository and push your code:

```bash
# Create a new repo on GitHub (via CLI or web UI)
gh repo create <your-org>/aca-workshop --private --source=. --push
```

Or if you already have a remote:

```bash
git add .
git commit -m "Add CI/CD workflows (Lab 6)"
git push origin lab/workshop
```

> **Important**: The workflows need to be in the repository's default branch (or the branch you're working on) to be discovered by GitHub Actions.

## Step 3 – Configure Federated Credentials with `azd pipeline config`

This is the key step. `azd pipeline config` will:
1. Create (or reuse) a **service principal** in Azure Entra ID
2. Add a **federated credential** that trusts your GitHub repository
3. Set the required **GitHub repository variables** (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, etc.)

Run:

```bash
azd pipeline config
```

Follow the prompts:
- Select your Azure subscription
- Confirm the GitHub repository
- Choose the authentication type → select **Federated (OIDC)**

When it completes, verify the variables were created in your GitHub repository:

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Click the **Variables** tab
3. You should see:

| Variable | Description |
|----------|-------------|
| `AZURE_CLIENT_ID` | Service principal's client (application) ID |
| `AZURE_TENANT_ID` | Your Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |
| `AZURE_ENV_NAME` | The azd environment name |
| `AZURE_LOCATION` | The Azure region |

### Understanding OIDC Federation

Unlike traditional service principal authentication (which stores a client secret in GitHub), federated credentials work differently:

```
┌──────────────┐    1. Request OIDC token    ┌──────────────┐
│   GitHub      │ ──────────────────────────► │ GitHub OIDC  │
│   Actions     │ ◄────────────────────────── │ Provider     │
│   Runner      │    2. Return JWT token      └──────────────┘
│               │
│               │    3. Present JWT token     ┌──────────────┐
│               │ ──────────────────────────► │ Azure Entra  │
│               │ ◄────────────────────────── │ ID           │
│               │    4. Return Azure token    └──────────────┘
└──────────────┘
```

- **No secrets stored in GitHub** — the OIDC token is requested fresh for each workflow run
- **Short-lived** — tokens expire after the workflow completes
- **Scoped** — the federated credential only trusts tokens from your specific repository and branch

## Step 4 – Review the azd Workflow

Open `.github/workflows/azure-dev.yml` and examine its structure:

```yaml
name: Azure Developer CLI Deploy
on:
  workflow_dispatch:        # Manual trigger only

permissions:
  id-token: write           # Required for OIDC token request
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Azure/setup-azd@v2
      - name: Log in with Azure (Federated Credentials)
        run: |
          azd auth login \
            --client-id "$AZURE_CLIENT_ID" \
            --federated-credential-provider "github" \
            --tenant-id "$AZURE_TENANT_ID"
      - name: Provision Infrastructure
        run: azd provision --no-prompt
      - name: Deploy Application
        run: azd deploy --no-prompt
```

Key points:

| Element | Purpose |
|---------|---------|
| `workflow_dispatch` | Allows manual triggering from the GitHub Actions UI |
| `permissions.id-token: write` | Enables the runner to request an OIDC token from GitHub |
| `Azure/setup-azd@v2` | Installs the Azure Developer CLI on the runner |
| `azd auth login --federated-credential-provider "github"` | Authenticates using the OIDC token — no secrets needed |
| `azd provision --no-prompt` | Provisions all infrastructure defined in `infra/main.bicep` |
| `azd deploy --no-prompt` | Builds and deploys all services defined in `azure.yaml` |

## Step 5 – Trigger a Manual Deployment

1. Go to your GitHub repository → **Actions** tab
2. Select **Azure Developer CLI Deploy** from the left sidebar
3. Click **Run workflow** → select your branch → click **Run workflow**
4. Watch the workflow run — it should:
   - Check out the code
   - Install `azd`
   - Authenticate via OIDC
   - Run `azd provision` (may take a few minutes if first run)
   - Run `azd deploy` (builds Docker images and deploys to ACA)

> **Tip**: Click on the running job to see live logs. The output is the same as running `azd up` locally.

If the workflow succeeds, your application is deployed entirely from CI/CD — no local `azd up` required.

## Step 6 – Review the Infrastructure Validation Workflow

Open `.github/workflows/infra-ci.yaml`. This workflow validates your Bicep templates whenever infrastructure files change:

```yaml
on:
  push:
    branches: [main]
    paths: ["infra/**"]
  pull_request:
    paths: ["infra/**"]
  workflow_dispatch:
```

### What It Does

1. **Detects changes** — only runs when files under `infra/` are modified
2. **Bicep linting** — runs `az bicep build` to catch syntax errors and best-practice violations
3. **Security scanning** — uses Microsoft Security DevOps (Template Analyzer) to find security misconfigurations
4. **SARIF upload** — pushes scan results to the GitHub **Security** tab for tracking

### Testing It

Create a branch, modify a Bicep file, and open a PR:

```bash
git checkout -b test/infra-validation
echo "// test comment" >> infra/main.bicep
git add infra/main.bicep
git commit -m "Test infra CI"
git push origin test/infra-validation
```

Then open a pull request on GitHub. The `Infra CI Pipeline` workflow should run automatically.

> **Clean up**: Remember to close the PR and delete the test branch when done.

## Step 7 – Understand Per-Service CI/CD (Advanced)

The previous steps used `azd` which deploys everything at once. For production workloads, you often want **per-service CI/CD** — only rebuild and deploy the services that actually changed.

This is implemented with three workflow files working together:

### 7a – Reusable Workflows

**`.github/workflows/acr-build-push.yaml`** — Builds a Docker image and pushes it to ACR:

```yaml
# Called by app-ci.yaml for each service that changed
on:
  workflow_call:
    inputs:
      image-name:        # e.g., "banking-workshop/account-api"
      app-folder-path:   # e.g., "./app/business-api/python/account"
```

Steps:
1. Log in to Azure with federated credentials
2. Log in to ACR (`az acr login`)
3. `docker build` from the service folder
4. `docker push` with the Git SHA as the image tag

**`.github/workflows/aca-deploy.yaml`** — Deploys an image to a Container App:

```yaml
on:
  workflow_call:
    inputs:
      image-name:              # Must match what was pushed
      container-app-name:      # Target Container App
      container-app-env-name:  # Target environment
```

Steps:
1. Log in to Azure with federated credentials
2. Use `azure/container-apps-deploy-action@v1` to update the Container App with the new image

### 7b – The Orchestrator: `app-ci.yaml`

Open `.github/workflows/app-ci.yaml`. This is the main CI/CD pipeline that ties everything together:

**Change Detection** — Uses `dorny/paths-filter@v2` to detect which services have file changes:

```yaml
filters: |
  account-api:
    - 'app/business-api/python/account/**'
  payment-api:
    - 'app/business-api/python/payment/**'
  transaction-api:
    - 'app/business-api/python/transaction/**'
  frontend:
    - 'app/frontend/banking-web/**'
```

**Conditional Jobs** — Each service has a build + deploy job pair that only runs if that service changed:

```yaml
build-account-app:
  needs: changes-detection
  if: ${{ needs.changes-detection.outputs.build-account-api == 'true' }}
  uses: ./.github/workflows/acr-build-push.yaml
  # ...

deploy-account-app:
  needs: [changes-detection, build-account-app]
  uses: ./.github/workflows/aca-deploy.yaml
  # ...
```

**Environment Variables** — The per-service pipeline requires additional GitHub repository variables. Set these in **Settings** → **Secrets and variables** → **Actions** → **Variables**:

| Variable | Description | Example |
|----------|-----------|---------|
| `ACR_NAME` | Azure Container Registry name (without `.azurecr.io`) | `crworkshopdev` |
| `RESOURCE_GROUP` | Resource group name | `rg-workshop-dev` |
| `ACA_DEV_ENV_NAME` | Container Apps environment name | `cae-workshop-dev` |
| `ACCOUNTS_ACA_DEV_APP_NAME` | Account API container app name | `account` |
| `TRANSACTIONS_ACA_DEV_APP_NAME` | Transaction API container app name | `transaction` |
| `PAYMENTS_ACA_DEV_APP_NAME` | Payment API container app name | `payment` |
| `WEB_ACA_DEV_APP_NAME` | Web frontend container app name | `web` |

> **Tip**: You can find these values from your `azd` environment:
> ```bash
> azd env get-values
> ```
> Or from the Azure Portal by inspecting your deployed resources.

### 7c – Test Per-Service Deploy

Push a small code change to one service:

```bash
# Make a minor change to the Account API
echo "# CI/CD test" >> app/business-api/python/account/main.py
git add -A
git commit -m "Test per-service CI/CD"
git push
```

In the GitHub Actions UI, observe that:
- The `Container Apps CI/CD pipeline` workflow triggers
- Only the `build-account-app` and `deploy-account-app` jobs run
- Other service jobs are skipped (shown as grey/skipped)

## Step 8 – Verify the Deployment

After either workflow completes successfully:

1. Get your application URLs:
   ```bash
   azd env get-values | grep -i endpoint
   ```

2. Or find them in the Azure Portal:
   - Go to your resource group
   - Click on each Container App → **Overview** → **Application Url**

3. Test the Account API:
   ```bash
   curl https://<your-account-api-url>/api/accounts/1000
   ```

## Key Takeaways

- **`azd pipeline config`** is the fastest way to set up OIDC federation between GitHub and Azure — it creates the service principal, federated credential, and repository variables in one command
- **Federated credentials (OIDC)** eliminate the need to store Azure secrets in GitHub — tokens are short-lived and scoped to specific repositories/branches
- **Two deployment strategies** are available:
  - `azd provision` + `azd deploy` — deploys everything, simple, good for dev/test
  - Per-service Docker build + ACA deploy — deploys only changed services, efficient for production
- **Reusable workflows** (`workflow_call`) keep CI/CD DRY — the build and deploy logic is defined once and called per service
- **Change detection** with `dorny/paths-filter` prevents unnecessary builds, saving time and compute
- **Infrastructure validation CI** catches Bicep errors and security issues before they reach production
- The `permissions.id-token: write` permission is **required** for OIDC — without it, the runner cannot request a token

## What's Next

In **Lab 7**, you'll integrate **Azure AI Foundry** to add AI/ML capabilities to your banking assistant, connecting the backend services to large language models for intelligent responses.
