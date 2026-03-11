# Lab 8 – Document Intelligence & Attachment Upload

## Objectives

| # | Goal | What you will do |
|---|------|------------------|
| 1 | **Provision Azure Document Intelligence** | Add a Document Intelligence (Form Recognizer) resource and an Azure Storage Account to the Bicep infrastructure. |
| 2 | **Introduce a PaymentAgent** | Create a second agent that uses the `scan_invoice` tool powered by Document Intelligence to extract structured data from uploaded invoices. |
| 3 | **Implement simple message triage** | Route incoming messages to either AccountAgent (general Q&A) or PaymentAgent (invoice/bill related) using a lightweight keyword + attachment heuristic. |
| 4 | **Enable file attachments** | Wire the two-phase ChatKit upload protocol so users can upload invoice images/PDFs through the chat UI. |

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                         Azure Container Apps                          │
│                                                                       │
│  ┌─────────┐    ┌──────────┐  ┌─────────────┐  ┌───────────┐          │
│  │  Web    │    │ Account  │  │ Transaction │  │  Payment  │          │
│  │ Frontend│    │  API     │  │  API        │  │  API      │          │
│  └────┬────┘    └──────────┘  └─────────────┘  └───────────┘          │
│       │ /chatkit                                                      |
|       | /upload                                                       |
|       | /preview                                                      │
│  ┌────▼───────────────────────────┐                                   │
│  │  Backend AI Service            │                                   │
│  │  (FastAPI + ChatKit)           │                                   │
│  │  ┌────────────────────────┐    │                                   │
│  │  │  Simple Triage         │    │                                   │
│  │  │ ┌──────────┬─────────┐ │    │                                   │
│  │  │ │ Account  │ Payment │ │    │                                   │
│  │  │ │ Agent    │ Agent   │ │    │                                   │
│  │  │ │ (Q&A)    │ (Scan)  │ │    │                                   │
│  │  │ └──────────┴─────────┘ │    │                                   │
│  │  └────────────────────────┘    │                                   │
│  └────────┬──────────┬──────────┬─┘                                   │
│           │          │          |                                     │
└───────────┼──────────┼──────────|─────────────────────────────────────┘
            │          │          |
   ┌────────▼───┐  ┌───▼───────┐ ┌▼──────────────────┐
   │ Azure AI   │  │ Azure     | |   Azure Document  |
   │            |  |  Blob     | |   Intelligence    |
   |            |  | Storage   | └───────────────────┘
   │ Foundry    │  │ (uploaded |    
   |            |  | invoices) |    
   │ ┌────────┐ │  └───────────┘   
   │ │ GPT-4.1│ │                                  
   │ └────────┘ │
   └────────────┘
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Azure Document Intelligence** | A cognitive service (`Microsoft.CognitiveServices/accounts` kind `FormRecognizer`) that extracts structured data from documents using pre-built or custom models. |
| **Pre-built Invoice Model** | The `prebuilt-invoice` model extracts vendor name, invoice ID, date, total, and other fields from invoice images and PDFs. |
| **`@tool` decorator** | The `agent_framework._tools.tool` decorator that turns a Python method into a tool the LLM agent can call autonomously during a conversation. |
| **Two-phase upload** | The ChatKit attachment protocol: (1) frontend gets an upload URL, (2) frontend POSTs the file bytes to that URL, (3) the file is stored in Blob Storage and the attachment ID is passed to the agent. |
| **Simple triage** | A lightweight per-message routing heuristic: if the message has attachments or contains payment-related keywords, route to PaymentAgent; otherwise route to AccountAgent. |
| **Azure Blob Storage** | Used to persist uploaded invoice files so Document Intelligence can read them for analysis. |

## What's New in This Lab

### Infrastructure (`infra/`)
- **`infra/main.bicep`** – Extended with:
  - **Azure Storage Account** for uploaded invoice files.
  - **Azure Document Intelligence** (Cognitive Services – FormRecognizer, S0 SKU).
  - **Storage Blob Data Contributor** RBAC role for the backend identity.
  - **Cognitive Services User** RBAC role on the Document Intelligence resource.
  - New environment variables on the backend Container App: `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_CONTAINER`, `AZURE_DOCUMENT_INTELLIGENCE_SERVICE`.

