"""Dependency injection container configuration for Lab 7 - Single Agent."""

from agent_framework.azure import AzureAIClient
from dependency_injector import containers, providers
from app.config.azure_credential import get_async_azure_credential
from app.config.settings import settings
from app.agents.account_agent import AccountAgent


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    # Foundry v2 Agent Client — Singleton so the same client (and its
    # server-side agent/thread resources) is reused across requests.
    _azure_ai_client = providers.Factory(
        AzureAIClient,
        credential=providers.Factory(get_async_azure_credential),
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME
    )

    # Account Agent — Singleton wrapper; the Foundry v2 backend stores
    # conversation threads automatically (OOB session management).
    account_agent = providers.Singleton(
        AccountAgent,
        azure_ai_client=_azure_ai_client,
    )
