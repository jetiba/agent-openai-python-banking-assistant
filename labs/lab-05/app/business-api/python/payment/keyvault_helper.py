"""
Azure Key Vault helper — retrieve secrets using managed identity.

Requires:
    azure-identity
    azure-keyvault-secrets

Environment variables:
    AZURE_KEY_VAULT_ENDPOINT  – Key Vault URI (e.g. https://kv-xyz.vault.azure.net/)
    AZURE_CLIENT_ID           – client ID of the user-assigned managed identity
"""

import os
import logging

logger = logging.getLogger(__name__)


def get_keyvault_client():
    """Return a SecretClient backed by DefaultAzureCredential, or None."""
    endpoint = os.environ.get("AZURE_KEY_VAULT_ENDPOINT", "")
    if not endpoint:
        logger.warning("AZURE_KEY_VAULT_ENDPOINT not set – Key Vault integration disabled")
        return None
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=endpoint, credential=credential)
        logger.info("Key Vault client initialised for %s", endpoint)
        return client
    except Exception:
        logger.exception("Failed to create Key Vault client")
        return None


def get_secret(secret_name: str, default: str | None = None) -> str | None:
    """Fetch a single secret value from Azure Key Vault.

    Falls back to *default* when the vault is unreachable or the secret
    does not exist.
    """
    client = get_keyvault_client()
    if client is None:
        return default
    try:
        secret = client.get_secret(secret_name)
        logger.info("Retrieved secret '%s' from Key Vault", secret_name)
        return secret.value
    except Exception:
        logger.exception("Could not retrieve secret '%s'", secret_name)
        return default


def verify_keyvault_access() -> bool:
    """Quick smoke-test that the managed identity can reach Key Vault.

    Lists up to 1 secret to confirm connectivity and permissions.
    Returns True on success, False otherwise.
    """
    client = get_keyvault_client()
    if client is None:
        return False
    try:
        # list_properties_of_secrets is a paged operation; fetching the first
        # page proves connectivity + RBAC/access-policy are correct.
        page = client.list_properties_of_secrets()
        _ = next(iter(page), None)  # consume at most one item
        logger.info("Key Vault access verified successfully")
        return True
    except Exception:
        logger.exception("Key Vault access verification failed")
        return False
