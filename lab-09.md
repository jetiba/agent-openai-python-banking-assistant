# Lab 9 – MCP Tool Integration

## Objectives

| # | Goal | What you will do |
|---|------|------------------|
| 1 | **Connect agents to live data via MCP** | Use `MCPStreamableHTTPTool` from the Agent Framework SDK to connect the AccountAgent and PaymentAgent to the business-API MCP servers at runtime. |
| 2 | **Expose account & transaction data** | Give AccountAgent access to account look-ups, beneficiaries, credit cards, and transaction history through the Account API and Transaction API MCP endpoints. |
| 3 | **Enable end-to-end payment processing** | Extend PaymentAgent with the Payment API MCP endpoint so it can scan an invoice *and* process the payment in a single conversation turn. |
| 4 | **Wire MCP URLs through infrastructure** | Add the three MCP endpoint URLs as environment variables on the backend Container App, dynamically derived from the business-API Container App FQDNs. |

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Azure Container Apps                              │
│                                                                            │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐  ┌───────────┐               │
│  │  Web    │──│ Account  │  │ Transaction │  │  Payment  │               │
│  │ Frontend│  │  API     │  │  API        │  │  API      │               │
│  └────┬────┘  │ /mcp ◄───┼──┼── ◄─────────┼──┼── ◄──┐    │               │
│       │       └──────────┘  └─────────────┘  └───────┼───┘               │
│       │ /chatkit  /upload  /preview                   │                    │
│  ┌────▼──────────────────────────────────────────────┐│                    │
│  │  Backend AI Service                               ││                    │
│  │  (FastAPI + ChatKit)                              ││                    │
│  │  ┌──────────────────────────────────────────────┐ ││                    │
│  │  │  Simple Triage                               │ ││                    │
│  │  │ ┌─────────────────────┬────────────────────┐ │ ││                    │
│  │  │ │ AccountAgent        │ PaymentAgent       │ │ ││                    │
│  │  │ │  MCP: account-api ──┼──────────►         │ │ ││                    │
│  │  │ │  MCP: transaction ──┼──────────►         │ │ ││                    │
│  │  │ │                     │ MCP: payment-api ──┼─┼─┘│                    │
│  │  │ │                     │ Tool: scan_invoice │ │   │                    │
│  │  │ └─────────────────────┴────────────────────┘ │   │                    │
│  │  └──────────────────────────────────────────────┘   │                    │
│  └────────┬──────────┬─────────────────────────────────┘                    │
│           │          │                                                      │
└───────────┼──────────┼──────────────────────────────────────────────────────┘
            │          │
   ┌────────▼───┐  ┌───▼───────────────────────┐   ┌───────────────────┐
   │ Azure AI   │  │ Azure Blob Storage        │   │ Azure Document    │
   │ Foundry    │  │ (uploaded invoices)        │   │ Intelligence      │
   │ ┌────────┐ │  └───────────────────────────┘   │ (Form Recognizer) │
   │ │ GPT-4.1│ │                                   └───────────────────┘
   │ └────────┘ │
   └────────────┘
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Model Context Protocol (MCP)** | An open protocol that standardises how AI agents discover and invoke external tools. MCP servers advertise a catalogue of tools; MCP clients connect and call them using structured JSON-RPC messages. |
| **Streamable HTTP transport** | The HTTP-based MCP transport used by the business APIs. Each API exposes a `/mcp` endpoint powered by FastMCP that supports tool listing and invocation over standard HTTP. |
| **`MCPStreamableHTTPTool`** | A class in the `agent_framework` SDK that acts as an MCP client. Given a `name` and HTTP `url`, it connects to the MCP server, discovers available tools, and makes them callable by the agent at runtime. |
| **Tool discovery** | MCP clients do **not** hard-code tool schemas. On connection the client queries the MCP server's tool catalogue, so the agent always sees the latest schema — no code change needed when the API adds new tools. |
| **Mixed tool lists** | An agent's `tools` list can contain both local Python tools (decorated with `@tool`) and `MCPStreamableHTTPTool` instances. The SDK manages the MCP connection lifecycle transparently. |

## What's New in This Lab

