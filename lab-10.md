# Lab 10 – Multi-Agent Orchestration with Handoff

## Objectives

| # | Goal | What you will do |
|---|------|------------------|
| 1 | **Split agents by domain responsibility** | Break the Lab 9 two-agent design into three specialist agents — `AccountAgent`, `TransactionHistoryAgent`, and `PaymentAgent` — each scoped to a specific banking domain. |
| 2 | **Introduce a triage agent** | Add a `TriageAgent` that classifies every user message and delegates it to the correct specialist via handoff tools. |
| 3 | **Build a HandoffBuilder workflow** | Wire all four agents together using the Agent Framework `HandoffBuilder` / `HandoffAgentExecutor` so the conversation can flow between specialists while preserving full context. |
| 4 | **Enable human-in-the-loop approval** | Use MCP `approval_mode` on the `processPayment` tool so the user must explicitly approve every payment through a ChatKit approval widget. |
| 5 | **Add per-thread checkpoint storage** | Maintain an `InMemoryCheckpointStorage` per thread so mid-workflow state (including pending approval requests) survives across HTTP requests. |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Azure Container Apps                               │
│                                                                             │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐  ┌───────────┐                │
│  │  Web    │──│ Account  │  │ Transaction │  │  Payment  │                │
│  │ Frontend│  │  API     │  │  API        │  │  API      │                │
│  └────┬────┘  │ /mcp     │  │ /mcp        │  │ /mcp      │                │
│       │       └────▲─────┘  └─────▲───────┘  └─────▲─────┘                │
│       │ /chatkit   │              │                │                        │
│  ┌────▼───────────────────────────────────────────────────┐                │
│  │  Backend AI Service (FastAPI + ChatKit)                 │                │
│  │                                                         │                │
│  │  ┌─────────────────────────────────────────────────┐   │                │
│  │  │          HandoffBuilder Workflow                 │   │                │
│  │  │                                                 │   │                │
│  │  │  ┌──────────────┐                               │   │                │
│  │  │  │ TriageAgent  │  (classifies & routes)        │   │                │
│  │  │  │  ─handoff──► │                               │   │                │
│  │  │  └──┬───┬───┬───┘                               │   │                │
│  │  │     │   │   │                                   │   │                │
│  │  │  ┌──▼┐ ┌▼──┐ ┌──▼───────────────────────┐      │   │                │
│  │  │  │ A │ │ T │ │ P (PaymentAgent)         │      │   │                │
│  │  │  │ c │ │ x │ │  MCP: account-api ───────┼──────┤   │                │
│  │  │  │ c │ │ n │ │  MCP: transaction-api ───┼──────┤   │                │
│  │  │  │ o │ │ H │ │  MCP: payment-api ───────┼──────┤   │                │
│  │  │  │ u │ │ i │ │  Tool: scan_invoice      │      │   │                │
│  │  │  │ n │ │ s │ │  approval_mode ──► widget│      │   │                │
│  │  │  │ t │ │ t │ └──────────────────────────┘      │   │                │
│  │  │  │   │ │   │                                   │   │                │
│  │  │  │MCP│ │MCP│  Each specialist can               │   │                │
│  │  │  │acc│ │acc│  ◄── handoff_to_TriageAgent        │   │                │
│  │  │  │   │ │txn│                                   │   │                │
│  │  │  └───┘ └───┘                                   │   │                │
│  │  └─────────────────────────────────────────────────┘   │                │
│  └────────┬──────────┬────────────────────────────────────┘                │
└───────────┼──────────┼─────────────────────────────────────────────────────┘
            │          │
   ┌────────▼───┐  ┌───▼────────────────────────┐   ┌───────────────────┐
   │ Azure AI   │  │ Azure Blob Storage         │   │ Azure Document    │
   │ Foundry    │  │ (uploaded invoices)         │   │ Intelligence      │
   │ ┌────────┐ │  └────────────────────────────┘   └───────────────────┘
   │ │ GPT-4.1│ │
   │ └────────┘ │
   └────────────┘
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **HandoffBuilder** | A declarative workflow builder from `agent_framework.orchestrations`. You register *participants* and define which agents can hand off to which others. The builder produces a runnable workflow that manages turn-taking, context passing, and checkpointing. |
| **HandoffAgentExecutor** | The executor that runs each participant inside the workflow. Lab 10 uses a `CustomHandoffAgentExecutor` subclass that prevents duplicate handoff tools when an agent already declares them in `default_options["tools"]`. |
| **Triage Agent** | A lightweight agent whose sole purpose is to classify the user's request and call the correct `handoff_to_*` tool. It has no MCP tools — only three handoff function tools. |
| **Specialist Agents** | `AccountAgent`, `TransactionHistoryAgent`, and `PaymentAgent` — each scoped to a single banking domain with the minimum set of MCP servers required. Every specialist also has a `handoff_to_TriageAgent` tool so it can return control when the conversation topic changes. |
| **Approval Mode** | The `MCPStreamableHTTPTool` accepts an `approval_mode` dict. Setting `{"always_require_approval": ["processPayment"]}` causes the SDK to emit a `function_approval_request` event instead of executing the tool, requiring explicit user consent. |
| **ClientWidgetItem** | A custom ChatKit thread item type (defined in `app/common/chatkit/types.py`) that renders an approval card in the frontend. The card contains Approve / Reject buttons whose `ActionConfig` triggers a `ThreadsCustomActionReq` back to the server. |
| **Per-thread Checkpointing** | Each conversation thread gets its own `InMemoryCheckpointStorage`. This lets the `HandoffOrchestrator` resume a workflow exactly where it left off — critical for surviving the HTTP round-trip between showing an approval widget and receiving the user's response. |
| **ChatKitEventsHandler** | Translates raw `WorkflowEvent` objects from the Agent Framework into ChatKit SSE events (text deltas, task indicators, approval widgets). Filters out internal events like `executor_invoked` / `superstep_started` to keep the stream clean. |

