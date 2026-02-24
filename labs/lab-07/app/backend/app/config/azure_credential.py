import os
from azure.identity import ManagedIdentityCredential, AzureCliCredential
from azure.identity.aio import ManagedIdentityCredential as AioManagedIdentityCredential, AzureCliCredential as AioCliCredential
from app.config.settings import settings


async def get_azure_credential_async():
    """Returns an async Azure credential based on the application environment."""
    if settings.PROFILE == 'dev':
        return AioCliCredential()
    else:
        return AioManagedIdentityCredential(client_id=settings.AZURE_CLIENT_ID)


def get_async_azure_credential():
    """Returns an async Azure credential based on the application environment."""
    if settings.PROFILE == 'dev':
        return AioCliCredential()
    else:
        return AioManagedIdentityCredential(client_id=settings.AZURE_CLIENT_ID)


def get_azure_credential():
    """Returns a sync Azure credential based on the application environment."""
    if settings.PROFILE == 'dev':
        return AzureCliCredential()
    else:
        return ManagedIdentityCredential(client_id=settings.AZURE_CLIENT_ID)
