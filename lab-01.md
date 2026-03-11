# Lab 1 – Deploy Your First Container App

## Objective

Deploy a single **Account API** (FastAPI) to **Azure Container Apps** with external ingress, an Azure Container Registry, and Application Insights monitoring.

## What You'll Learn

- What Azure Container Apps (ACA) is and how it differs from other container hosting options
- How `azd` (Azure Developer CLI) provisions infrastructure and deploys code
- How Bicep templates define cloud resources
- How to expose a container with external ingress

## Architecture

This is the architecture we'll put in place by the end of this lab. We'll deploy a single containerized API into Azure Container Apps, backed by a container registry and connected to monitoring services.

```
┌──────────────────────────────────────────────┐
│              Azure Resource Group             │
│                                               │
│  ┌─────────────┐   ┌──────────────────────┐  │
│  │ Container    │   │  Container Apps Env   │  │
│  │ Registry     │──▶│                      │  │
│  │ (ACR)        │   │  ┌────────────────┐  │  │
│  └─────────────┘   │  │  Account API   │  │  │
│                     │  │  (external)    │  │  │
│                     │  └────────────────┘  │  │
│                     └──────────────────────┘  │
│                                               │
│  ┌─────────────┐   ┌──────────────────────┐  │
│  │ Log         │   │  Application         │  │
│  │ Analytics   │◀──│  Insights            │  │
│  └─────────────┘   └──────────────────────┘  │
└──────────────────────────────────────────────┘
```

## Prerequisites

Before starting, make sure the following tools are installed locally on your machine:

| Tool | Install |
|------|---------|
| Python ≥ 3.11 | https://www.python.org/downloads/ |
| uv | https://github.com/astral-sh/uv |
| Azure Developer CLI | https://aka.ms/azure-dev/install |
| Docker | https://docs.docker.com/get-docker/ |

## Project Layout

Take a moment to familiarize yourself with the repository structure. The project is organized into three main areas: **infrastructure** (Bicep templates that define Azure resources), **application code** (the FastAPI service), and **labs** (incremental files applied at each step of the workshop).

```
.  (repository root = your workspace)
├── azure.yaml                          # azd service definitions
├── setup-lab.sh                        # Script to apply lab deltas
├── infra/
│   ├── main.bicep                      # Main IaC template
│   ├── main.parameters.json            # Parameters
│   ├── app/
│   │   └── account.bicep               # Account container app
│   └── shared/
│       ├── host/                        # ACA + ACR modules
│       ├── monitor/                     # Monitoring modules
│       └── security/                    # Identity + registry access
├── app/
│   └── business-api/python/account/    # Account API (FastAPI)
│       ├── main.py                      # App entry point
│       ├── routers.py                   # REST endpoints
│       ├── services.py                  # Business logic + data
│       ├── models.py                    # Pydantic models
│       ├── mcp_tools.py                 # MCP tool definitions
│       └── Dockerfile                   # Container image
└── labs/                                # Lab delta files (instructions, new/modified files)
    ├── lab-01/README.md                 # ← You are here
    ├── lab-02/                          # Delta for Lab 2
    └── lab-03/                          # Delta for Lab 3
    └── lab-04/                          # Delta for Lab 4
    └── lab-05/                          # Delta for Lab 5
    └── lab-06/                          # Delta for Lab 6
    └── lab-07/                          # Delta for Lab 7
    └── lab-08/                          # Delta for Lab 8
    └── lab-09/                          # Delta for Lab 9
    └── lab-10/                          # Delta for Lab 10



```

## Step 1 – Explore the Account API locally

Before deploying anything to the cloud, let's start by running the application locally. This will help you understand how the API is built, what endpoints it exposes, and how the code is structured — so you have a solid foundation before moving on to infrastructure and deployment.

```bash
cd app/business-api/python/account
uv sync
uv run uvicorn main:app --reload --port 8080
```

Open http://localhost:8080/docs and try the endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/accounts/{account_id}/cards` | List cards for an account |
| GET | `/api/cards/{card_id}` | Get card details |
| POST | `/api/cards/{card_id}/recharge` | Recharge a card |
| POST | `/api/cards/{card_id}/pay` | Pay with a card |

Try account IDs: `1000` (Alice), `1010` (Bob), `1020` (Charlie).