## What's New in This Lab

### New packages (`app/common/`)
- **`app/common/__init__.py`** — Package init.
- **`app/common/chatkit/__init__.py`** — Package init.
- **`app/common/chatkit/types.py`** — `ClientWidgetItem` (custom thread item for approval cards) and `CustomThreadItemDoneEvent` (lets the store persist widget items).
- **`app/common/chatkit/widgets.py`** — `build_approval_request()` — builds a ChatKit `Card` widget with Approve / Reject buttons for tool approval requests.

### Agents (`app/agents/`)
- **`app/agents/account_agent.py`** — Slimmed down to account-only MCP. Transactions are moved to the new `TransactionHistoryAgent`. Adds `handoff_to_TriageAgent` tool.
- **`app/agents/transaction_agent.py`** — **NEW.** `TransactionHistoryAgent` with account + transaction MCP servers and its own `handoff_to_TriageAgent`.
- **`app/agents/payment_agent.py`** — Now has all three MCP servers, `scan_invoice`, and `approval_mode` on `processPayment`. Adds `handoff_to_TriageAgent`.
- **`app/agents/handoff_orchestrator.py`** — **NEW.** `HandoffOrchestrator` class with `CustomHandoffBuilder`, per-thread checkpoint storage, `processMessageStream()`, and `processToolApprovalResponse()`. Four module-level `@tool` handoff functions connect the agents.
- **`app/agents/_chatkit_events_handler.py`** — **NEW.** `ChatKitEventsHandler` converts `WorkflowEvent` → ChatKit SSE events with progress indicators, text streaming, and approval widget rendering.

### DI & Routing (`app/config/`, `app/routers/`)
- **`app/config/container.py`** — Adds `TransactionHistoryAgent` and `HandoffOrchestrator` singletons. `AccountAgent` now receives only `account_api_mcp_url`. `PaymentAgent` receives all three MCP URLs.
- **`app/routers/chatkit_server.py`** — Complete rewrite. `BankingAssistantChatKitServer` delegates to `HandoffOrchestrator` instead of keyword triage. Overrides `_process_events()` and `_process_streaming_impl()` for `ClientWidgetItem` and approval actions.
- **`app/routers/chat_routers.py`** — Updated to create the `HandoffOrchestrator` from the DI container. Adds `wrap_stream_with_error_handling()` for robust SSE streaming.

### What Did NOT Change
Infrastructure (`infra/`), settings, attachment handling, Blob Storage, Document Intelligence, frontend, and nginx configuration all carry forward from Lab 9 unchanged.

## Agent Routing Map

| User Intent | Triage Routes To | MCP Servers Used |
|-------------|-----------------|------------------|
| Account lookup, details, beneficiaries, credit cards | `AccountAgent` | account-api |
| Transaction history, recipient search, card transactions | `TransactionHistoryAgent` | account-api, transaction-api |
| Payments, invoice scanning, payment processing | `PaymentAgent` | account-api, transaction-api, payment-api |
| Topic change mid-conversation | Specialist → `TriageAgent` → new specialist | (varies) |

