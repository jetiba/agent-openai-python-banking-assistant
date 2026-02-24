from agent_framework.azure import AzureAIClient
from agent_framework import Agent

import logging


logger = logging.getLogger(__name__)


class AccountAgent:
    """A simple conversational banking assistant agent.

    This agent uses Azure AI Foundry v2 to answer general banking questions.
    It does not have any tools or MCP connections — it is purely conversational.
    """

    instructions = """
    You are a friendly personal banking assistant who helps users with general
    banking questions. You can provide information about common banking topics
    such as account types, interest rates, banking fees, and financial advice.

    Always use markdown to format your response.
    Always be helpful, concise, and professional.

    Note: You currently do not have access to any real account data or
    transaction systems. If a user asks about their specific account details,
    let them know that this feature will be available soon and offer to help
    with general banking questions instead.
    """

    name = "AccountAgent"
    description = "A conversational banking assistant that answers general banking questions."

    def __init__(self, azure_ai_client: AzureAIClient):
        self.azure_ai_client = azure_ai_client

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent."""
        logger.info("Initializing Account Agent")

        agent = Agent(
            client=self.azure_ai_client,
            instructions=AccountAgent.instructions,
            name=AccountAgent.name,
        )
        return agent
