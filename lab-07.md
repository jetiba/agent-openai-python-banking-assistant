# Lab 7 – AI Foundry & Single Agent

## Objectives

| # | Goal | What you will do |
|---|------|------------------|
| 1 | **Provision Azure AI Foundry** | Add an AI Foundry account, project, and GPT-4.1 model deployment to the Bicep infrastructure. |
| 2 | **Deploy a backend AI service** | Create a new Container App running a FastAPI backend with the Agent Framework SDK. |
| 3 | **Build a single conversational agent** | Wire a single `AzureAIProjectAgentProvider`-based agent that can answer general banking questions (no tools yet). |
| 4 | **Connect the frontend to the AI backend** | Update the web frontend's nginx config to proxy `/chatkit` requests to the backend, enabling the chat UI. |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Azure Container Apps                     │
│                                                                 │
│  ┌─────────┐    ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Web    │    │  Account    │  │ Transaction │  │  Payment  │ │
│  │ Frontend│    │  API        │  │  API        │  │  API      │ │
│  └────┬────┘    └─────────────┘  └─────────────┘  └───────────┘ │
│       │ /chatkit                                                │
│  ┌────▼────────────────┐                                        │
│  │  Backend AI Service │                                        │
│  │  (FastAPI + ChatKit)│                                        │
│  └────────┬────────────┘                                        │
│           │                                                     │
└───────────┼─────────────────────────────────────────────────────┘
            │
   ┌────────▼────────┐
   │  Azure AI       │
   │  Foundry        │
   │  ┌────────────┐ │
   │  │  GPT-4.1   │ │
   │  └────────────┘ │
   └─────────────────┘
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Azure AI Foundry** | A managed Azure service (`Microsoft.CognitiveServices/accounts` with `allowProjectManagement`) that hosts AI projects, model deployments, and endpoints. |
| **AI Foundry Project** | A child resource of the Foundry account that groups models, data, and configuration for a specific workload. |
| **Agent Framework SDK** | Microsoft's `agent-framework-core` and `agent-framework-azure-ai` Python packages for building AI agents with streaming support. |
| **AzureAIProjectAgentProvider** | The Foundry v2 client from `agent_framework.azure` that connects to an AI project endpoint and provides agent creation and execution. |
| **ChatKit Protocol** | A server-sent events (SSE) streaming protocol implemented by `agent-framework-chatkit` that the banking web frontend uses to communicate with the backend. |
| **RBAC** | Role-Based Access Control – the backend's managed identity is granted *Cognitive Services User* and *AI Developer* roles on the Foundry resource. |

## What's New in This Lab

### Infrastructure (`infra/`)
- **`infra/app/backend.bicep`** – New Container App module for the AI backend (1 CPU, 2 GiB, port 8080, user-assigned identity).
- **`infra/main.bicep`** – Extended with AI Foundry account + project, GPT-4.1 model deployment, backend Container App, RBAC role assignments, and web frontend proxying to backend.

### Backend (`app/backend/`)
- **`Dockerfile`** – Python 3.11 image with `uv` package manager, running `uvicorn` on port 8080.
- **`pyproject.toml`** – Dependencies: FastAPI, Agent Framework (core + azure-ai + chatkit), OpenAI ChatKit.
- **`app/main.py`** – FastAPI entry point with ChatKit router, CORS, and Azure Monitor telemetry.
- **`app/config/`** – Pydantic settings, Azure credential helpers, DI container with `AzureAIProjectAgentProvider`.
- **`app/agents/account_agent.py`** – Single conversational agent with banking assistant instructions (no tools).
- **`app/routers/`** – ChatKit server implementation: SSE streaming endpoint at `/chatkit`, in-memory store for thread metadata (conversation history is managed by Azure AI Foundry OOB).

### Frontend (`app/frontend/banking-web/`)
- **`nginx/nginx.conf.template`** – Updated to proxy `/chatkit` requests to the backend AI service.

### Configuration
- **`azure.yaml`** – Adds `backend` as a 5th service.

## Steps

1. **Apply the lab delta:**
   ```bash
   ./setup-lab.sh 7
   ```

2. **Review the new infrastructure** in `infra/main.bicep` – note the AI Foundry module, model deployment, and backend container app with RBAC.

3. **Explore the backend code** in `app/backend/app/` – trace how a chat message flows from the `/chatkit` endpoint through the ChatKit server to the agent and back as SSE events.

4. **Deploy:**
   ```bash
   azd up
   ```

5. **Test:** 
    - Connect to the web frontend URL (you can find it in the Azure portal under the frontend Container App) and locate the chat at the bottom right of the page. 
    - Ask the agent a general banking question (e.g., "What is a savings account?", "How interest works on accounts?", "Can you help me with tips on budgeting?"). The agent responds conversationally. 
    - Connect to the Foundry portal: from the [Azure Portal](https://portal.azure.com) > select your Foundry project resource > in the 'Overview' page click on 'Go to Foundry portal' > switch to new Foundry mode on the top of the page > Build > Agents > select 'Account Agent'. Check:
        - The agent's version and configuration in the 'Playground'
        - The agent's execution traces, in the tab 'Traces'. Each message has a conversation ID, if you click on that you can see the entire history for the conversation.
        - Traces are not enabled because App Insights is not configured, but you can enable them in the Foundry portal and then check the telemetry in Azure Monitor.
    - Note that this is a simple prompt agent and it has no tools yet, so it cannot look up real account data or interact with the transaction/payment APIs – that will come in the next labs!

## Next Steps 
Continue with **[Lab 8: Document Intelligence & Invoice scan tool](lab-08.md)** to add a new agent with a Document Intelligence tool, and connect it to the frontend for file upload and scanning capabilities!