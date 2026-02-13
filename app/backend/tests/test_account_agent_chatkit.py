"""Tests for AccountAgent class."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from agent_framework.azure import AzureAIClient
from agent_framework import Agent
from azure.identity.aio import AzureCliCredential
from app.backend.app.agents.foundry_v2.account_agent import AccountAgent
from app.config.settings import settings


@pytest.fixture
def azure_ai_client():
    """Create a real AzureAIClient instance."""
    project_endpoint = settings.AZURE_AI_PROJECT_ENDPOINT
    model_deployment_name = settings.AZURE_AI_MODEL_DEPLOYMENT_NAME
    
    if not project_endpoint:
        pytest.skip("AZURE_AI_PROJECT_ENDPOINT environment variable is not set")
    if not model_deployment_name:
        pytest.skip("AZURE_AI_MODEL_DEPLOYMENT_NAME environment variable is not set")
    
    return AzureAIClient(
        credential=AzureCliCredential(),
        project_endpoint=project_endpoint,
        model_deployment_name=model_deployment_name
    )


@pytest.fixture
def account_mcp_server_url():
    """Return a test MCP server URL."""
    return "http://localhost:8070/mcp"


@pytest.fixture
def account_agent(azure_ai_client, account_mcp_server_url):
    """Create an AccountAgent instance for testing."""
    return AccountAgent(
        azure_ai_client=azure_ai_client,
        account_mcp_server_url=account_mcp_server_url
    )


class TestAccountAgent:
    """Test cases for AccountAgent."""


    @pytest.mark.asyncio
    async def test_agent_query_execution(self, azure_ai_client, account_mcp_server_url):
        """Test creating an agent and executing a query."""
        # Create account agent instance
        account_agent = AccountAgent(
            azure_ai_client=azure_ai_client,
            account_mcp_server_url= f"{account_mcp_server_url}/mcp"
        )
        
        # Build the agent framework agent
        agent = await account_agent.build_af_agent()
        
        # Execute a query
        query = "How much I have on my account?"
        print(f"\nUser: {query}")
        print("Agent: ", end="", flush=True)
        
        response_chunks = []
        async for chunk in agent.run(query, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)
                response_chunks.append(chunk.text)
        print("\n")
        
        # Verify we got a response
        full_response = "".join(response_chunks)
        assert len(full_response) > 0, "Agent should return a response"