Try card IDs: `card-1020`, `card-1021` (Alice), `55555`, `66666`, `77777` (Bob).

> **Note**: The API uses in-memory hardcoded data — no database required.

The API also exposes **MCP** (Model Context Protocol) tools at `/mcp`. We'll use these in Part 2 when we add AI agents.

## Step 2 – Review the infrastructure

Now that you've seen the API in action, let's look at how the cloud infrastructure is defined. This project uses **Bicep** templates — Azure's declarative infrastructure-as-code language — together with **Azure Developer CLI (`azd`)** which orchestrates the build, push, and deployment process. Understanding these files will help you see how each Azure resource is configured and how they connect together.

The root of this repo is your working directory. Key files:

| File | Purpose |
|------|---------|
| `azure.yaml` | Tells `azd` which services to build and deploy |
| `infra/main.bicep` | Main IaC template — creates RG, monitoring, ACR, ACA env, Account app |
| `infra/main.parameters.json` | Parameter values |
| `infra/app/account.bicep` | Account container app definition (external ingress, port 8080) |
| `infra/shared/host/` | Reusable Bicep modules for ACA + ACR |
| `infra/shared/monitor/` | Monitoring modules (Log Analytics + App Insights) |

Notice in `infra/app/account.bicep`:
```bicep
external: true      // ← publicly accessible
targetPort: 8080    // ← matches uvicorn port
```

## Step 3 – Deploy to Azure

Now that you understand the application and the repository structure, it's time to deploy everything to Azure. A single `azd up` command will provision all the infrastructure and deploy the container — no manual portal steps needed.

> **⚠️ Warning:** If your machine is already authenticated with other Azure credentials (e.g. a different account or subscription), make sure to log out first to avoid accidentally deploying resources to the wrong subscription:
> ```bash
> azd auth logout
> az logout        # if you also use the Azure CLI
> ```

From the **repository root**:

```bash
# (Optional) If you're still in the account API directory from Step 1:
cd ../../../..

# If you have multiple tenants, specify the tenant ID:
azd auth login --tenant-id "<your-tenant-id>"

# Also log in with the Azure CLI (needed for later labs):
az login --tenant "<your-tenant-id>" --use-device-code
az account set --subscription "$(azd env get-value AZURE_SUBSCRIPTION_ID)"

azd up
```

> **Tip:** You can find your **Tenant ID** in the Azure Portal: go to [Microsoft Entra ID](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/Overview) → **Overview** — the Tenant ID is displayed on the main page. Alternatively, run `az account list -o table` to see all your subscriptions and their associated tenant IDs.

> **Note:** `azd up` will prompt you to select a subscription and location when creating a new environment. Double-check that you're selecting the correct subscription before confirming.

> **📣 Ask your instructor** which Azure **region/location** to use for deploying the resources (e.g. `swedencentral`, `eastus2`). Using the same region as the rest of the group ensures consistency and avoids potential quota issues.

`azd up` will:
1. Create a resource group
2. Provision Log Analytics + Application Insights
3. Create an Azure Container Registry
4. Create an Azure Container Apps Environment
5. Build the Account API Docker image and push to ACR
6. Deploy the container app with external ingress

Once complete, `azd` prints the Account API URL. Open `<url>/docs` to test.

## Step 4 – Verify in the Azure Portal

1. Go to the [Azure Portal](https://portal.azure.com)
2. Find your resource group (name matches your `azd` environment)
3. Explore:
   - **Container Apps Environment** — the shared hosting environment
   - **Container App (account)** — your deployed API
   - **Container Registry** — where the Docker image is stored
   - **Application Insights** — monitoring and logs

4. **Dig deeper — try to answer these questions:**
   - What image tag was pushed to the Container Registry?
   - How could you cache Docker Hub images locally using the Container Registry?
   - How many replicas is your application running on Container Apps?
   - Is Application Insights already collecting metrics from your container app?
   - Where is the `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable defined that define the `InstrumentationKey` value needed by the application?

## Clean Up (Optional - or you can continue to Lab 2 from here)

```bash
azd down --purge
```

---

## Next Steps 
Continue with [Lab 2: Add Transaction & Payment APIs](lab-02.md) to expand the API and deploy updates with `azd deploy`!