### Infrastructure (`infra/`)
- **`infra/main.bicep`** – Three new environment variables on the backend Container App:
  - `ACCOUNT_API_MCP_URL` → `${account.outputs.SERVICE_API_URI}/mcp`
  - `TRANSACTION_API_MCP_URL` → `${transaction.outputs.SERVICE_API_URI}/mcp`
  - `PAYMENT_API_MCP_URL` → `${payment.outputs.SERVICE_API_URI}/mcp`

  These are computed from the business-API Container App FQDNs so no manual configuration is needed.

### Backend (`app/backend/`)
- **`app/config/settings.py`** – Three new settings: `ACCOUNT_API_MCP_URL`, `TRANSACTION_API_MCP_URL`, `PAYMENT_API_MCP_URL` (with `localhost` defaults for local development).
- **`app/config/container.py`** – Passes the three MCP URLs into `AccountAgent` and `PaymentAgent` constructors.
- **`app/agents/account_agent.py`** – Completely rewritten. Now creates two `MCPStreamableHTTPTool` instances (`account-api`, `transaction-api`) and passes them to the agent. Instructions describe the eight available MCP tools so the LLM knows what data it can retrieve.
- **`app/agents/payment_agent.py`** – Extended with a `MCPStreamableHTTPTool` for the Payment API (`payment-api`). The agent's tool list now includes both `scan_invoice` (local) and `payment-api` (MCP). Updated instructions guide the LLM through the full workflow: scan invoice → confirm with user → call `processPayment`.

### What Did NOT Change
All other files from Lab 8 carry forward unchanged — triage logic, attachment handling, Blob Storage, Document Intelligence, frontend, and nginx configuration remain the same.

## MCP Tools Available to Each Agent

### AccountAgent

| MCP Server | Tool | Description |
|------------|------|-------------|
| account-api | `getAccountsByUserName` | List all accounts for a user |
| account-api | `getAccountDetails` | Get details for a specific account |
| account-api | `getRegisteredBeneficiary` | List registered beneficiaries |
| account-api | `getCreditCards` | List credit cards for a user |
| account-api | `getCardDetails` | Get details for a specific card |
| transaction-api | `getTransactionsByRecipientName` | Search transactions by recipient |
| transaction-api | `getCardTransactions` | Get transactions for a card |
| transaction-api | `getLastTransactions` | Get recent transactions for an account |

### PaymentAgent

| MCP Server | Tool | Description |
|------------|------|-------------|
| payment-api | `processPayment` | Execute a payment with amount, recipient, and account details |
| *(local)* | `scan_invoice` | Extract structured invoice data from an uploaded document |

## Steps

1. **Apply the lab delta:**
   ```bash
   ./setup-lab.sh 9
   ```

2. **Review the MCP tool wiring** in `app/backend/app/agents/account_agent.py` — see how `MCPStreamableHTTPTool` connects to two separate MCP servers and passes them as the agent's tool list.

3. **Review the payment agent update** in `app/backend/app/agents/payment_agent.py` — note how the local `scan_invoice` tool and the `payment-api` MCP tool coexist in a single tool list.

4. **Inspect the infrastructure** in `infra/main.bicep` — find the three new `*_MCP_URL` environment variables on the backend module that bridge the Container App FQDNs to MCP endpoints.

5. **Deploy:**
   ```bash
   azd up
   ```

6. **Test:** 
   - Open the web frontend and locate the agent chat at the bottom right of the page.
   - Ask *"Show my accounts"* — AccountAgent calls `getAccountsByUserName` via MCP and returns real data.
   - Ask *"What are my recent transactions for account 1010?"* — AccountAgent calls `getLastTransactions` via MCP.
   - Upload an invoice and ask *"Pay this invoice"* — PaymentAgent scans the document, presents the extracted data, and on confirmation calls `processPayment` via MCP.
   - Connect to the Foundry portal: from the [Azure Portal](https://portal.azure.com) > select your Foundry project resource > in the 'Overview' page click on 'Go to Foundry portal' > Build > Agents > select one of the agents created and check:
      - The agent's version (it should be updated) and configuration in the 'Playground'
      - The agent's execution traces, in the tab 'Traces'. Each message has a conversation ID, if you click on that you can see the entire history for the conversation.
      - Note the tool invocations in the conversation details, which show calls to the MCP server.
      - Traces are not enabled because App Insights is not configured, but you can enable them in the Foundry portal and then check the telemetry in Azure Monitor.

## Next Steps 
Continue with **[Lab 10: Business APIs Integration as MCP Servers](lab-10.md)** to integrate business APIs and extend the capabilities of your agents.
