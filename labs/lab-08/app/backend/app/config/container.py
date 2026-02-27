"""Dependency injection container for Lab 8 — AccountAgent + PaymentAgent."""

from agent_framework.azure import AzureAIClient
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

    # Foundry v2 Agent Client — Singleton so the same client (and its
    # server-side agent/thread resources) is reused across requests.
    _azure_ai_client = providers.Singleton(
        AzureAIClient,
        credential=providers.Factory(get_async_azure_credential),
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
    )

    _azure_ai_client_payment = providers.Singleton(
        AzureAIClient,
        credential=providers.Factory(get_async_azure_credential),
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
    )

    # ---- NEW in Lab 8: Blob Storage + Document Intelligence ----

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

    # Account Agent — conversational only, same as Lab 7 (no tools).
    account_agent = providers.Singleton(
        AccountAgent,
        azure_ai_client=_azure_ai_client,
    )

    # Payment Agent — NEW in Lab 8, uses Document Intelligence scan_invoice tool.
    payment_agent = providers.Singleton(
        PaymentAgent,
        azure_ai_client=_azure_ai_client_payment,
        document_scanner_helper=document_intelligence_scanner,
    )
