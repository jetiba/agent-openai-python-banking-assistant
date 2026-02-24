"""Account agent for Lab 9 — Foundry v2 agent with MCP tool connections.

Compared to Lab 7 (conversational only), this agent now connects to the
Account API and Transaction API via MCP Streamable HTTP to fetch real
customer data, account details, beneficiaries, credit cards, and
transaction history.
"""

import logging
from datetime import datetime

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.azure import AzureAIClient

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
        azure_ai_client: AzureAIClient,
        account_api_mcp_url: str,
        transaction_api_mcp_url: str,
    ):
        self.azure_ai_client = azure_ai_client
        self.account_api_mcp_url = account_api_mcp_url
        self.transaction_api_mcp_url = transaction_api_mcp_url

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent with MCP tools."""
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

        agent = Agent(
            client=self.azure_ai_client,
            instructions=full_instructions,
            name=AccountAgent.name,
            tools=[account_mcp, transaction_mcp],
        )
        return agent
