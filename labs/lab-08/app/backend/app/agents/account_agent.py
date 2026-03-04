from agent_framework.azure import AzureAIProjectAgentProvider
from agent_framework import Agent, AgentSession

import logging


logger = logging.getLogger(__name__)


class AccountAgent:
    """A simple conversational banking assistant agent.

    This agent uses Azure AI Foundry v2 with AzureAIProjectAgentProvider
    to answer general banking questions. Sessions are bound to Foundry
    conversations so history is managed server-side.
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

    def __init__(self, provider: AzureAIProjectAgentProvider):
        self.provider = provider
        self._agent: Agent | None = None

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent via the provider."""
        if self._agent is not None:
            return self._agent

        logger.info("Initializing Account Agent via AzureAIProjectAgentProvider")

        self._agent = await self.provider.create_agent(
            name=AccountAgent.name,
            instructions=AccountAgent.instructions,
            description=AccountAgent.description,
        )
        return self._agent

    async def create_conversation_session(self) -> tuple[str, AgentSession]:
        """Create a Foundry conversation and return (conversation_id, session).

        The session is bound to the Foundry conversation so that message
        history is managed server-side.
        """
        agent = await self.build_af_agent()

        # Create a Foundry conversation via the underlying OpenAI client
        openai_client = agent.client.project_client.get_openai_client()
        conversation = await openai_client.conversations.create()
        conversation_id = conversation.id
        logger.info("Created Foundry conversation: %s", conversation_id)

        # Bind the session to the conversation id
        session = agent.get_session(service_session_id=conversation_id)
        return conversation_id, session

    async def get_session_for_conversation(self, conversation_id: str) -> AgentSession:
        """Return a session bound to an existing Foundry conversation."""
        agent = await self.build_af_agent()
        return agent.get_session(service_session_id=conversation_id)
