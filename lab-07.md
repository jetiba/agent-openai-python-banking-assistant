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
| **Azure AI Foundry** | A managed Azure service that hosts AI projects, model deployments, and endpoints. |
| **AI Foundry Project** | A child resource of the Foundry account that groups models, data, and configuration for a specific workload. |
| **Agent Framework SDK** | Microsoft's framework for building and orchestrating AI agents. |

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

## Step 1 - Apply the Lab Delta and Deploy

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
## Step 2 - Verify and Test
1. **Verify in the Azure Portal**
   - In the Azure Portal, select your resource group and check the new resources created: Foundry account, Foundry project, backend Container App
   - select the Foundry project > in the Overview page click on "Go to Foundry portal" > take a quick tour of the Foundry portal
      - in the Home page you can see the project endpoints, recent activity, and quick links to resources
      - in the Discover page you can see the model and tool catalogs
      - in the Build page check
         - Agents: see the "Account Agent" created by the backend's agent provider, the version of the agent should be '1'. Click on the agent and review the configuration (system prompt and model settings) in the Playground tab
         - Models: see the GPT-4.1 deployment
      - in the Operations page you can see an overview of agents metrics, the full list of the agents created in the project, access the quota settings for reviewing the limits and asking for quota increases, and in Admin page you can review the role assignments and add new users to the project

2. **Test:** 
    - Connect to the web frontend URL (you can find it in the Azure portal under the frontend Container App) and locate the chat at the bottom right of the page. 
    - Ask the agent a general banking question (e.g., "What is a savings account?", "How interest works on accounts?", "Can you help me with tips on budgeting?"). The agent responds conversationally. 
    - Connect to the Foundry portal: from the [Azure Portal](https://portal.azure.com) > select your Foundry project resource > in the 'Overview' page click on 'Go to Foundry portal' > switch to new Foundry mode on the top of the page > Build > Agents > select 'Account Agent'. Check:
        - The agent's version and configuration in the 'Playground'
        - The agent's execution traces, in the tab 'Traces'. Each message has a conversation ID, if you click on that you can see the entire history for the conversation.
        - Traces are not enabled because App Insights is not configured, but you can enable them in the Foundry portal and then check the telemetry in Azure Monitor.
    - Note that this is a simple prompt agent and it has no tools yet, so it cannot look up real account data or interact with the transaction/payment APIs – that will come in the next labs!

## Key takeaways:
   - **Azure AI Foundry** provides a managed control plane for AI projects – you provision a Foundry account, create a project, and deploy models (e.g., GPT-4.1) entirely through Bicep, keeping your AI infrastructure reproducible and version-controlled.
   - **Agent Framework SDK** decouples agent logic from transport: `AzureAIProjectAgentProvider` handles model communication while `agent-framework-chatkit` handles SSE streaming to the frontend – you write agent instructions, not plumbing code.
   - **Managed Identity + RBAC** eliminates API keys: the backend Container App authenticates to Foundry via its user-assigned managed identity with *Azure AI User* and *Azure AI Developer* roles, following zero-trust best practices.
   - **Conversation history is managed server-side** by Azure AI Foundry (threads), so the backend stays stateless and horizontally scalable – only lightweight thread metadata is kept in-memory.
   - **ChatKit protocol** (SSE-based) gives the frontend real-time token streaming out of the box; the nginx reverse-proxy on the frontend simply forwards `/chatkit` requests to the backend.
   - **Foundry portal observability** lets you inspect deployed agents, review their configuration, view execution traces, and manage quotas – all without touching code.
   - A **prompt-only agent** (no tools) is useful for validating the end-to-end pipeline before adding complexity; tools for real data access come in subsequent labs.


## Next Steps 
Continue with **[Lab 8: Document Intelligence & Invoice scan tool](lab-08.md)** to add a new agent with a Document Intelligence tool, and connect it to the frontend for file upload and scanning capabilities!