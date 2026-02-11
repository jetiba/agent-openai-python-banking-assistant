"""Dependency injection container configuration."""

import os
from dependency_injector import containers, providers
from azure.ai.projects import AIProjectClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.storage.blob import BlobServiceClient
from app.helpers.blob_proxy import BlobStorageProxy
from app.helpers.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper
from app.config.azure_credential import get_azure_credential, get_async_azure_credential
from app.config.settings import settings

# Azure AI Foundry based agent dependencies
from app.agents.foundry.account_agent_foundry import AccountAgent
from app.agents.foundry.transaction_agent_foundry import TransactionHistoryAgent
from app.agents.foundry.payment_agent_foundry import PaymentAgent
from app.agents.foundry.supervisor_agent_foundry import SupervisorAgent
from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureAIProjectAgentProvider




class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""
   
    # Helpers
    blob_service_client = providers.Singleton(
        BlobServiceClient,
        credential = providers.Factory(get_azure_credential),
        account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
    )

    blob_proxy = providers.Singleton(
        BlobStorageProxy,
        client = blob_service_client,
        container_name = settings.AZURE_STORAGE_CONTAINER
    )

    # Document Intelligence client singleton
    document_intelligence_client = providers.Singleton(
        DocumentIntelligenceClient,
        credential=providers.Factory(get_azure_credential),
        endpoint=f"https://{settings.AZURE_DOCUMENT_INTELLIGENCE_SERVICE}.cognitiveservices.azure.com/"
    )

    # Document Intelligence scanner singleton
    document_intelligence_scanner = providers.Singleton(
        DocumentIntelligenceInvoiceScanHelper,
        client=document_intelligence_client,
        blob_storage_proxy=blob_proxy
    )
    

     

    
    #Azure Agent Service based agents

    # Foundry Agent Creation
    _foundry_project_provider = AzureAIProjectAgentProvider(project_endpoint=settings.FOUNDRY_PROJECT_ENDPOINT, credential=get_async_azure_credential())
    
    # Account Agent with Azure AI Foundry
    _foundry_account_agent = providers.Singleton(
        AccountAgent,
        foundry_project_provider=_foundry_project_provider,
        chat_deployment_name=settings.FOUNDRY_MODEL_DEPLOYMENT_NAME,
        account_mcp_server_url=f"{settings.ACCOUNT_MCP_URL}/mcp"
    )

    # Transaction History Agent with Azure AI Foundry
    _foundry_transaction_history_agent = providers.Singleton(
        TransactionHistoryAgent,
        foundry_project_provider=_foundry_project_provider,
        chat_deployment_name=settings.FOUNDRY_MODEL_DEPLOYMENT_NAME,
        account_mcp_server_url=f"{settings.ACCOUNT_MCP_URL}/mcp",
        transaction_mcp_server_url=f"{settings.TRANSACTION_MCP_URL}/mcp"
    )

    # Payment Agent with Azure AI Foundry
    _foundry_payment_agent = providers.Singleton(
        PaymentAgent,
        foundry_project_provider=_foundry_project_provider,
        chat_deployment_name=settings.FOUNDRY_MODEL_DEPLOYMENT_NAME,
        account_mcp_server_url=f"{settings.ACCOUNT_MCP_URL}/mcp",
        transaction_mcp_server_url=f"{settings.TRANSACTION_MCP_URL}/mcp",
        payment_mcp_server_url=f"{settings.PAYMENT_MCP_URL}/mcp",
        document_scanner_helper=document_intelligence_scanner
    )


     # Supervisor Agent Azure AI to be used in agents-as-tool orchestration
    supervisor_agent = providers.Factory(
        SupervisorAgent,
       foundry_project_provider=_foundry_project_provider,
        chat_deployment_name=settings.FOUNDRY_MODEL_DEPLOYMENT_NAME,
        account_agent=_foundry_account_agent,
        transaction_agent=_foundry_transaction_history_agent,
        payment_agent=_foundry_payment_agent,
        foundry_endpoint=settings.FOUNDRY_PROJECT_ENDPOINT
    )

   