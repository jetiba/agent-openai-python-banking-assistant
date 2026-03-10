# Lab 1 – Deploy Your First Container App

## Objective

Deploy a single **Account API** (FastAPI) to **Azure Container Apps** with external ingress, an Azure Container Registry, and Application Insights monitoring.

## What You'll Learn

- What Azure Container Apps (ACA) is and how it differs from other container hosting options
- How `azd` (Azure Developer CLI) provisions infrastructure and deploys code
- How Bicep templates define cloud resources
- How to expose a container with external ingress

## Architecture

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

| Tool | Install |
|------|---------|
| Python ≥ 3.11 | https://www.python.org/downloads/ |
| uv | https://github.com/astral-sh/uv |
| Azure Developer CLI | https://aka.ms/azure-dev/install |
| Docker | https://docs.docker.com/get-docker/ |

## Step 1 – Explore the Account API locally

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

From the **repository root**:

```bash
# (Optional) If you're still in the account API directory from Step 1:
cd ../../../..

azd auth login
azd up
```

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

## Project Layout

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

## Clean Up (Optional - or you can continue to Lab 2 from here)

```bash
azd down --purge
```

---

## Next Steps 
Continue with [Lab 2: Add Transaction & Payment APIs](lab-02.md) to expand the API and deploy updates with `azd deploy`!
