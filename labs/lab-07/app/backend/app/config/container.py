"""Dependency injection container configuration for Lab 7 - Single Agent with Provider."""

from agent_framework.azure import AzureAIProjectAgentProvider
from dependency_injector import containers, providers
from app.config.azure_credential import get_async_azure_credential
from app.config.settings import settings
from app.agents.account_agent import AccountAgent


class Container(containers.DeclarativeContainer):
    """IoC container for application dependencies."""

    # AzureAIProjectAgentProvider — Singleton so the same provider (and its
    # server-side agent/thread resources) is reused across requests.
    _provider = providers.Factory(
        AzureAIProjectAgentProvider,
        credential=providers.Factory(get_async_azure_credential),
        project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
        model=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
    )

    # Account Agent — Singleton wrapper; sessions are bound to Foundry
    # conversations for server-managed history.
    account_agent = providers.Singleton(
        AccountAgent,
        provider=_provider,
    )
