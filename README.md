# Azure Container Apps Workshop

A hands-on workshop that starts from a single containerized API and progressively builds a full-stack, AI-powered banking assistant on **Azure Container Apps**.

## Workshop Structure

The repository root is your **working directory**. It starts in the **Lab 1** state: a single Account API deployed to Azure Container Apps.

Each subsequent lab is stored as a set of **delta files** in `labs/lab-XX/`. You apply a lab by running:

```bash
./setup-lab.sh <lab-number>
```

This copies the lab's new and modified files into the root. You always run `azd up` (or `azd deploy`) from the root.

## Labs

### Part 1 — Azure Container Apps Features

| Lab | Topic | What You'll Build |
|-----|-------|-------------------|
| [Lab 1](lab-01.md) | Deploy Your First Container App | Account API with ACR, ACA Environment, monitoring |
| [Lab 2](lab-02.md) | Add Microservices & Frontend | Transaction API, Payment API, React web frontend |
| [Lab 3](lab-03.md) | Revisions & Traffic Splitting | Multiple revision mode, canary deployments, rollback |
| [Lab 4](lab-04.md) | Logging & Monitoring | Azure Monitor OpenTelemetry, App Insights dashboard, KQL queries |
| [Lab 5](lab-05.md) | Security | Azure Key Vault, managed identity secret access, Easy Auth |
| [Lab 6](lab-06.md) | CI/CD with GitHub Actions | OIDC federation, azd deploy, per-service pipelines, Bicep validation |

### Part 2 — AI Components

| Lab | Topic | What You'll Build |
|-----|-------|-------------------|
| [Lab 7](lab-07.md) | Single simple Agent deployment | Azure AI Foundry resource, GPT-4.1 deployment, simple prompt agent with ChatKit integration 
| [Lab 8](lab-08.md) | Tools integration | A simple agent with Document Intelligence tool, file upload and scan handling 
| [Lab 9](lab-09.md) | MCP tool integration | Agent tools that call the business API via MCP servers, end-to-end flows with real data
| [Lab 10](lab-10.md)| Multi-agent orchestration | Message triage and handoff for a multi-agent experience
## Prerequisites

| Tool | Install |
|------|---------|
| Python ≥ 3.11 | https://www.python.org/downloads/ |
| uv | https://github.com/astral-sh/uv |
| Azure Developer CLI (`azd`) | https://aka.ms/azure-dev/install |
| Docker | https://docs.docker.com/get-docker/ |
| Node.js ≥ 18 (Lab 2+) | https://nodejs.org/ |

## How to Start

```bash
# 1. Clone the repo and switch to the workshop branch
git clone <repo-url>
cd agent-openai-python-banking-assistant
git checkout lab/workshop

# 2. Follow the instructions in lab-01.md
cat lab-01.md
```

## Project Layout

```
.
├── azure.yaml                  # azd service definitions (evolves per lab)
├── setup-lab.sh                # Script to apply lab deltas
├── infra/
│   ├── main.bicep              # Main IaC template
│   ├── main.parameters.json    # Parameters
│   ├── app/                    # Per-service Bicep modules
│   └── shared/                 # Reusable Bicep modules (ACA, ACR, monitoring)
├── app/
│   └── business-api/python/    # API source code
│       └── account/            # Account API (Lab 1)
├── lab-01.md                   # Lab 1 instructions
├── lab-02.md                   # Lab 2 instructions
├── lab-03.md                   # Lab 3 instructions
├── lab-04.md                   # Lab 4 instructions
├── lab-05.md                   # Lab 5 instructions
├── lab-06.md                   # Lab 6 instructions
└── labs/
    ├── lab-02/                 # Lab 2 delta: +transaction, +payment, +frontend
    ├── lab-03/                 # Lab 3 delta: revisions & traffic splitting
    ├── lab-04/                 # Lab 4 delta: logging & monitoring
    ├── lab-05/                 # Lab 5 delta: Key Vault & Easy Auth
    └── lab-06/                 # Lab 6 delta: CI/CD with GitHub Actions
```

## How the Delta Model Works

- **Root = deployable workspace.** At any point, `azd up` from root deploys whatever labs you've applied.
- **Labs are overlays.** `setup-lab.sh` copies new/modified files into root. It never removes files.
- **Labs build on each other.** Apply them in order (2, 3, 4, ...). Lab 1 is the starting state.
- **`infra/shared/`** contains reusable Bicep modules shared across all labs.

## Clean Up

```bash
azd down --purge
```
