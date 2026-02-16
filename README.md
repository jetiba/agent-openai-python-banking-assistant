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
| [Lab 1](labs/lab-01/README.md) | Deploy Your First Container App | Account API with ACR, ACA Environment, monitoring |
| [Lab 2](labs/lab-02/README.md) | Add Microservices & Frontend | Transaction API, Payment API, React web frontend |
| [Lab 3](labs/lab-03/README.md) | Revisions & Traffic Splitting | Multiple revision mode, canary deployments, rollback |
| [Lab 4](labs/lab-04/README.md) | Logging & Monitoring | Azure Monitor OpenTelemetry, App Insights dashboard, KQL queries |
| [Lab 5](labs/lab-05/README.md) | Security | Azure Key Vault, managed identity secret access, Easy Auth |

### Part 2 — AI Components

| Lab | Topic | What You'll Build |
|-----|-------|-------------------|
| Lab 6 | *Coming soon* | AI Foundry + model deployment |
| Lab 7 | *Coming soon* | AI backend agent |
| Lab 8 | *Coming soon* | Multi-agent orchestration |
| Lab 9 | *Coming soon* | MCP tool integration |
| Lab 10 | *Coming soon* | Full banking assistant |

## Prerequisites

| Tool | Install |
|------|---------|
| Python ≥ 3.11 | https://www.python.org/downloads/ |
| uv | https://github.com/astral-sh/uv |
| Azure Developer CLI (`azd`) | https://aka.ms/azure-dev/install |
| Docker | https://docs.docker.com/get-docker/ |
| Node.js ≥ 18 (Lab 2+) | https://nodejs.org/ |

## Quick Start

```bash
# 1. Clone the repo and switch to the workshop branch
git clone <repo-url>
cd agent-openai-python-banking-assistant
git checkout lab/workshop

# 2. Start with Lab 1 (root is already Lab 1)
cat labs/lab-01/README.md

# 3. Deploy
azd auth login
azd up

# 4. When ready for the next lab
./setup-lab.sh 2
azd up
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
└── labs/
    ├── lab-01/                 # Lab 1 instructions (root IS Lab 1)
    ├── lab-02/                 # Lab 2 delta: +transaction, +payment, +frontend
    ├── lab-03/                 # Lab 3 delta: revisions & traffic splitting
    ├── lab-04/                 # Lab 4 delta: logging & monitoring
    └── lab-05/                 # Lab 5 delta: Key Vault & Easy Auth
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