### Backend (`app/backend/`)
- **`pyproject.toml`** – Two new dependencies: `azure-storage-blob`, `azure-ai-documentintelligence`.
- **`app/config/settings.py`** – Three new settings: `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_CONTAINER`, `AZURE_DOCUMENT_INTELLIGENCE_SERVICE`.
- **`app/config/container.py`** – DI container extended with `BlobServiceClient`, `BlobStorageProxy`, `DocumentIntelligenceClient`, `DocumentIntelligenceInvoiceScanHelper`, and a new `PaymentAgent` singleton.
- **`app/agents/payment_agent.py`** *(new)* – PaymentAgent with `scan_invoice` tool. Instructions guide the LLM to call the tool when `[attachment_id: …]` is present.
- **`app/helpers/blob_proxy.py`** *(new)* – `BlobStorageProxy` for upload/download of blob files.
- **`app/helpers/document_intelligence_scanner.py`** *(new)* – `DocumentIntelligenceInvoiceScanHelper` with `@tool scan_invoice` that reads a blob, sends it to Document Intelligence, and returns extracted invoice fields as JSON.
- **`app/routers/chatkit_server.py`** – Upgraded with attachment support and simple triage: routes to PaymentAgent when attachments or payment keywords are detected, otherwise AccountAgent.
- **`app/routers/chat_routers.py`** – Now injects both `AccountAgent` and `PaymentAgent`, passes `origin` header for attachment URL generation.
- **`app/routers/attachment_routers.py`** *(new)* – `POST /upload/{attachment_id}` and `GET /preview/{attachment_id}` endpoints.
- **`app/routers/attachment_store.py`** *(new)* – `AttachmentMetadataStore` that creates attachment records with upload/preview URLs.
- **`app/routers/memory_store.py`** – Extended with `save_attachment` / `load_attachment` / `delete_attachment` methods.
- **`app/main.py`** – Now wires both `chat_routers` and `attachment_routers`.

### Frontend (`app/frontend/banking-web/`)
- **`nginx/nginx.conf.template`** – Two new location blocks: `/upload` and `/preview` proxied to the backend, with `client_max_body_size 10m` for file uploads.

## Steps

1. **Apply the lab delta:**
   ```bash
   ./setup-lab.sh 8
   ```

2. **Review the infrastructure changes** in `infra/main.bicep` — note the Storage Account, Document Intelligence resource, and additional RBAC role assignments.

3. **Explore the new PaymentAgent** in `app/backend/app/agents/payment_agent.py` — see how the `scan_invoice` tool is wired via the `@tool` decorator.

4. **Trace the attachment flow:**
   - `attachment_store.py` → creates upload/preview URLs
   - `attachment_routers.py` → handles file upload to Blob Storage
   - `chatkit_server.py` → appends `[attachment_id: …]` to the agent text
   - `document_intelligence_scanner.py` → reads blob, calls Document Intelligence, returns JSON

5. **Deploy:**
   ```bash
   azd up
   ```

6. **Test:** 
   - Connect to the web frontend URL (you can find it in the Azure portal under the frontend Container App) and locate the chat at the bottom right of the page. 
   - Ask the agent a general banking question (e.g., "What is a savings account?", "How interest works on accounts?", "Can you help me with tips on budgeting?"). The agent responds conversationally. 
   - Upload an invoice image (you can find some samples in [data](./data)) and ask "Help me pay this bill" or "Scan this invoice for me", the request will be routed to PaymentAgent, which calls `scan_invoice` and presents extracted fields. 
   - Note that the agent is not connected to the Payment API deployed before, so it cannot proceed with the payment – that will come in the next labs!
   - Connect to the Foundry portal: from the [Azure Portal](https://portal.azure.com) > select your Foundry project resource > in the 'Overview' page click on 'Go to Foundry portal' > Build > Agents > select 'Payment Agent'. Check:
      - The agent's version and configuration in the 'Playground'
      - The agent's execution traces, in the tab 'Traces'. Each message has a conversation ID, if you click on that you can see the entire history for the conversation.
      - Note the tool invocations in the conversation details, which show calls to `scan_invoice` with the attachment ID, and the tool output with the extracted invoice fields.
      - Traces are not enabled because App Insights is not configured, but you can enable them in the Foundry portal and then check the telemetry in Azure Monitor.

## Next Steps 
Continue with **[Lab 9: Business APIs Integration as MCP Servers](lab-09.md)** to integrate business APIs and extend the capabilities of your agents.
