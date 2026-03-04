# Lab 7 – AI Foundry & Single Agent

## Objectives

| # | Goal | What you will do |
|---|------|------------------|
| 1 | **Provision Azure AI Foundry** | Add an AI Foundry account, project, and GPT-4.1 model deployment to the Bicep infrastructure. |
| 2 | **Deploy a backend AI service** | Create a new Container App running a FastAPI backend with the Agent Framework SDK. |
| 3 | **Build a single conversational agent** | Wire a single `AzureAIClient`-based agent that can answer general banking questions (no tools yet). |
| 4 | **Connect the frontend to the AI backend** | Update the web frontend's nginx config to proxy `/chatkit` requests to the backend, enabling the chat UI. |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Azure Container Apps                     │
│                                                                 │
│  ┌─────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Web    │──│  Account    │  │ Transaction │  │  Payment  │ │
│  │ Frontend│  │  API        │  │  API        │  │  API      │ │
│  └────┬────┘  └─────────────┘  └─────────────┘  └───────────┘ │
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
| **AzureAIClient** | The Foundry v2 client from `agent_framework.azure` that connects to an AI project endpoint and provides agent creation and execution. |
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
- **`app/config/`** – Pydantic settings, Azure credential helpers, DI container with `AzureAIClient`.
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

5. **Test:** Open the web frontend and navigate to the **AI Agent** tab. Ask the agent a general banking question (e.g., "What is a savings account?"). The agent responds conversationally – it has no tools yet, so it cannot look up real account data.
