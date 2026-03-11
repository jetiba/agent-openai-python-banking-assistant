"""Dependency injection container for Lab 9 — MCP tool connections added.

Compared to Lab 8, this container now passes MCP server URLs to both agents
so they can connect to the business API MCP servers at runtime:
- AccountAgent  → Account API + Transaction API
- PaymentAgent  → Payment API  (+ scan_invoice as before)

Uses AzureAIProjectAgentProvider for agent creation and Foundry conversation-
based session management.
"""

from agent_framework.azure import AzureAIProjectAgentProvider
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.storage.blob import BlobServiceClient
from dependency_injector import containers, providers

from app.agents.account_agent import AccountAgent
from app.agents.payment_agent import PaymentAgent
from app.config.azure_credential import get_async_azure_credential, get_azure_credential
from app.config.settings import settings
from app.helpers.blob_proxy import BlobStorageProxy
from app.helpers.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    # AzureAIProjectAgentProvider — Factory so a new provider (and its
    # server-side agent/thread resources) is created for each request.
    _provider = providers.Factory(
        AzureAIProjectAgentProvider,
        credential=providers.Factory(get_async_azure_credential),
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        model=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
    )

    # ---- Lab 8: Blob Storage + Document Intelligence ----

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

    # Account Agent — NEW in Lab 9: MCP connections to Account + Transaction APIs.
    account_agent = providers.Singleton(
        AccountAgent,
        provider=_provider,
        account_api_mcp_url=settings.ACCOUNT_API_MCP_URL,
        transaction_api_mcp_url=settings.TRANSACTION_API_MCP_URL,
    )

    # Payment Agent — NEW in Lab 9: adds Payment API MCP alongside scan_invoice.
    payment_agent = providers.Singleton(
        PaymentAgent,
        provider=_provider,
        document_scanner_helper=document_intelligence_scanner,
        payment_api_mcp_url=settings.PAYMENT_API_MCP_URL,
    )
