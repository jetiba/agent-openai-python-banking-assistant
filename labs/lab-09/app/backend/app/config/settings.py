import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_files() -> List[str]:
    """Get list of environment files to load based on current environment."""
    env = os.getenv("PROFILE")

    if env:
        print(f"Loading environment files for environment: {env}")
    else:
        print("No environment specified, environment variables only configuration will be used.")
        return []

    env = env.lower()
    env_files = [
        ".env",
        f".env.{env}"
    ]

    final_env_files = []
    print("Environment files loading:")
    for f in env_files:
        print(f"Loading: {f}")
        if os.path.exists(f):
            final_env_files.append(f)
            print(f"{f} Loaded")

    return final_env_files


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # app-level
    APP_NAME: str = "Home Banking AI Assistant"
    PROFILE: str = Field(default="prod")

    # Logging and monitoring
    APPLICATIONINSIGHTS_CONNECTION_STRING: str | None = Field(default=None)

    # Azure AI Foundry v2 configuration
    AZURE_AI_PROJECT_ENDPOINT: str | None = Field(default=None)
    AZURE_AI_MODEL_DEPLOYMENT_NAME: str = Field(default="gpt-4.1")

    # Azure OpenAI endpoint (for direct access)
    AZURE_OPENAI_ENDPOINT: str | None = Field(default=None)

    # Support for User Assigned Managed Identity: empty means system-managed
    AZURE_CLIENT_ID: str | None = Field(default="system-managed-identity")

    # ---- Lab 8: Storage & Document Intelligence ----
    AZURE_STORAGE_ACCOUNT: str | None = Field(default=None)
    AZURE_STORAGE_CONTAINER: str = Field(default="content")
    AZURE_DOCUMENT_INTELLIGENCE_SERVICE: str | None = Field(default=None)

    # ---- NEW in Lab 9: MCP server URLs for the business APIs ----
    ACCOUNT_API_MCP_URL: str = Field(default="http://localhost:8070/mcp/")
    TRANSACTION_API_MCP_URL: str = Field(default="http://localhost:8071/mcp/")
    PAYMENT_API_MCP_URL: str = Field(default="http://localhost:8072/mcp/")

    model_config = SettingsConfigDict(
        env_file=get_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
