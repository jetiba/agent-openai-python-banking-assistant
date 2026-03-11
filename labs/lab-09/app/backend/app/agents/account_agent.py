"""Account agent for Lab 9 — Foundry v2 agent with MCP tool connections.

Compared to Lab 7 (conversational only), this agent now connects to the
Account API and Transaction API via MCP Streamable HTTP to fetch real
customer data, account details, beneficiaries, credit cards, and
transaction history.

Uses AzureAIProjectAgentProvider for agent creation and Foundry conversation-
based session management.
"""

import logging
from datetime import datetime

from agent_framework import Agent, AgentSession, MCPStreamableHTTPTool
from agent_framework.azure import AzureAIProjectAgentProvider

logger = logging.getLogger(__name__)


class AccountAgent:
    """A banking assistant agent with MCP connections to Account & Transaction APIs."""

    instructions = """
    You are a personal banking assistant for Woodgrove Bank who helps users
    with account inquiries and transaction history.

    Current date and time: {current_date_time}

    You have access to the following capabilities via MCP tools:

    **Account API:**
    - Look up accounts by username (getAccountsByUserName)
    - Get account details and payment methods (getAccountDetails)
    - List registered beneficiaries (getRegisteredBeneficiary)
    - View credit cards (getCreditCards) and card details (getCardDetails)

    **Transaction API:**
    - Get recent transactions for an account (getLastTransactions)
    - Search transactions by recipient name (getTransactionsByRecipientName)
    - View card-specific transactions (getCardTransactions)

    **Guidelines:**
    - When a user asks about their accounts, use their username to look up
      accounts first, then fetch details as needed.
    - Present financial data in clear, well-formatted markdown tables.
    - Always be helpful, concise, and professional.
    - If you encounter an error fetching data, explain it clearly and suggest
      the user try again or provide different details.
    """

    name = "AccountAgent"
    description = "A banking assistant with access to account and transaction data via MCP."

    def __init__(
        self,
        provider: AzureAIProjectAgentProvider,
        account_api_mcp_url: str,
        transaction_api_mcp_url: str,
    ):
        self.provider = provider
        self.account_api_mcp_url = account_api_mcp_url
        self.transaction_api_mcp_url = transaction_api_mcp_url
        self._agent: Agent | None = None

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent with MCP tools."""
        if self._agent is not None:
            return self._agent

        logger.info("Initializing Account Agent with MCP tools")

        account_mcp = MCPStreamableHTTPTool(
            name="account-api",
            url=self.account_api_mcp_url,
            description="Account management: lookup accounts, details, beneficiaries, credit cards.",
        )

        transaction_mcp = MCPStreamableHTTPTool(
            name="transaction-api",
            url=self.transaction_api_mcp_url,
            description="Transaction history: recent transactions, search by recipient, card transactions.",
        )

        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_instructions = AccountAgent.instructions.format(
            current_date_time=current_date_time,
        )

        self._agent = await self.provider.create_agent(
            name=AccountAgent.name,
            instructions=full_instructions,
            description=AccountAgent.description,
            tools=[account_mcp, transaction_mcp],
        )
        return self._agent

    async def create_conversation_session(self) -> tuple[str, AgentSession]:
        """Create a Foundry conversation and return (conversation_id, session)."""
        agent = await self.build_af_agent()

        openai_client = agent.client.project_client.get_openai_client()
        conversation = await openai_client.conversations.create()
        conversation_id = conversation.id
        logger.info("Created Foundry conversation for AccountAgent: %s", conversation_id)

        session = agent.get_session(service_session_id=conversation_id)
        return conversation_id, session

    async def get_session_for_conversation(self, conversation_id: str) -> AgentSession:
        """Return a session bound to an existing Foundry conversation."""
        agent = await self.build_af_agent()
        return agent.get_session(service_session_id=conversation_id)