## MCP Tools Available to Each Agent

### AccountAgent

| MCP Server | Tool | Description |
|------------|------|-------------|
| account-api | `getAccountsByUserName` | List all accounts for a user |
| account-api | `getAccountDetails` | Get details for a specific account |
| account-api | `getRegisteredBeneficiary` | List registered beneficiaries |
| account-api | `getCreditCards` | List credit cards for a user |
| account-api | `getCardDetails` | Get details for a specific card |

### TransactionHistoryAgent

| MCP Server | Tool | Description |
|------------|------|-------------|
| account-api | `getAccountsByUserName` | List all accounts for a user |
| account-api | `getAccountDetails` | Get details for a specific account |
| transaction-api | `getLastTransactions` | Get recent transactions for an account |
| transaction-api | `getTransactionsByRecipientName` | Search transactions by recipient |
| transaction-api | `getCardTransactions` | Get transactions for a card |

### PaymentAgent

| MCP Server | Tool | Description |
|------------|------|-------------|
| account-api | `getAccountsByUserName` | List all accounts for a user |
| account-api | `getAccountDetails` | Get details for a specific account |
| transaction-api | `getLastTransactions` | Get recent transactions for an account |
| transaction-api | `getTransactionsByRecipientName` | Search transactions by recipient |
| payment-api | `processPayment` | Execute a payment (**requires approval**) |
| *(local)* | `scan_invoice` | Extract structured invoice data from an uploaded document |

## Step 1 - Review the Code Changes and deploy

1. **Apply the lab delta:**
   ```bash
   ./setup-lab.sh 10
   ```

2. **Review the agent split** — compare `app/agents/account_agent.py` (account-only) with the new `app/agents/transaction_agent.py` (account + transaction). Note how each has a `handoff_to_TriageAgent` tool to return control.

3. **Review the handoff orchestrator** in `app/agents/handoff_orchestrator.py`:
   - See how `CustomHandoffBuilder` wires triage → 3 specialists with bidirectional handoff.
   - Note the per-thread `InMemoryCheckpointStorage` for workflow resumption.
   - Look at `processToolApprovalResponse()` for the approval flow.

4. **Review the events handler** in `app/agents/_chatkit_events_handler.py` — see how `WorkflowEvent` types map to ChatKit progress indicators and text deltas.

5. **Review the approval widget** in `app/common/chatkit/widgets.py` — this builds the Approve / Reject card sent to the frontend.

6. **Review the ChatKit server** in `app/routers/chatkit_server.py`:
   - `respond()` feeds messages through the orchestrator and events handler.
   - `action()` handles approval responses from the widget.
   - `_process_streaming_impl()` handles the `ThreadsCustomActionReq` for widget actions.

7. **Deploy:**
   ```bash
   azd deploy backend
   ```
   In this lab we only need to deploy the backend since infrastructure and the other application components are unchanged.

## Step 2 - Test the multi-agent handoff
   - Ask *"Show details of my account"* — TriageAgent routes to **AccountAgent**.
   - Ask *"What are my recent transactions?"* — TriageAgent routes to **TransactionHistoryAgent**.
   - Ask *"Pay this invoice"* (with an uploaded invoice) — TriageAgent routes to **PaymentAgent**, which scans the document, then shows an **approval widget** before calling `processPayment`.
   - Mid-conversation, switch topics (e.g. from transactions to payments) — the specialist hands back to TriageAgent, which re-routes to the correct agent.

## Key Takeaways

- **HandoffBuilder enables declarative multi-agent orchestration**: you register participants and define routing rules, and the framework handles turn-taking, context passing, and checkpointing — no manual state machine required.
- **Triage + specialist pattern** cleanly separates concerns: the TriageAgent owns classification only (no tools), while each specialist agent holds the minimum set of MCP servers for its domain, reducing scope and improving accuracy.
- **Bidirectional handoff** keeps conversations fluid: specialists can hand back to TriageAgent when the topic changes, enabling natural multi-topic conversations without restarting the session.
- **Human-in-the-loop approval** via `approval_mode` adds a safety gate to sensitive operations: `processPayment` emits an approval widget instead of executing immediately, letting the user review and confirm before money moves.
- **Agent splitting improves tool precision**: giving AccountAgent only account tools and TransactionHistoryAgent only transaction tools reduces the LLM's tool selection space, leading to more accurate and predictable tool calls.
