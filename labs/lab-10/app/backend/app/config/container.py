"""Dependency injection container for Lab 10 — Multi-agent handoff.

Compared to Lab 9, this container:
* Splits account functionality into ``AccountAgent`` (account-only) and
  ``TransactionHistoryAgent`` (account + transaction MCP).
* Adds a ``HandoffOrchestrator`` that wires triage + 3 specialists via
  the ``HandoffBuilder`` workflow.
"""

from agent_framework.azure import AzureAIClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.storage.blob import BlobServiceClient
from dependency_injector import containers, providers

from app.agents.account_agent import AccountAgent
from app.agents.handoff_orchestrator import HandoffOrchestrator
from app.agents.payment_agent import PaymentAgent
from app.agents.transaction_agent import TransactionHistoryAgent
from app.config.azure_credential import get_async_azure_credential, get_azure_credential
from app.config.settings import settings
from app.helpers.blob_proxy import BlobStorageProxy
from app.helpers.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    # Foundry v2 Agent Client — Factory so a new client (and its
    # server-side agent/thread resources) is created for each request.
    _azure_ai_client = providers.Factory(
        AzureAIClient,
        credential=providers.Factory(get_async_azure_credential),
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
    )

    # ---- Blob Storage + Document Intelligence ----

    blob_service_client = providers.Singleton(
        BlobServiceClient,
        account_url=f"https://{settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net",
        credential=providers.Factory(get_azure_credential),
    )

    blob_proxy = providers.Singleton(
        BlobStorageProxy,
        container_name=settings.AZURE_STORAGE_CONTAINER,
        client=blob_service_client,
    )

    document_intelligence_client = providers.Singleton(
        DocumentIntelligenceClient,
        endpoint=f"https://{settings.AZURE_DOCUMENT_INTELLIGENCE_SERVICE}.cognitiveservices.azure.com/",
        credential=providers.Factory(get_azure_credential),
    )

    document_intelligence_scanner = providers.Singleton(
        DocumentIntelligenceInvoiceScanHelper,
        client=document_intelligence_client,
        blob_storage_proxy=blob_proxy,
    )

    # ---- Specialist agents ----

    # AccountAgent — account MCP only (Lab 10 splits out transactions).
    account_agent = providers.Singleton(
        AccountAgent,
        azure_ai_client=_azure_ai_client,
        account_api_mcp_url=settings.ACCOUNT_API_MCP_URL,
    )

    # TransactionHistoryAgent — NEW in Lab 10: account + transaction MCP.
    transaction_agent = providers.Singleton(
        TransactionHistoryAgent,
        azure_ai_client=_azure_ai_client,
        account_api_mcp_url=settings.ACCOUNT_API_MCP_URL,
        transaction_api_mcp_url=settings.TRANSACTION_API_MCP_URL,
    )

    # PaymentAgent — all 3 MCP servers + scan_invoice.
    payment_agent = providers.Singleton(
        PaymentAgent,
        azure_ai_client=_azure_ai_client,
        document_scanner_helper=document_intelligence_scanner,
        account_api_mcp_url=settings.ACCOUNT_API_MCP_URL,
        transaction_api_mcp_url=settings.TRANSACTION_API_MCP_URL,
        payment_api_mcp_url=settings.PAYMENT_API_MCP_URL,
    )

    # ---- Handoff orchestrator ----

    handoff_orchestrator = providers.Factory(
        HandoffOrchestrator,
        azure_ai_client=_azure_ai_client,
        account_agent=account_agent,
        transaction_agent=transaction_agent,
        payment_agent=payment_agent,
    )
