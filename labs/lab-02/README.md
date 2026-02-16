# Lab 2 – Add Transaction, Payment APIs & Frontend

## Objective

Expand the workshop project from a single service to a **microservices architecture** by adding the Transaction and Payment APIs, plus the React web frontend.

You will learn:
- How multiple Container Apps coexist in the same ACA Environment
- Inter-service communication via internal URLs
- Service dependencies (Payment → Transaction)
- Deploying a frontend container that proxies API requests via nginx

## Architecture

```
Azure Container Apps Environment
├── Account API        (external – carries over from Lab 1)
├── Transaction API    (external – new)
├── Payment API        (external – new, calls Transaction internally)
└── Web Frontend       (external – new, nginx reverse-proxy to all APIs)
```

## What's New in This Lab

| Type | Path | Description |
|------|------|-------------|
| **New** | `app/business-api/python/transaction/` | Transaction history API (FastAPI + MCP) |
| **New** | `app/business-api/python/payment/` | Payment processing API (FastAPI + MCP) |
| **New** | `app/frontend/banking-web/` | React web frontend (Vite + nginx) |
| **New** | `infra/app/transaction.bicep` | Bicep module for Transaction container app |
| **New** | `infra/app/payment.bicep` | Bicep module for Payment container app |
| **New** | `infra/app/web.bicep` | Bicep module for Web frontend container app |
| **Modified** | `infra/main.bicep` | Adds transaction, payment & web modules |
| **Modified** | `infra/main.parameters.json` | Adds new `*AppExists` params |
| **Modified** | `azure.yaml` | Adds transaction, payment & web service definitions |

## Steps

### Step 1 – Apply Lab 2 Files

From the repository root, run the setup script to copy all Lab 2 delta files into your workspace:

```bash
./setup-lab.sh 2
```

This copies the new application code, Bicep modules, and updated configuration files into the root.

### Step 2 – Explore the New APIs Locally

**Transaction API:**
```bash
cd app/business-api/python/transaction
uv sync
uv run uvicorn main:app --reload --port 8071
```
Open http://localhost:8071/docs – try `GET /api/transactions/1010`.

**Payment API** (requires Transaction API running):
```bash
cd app/business-api/python/payment
uv sync
export TRANSACTIONS_API_SERVER_URL=http://localhost:8071
uv run uvicorn main:app --reload --port 8072
```
Open http://localhost:8072/docs – try `POST /api/payments` with a payment body.

**Frontend** (requires Account, Transaction, and Payment APIs running):
```bash
cd app/frontend/banking-web
npm install
npm run dev
```
Open http://localhost:5170 – browse Dashboard, Accounts, Payments, and Credit Cards.

> **Note:** The AI assistant chat widget and Support page require the AI backend (Part 2, Lab 7+). All other pages work without it.

### Step 3 – Deploy

```bash
azd up
```

This deploys all four services. The Payment container automatically receives the Transaction API's internal URL via `TRANSACTIONS_API_SERVER_URL`. The Web frontend receives all API URLs via environment variables that nginx uses for reverse-proxying.

### Step 4 – Verify

1. In the Azure Portal, navigate to your Resource Group
2. You should see **four** Container Apps: account, transaction, payment, web
3. Open the **web** Container App's Application URL to access the frontend
4. Navigate between pages to verify API integrations work
5. Check each API's `/docs` endpoint for the Swagger UI

## Key Concepts

- **Service-to-service communication**: The Payment API calls the Transaction API using its internal ACA URL. In the Bicep template, `transaction.outputs.SERVICE_API_URI` is passed as an environment variable to the Payment container.
- **Nginx reverse proxy**: The frontend uses nginx to proxy `/api/*` requests to the corresponding backend Container Apps. Environment variables are injected at container startup using `envsubst`.
- **REST + MCP**: All three APIs now expose both REST endpoints (via FastAPI) and MCP tools. REST endpoints are consumed by the frontend, while MCP tools will be consumed by AI agents in Part 2.
- **Independent scaling**: Each Container App scales independently based on its own traffic patterns.

---

**Next** → [Lab 3: Revisions & Traffic Splitting](../lab-03/README.md)
