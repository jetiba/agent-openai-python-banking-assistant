"""Transaction history agent for Lab 10 — NEW specialist.

This agent is responsible for **transaction history** queries.  It
connects to both the Account API MCP (to resolve account IDs) and the
Transaction API MCP (to fetch movements, search by recipient, view card
transactions).

It includes a ``handoff_to_triage_agent`` tool so the conversation can
be routed back to the triage agent for requests outside its scope.
"""

import logging
from datetime import datetime

from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.azure import AzureAIClient

logger = logging.getLogger(__name__)


# ── Handoff tool ──────────────────────────────────────────────────────
@tool(
    name="handoff_to_TriageAgent",
    description="Handoff to the triage-agent agent.",
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"


class TransactionHistoryAgent:
    """Banking assistant specialist — transaction history via MCP."""

    instructions = """
    You are a personal banking assistant for Woodgrove Bank who helps users
    with **transaction history and banking movements**.

    Current date and time: {current_date_time}
    Always use the below logged-in user details to retrieve account info:
       {user_mail}

    You have access to the following capabilities:

    **Account API** (to resolve account IDs):
    - Look up accounts by username (getAccountsByUserName)
    - Get account details (getAccountDetails)

    **Transaction API:**
    - Get recent transactions for an account (getLastTransactions)
    - Search transactions by recipient name (getTransactionsByRecipientName)
    - View card-specific transactions (getCardTransactions)

    **Guidelines:**
    - When a user asks about transactions, first retrieve their account(s)
      via getAccountsByUserName, then fetch transactions for that account.
    - Present transaction data in clear, well-formatted markdown tables.
    - Always be helpful, concise, and professional.
    - If the user asks about account details (cards, beneficiaries) or
      payments, hand off to the appropriate specialist by calling
      handoff_to_TriageAgent.
    """

    name = "TransactionHistoryAgent"
    description = (
        "This agent manages user banking movements and transaction history "
        "such as recent transactions, recipient search, and card transactions."
    )

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
        """Build and return an Agent Framework agent with Account + Transaction MCP tools."""
        logger.info("Building TransactionHistoryAgent with Account + Transaction MCP tools")

        account_mcp = MCPStreamableHTTPTool(
            name="account-api",
            url=self.account_api_mcp_url,
            description="Account lookup: resolve accounts by username, get account details.",
        )

        transaction_mcp = MCPStreamableHTTPTool(
            name="transaction-api",
            url=self.transaction_api_mcp_url,
            description="Transaction history: recent transactions, search by recipient, card transactions.",
        )

        user_mail = "bob.user@contoso.com"
        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_instructions = TransactionHistoryAgent.instructions.format(
            current_date_time=current_date_time,
            user_mail=user_mail,
        )

        agent = Agent(
            client=self.azure_ai_client,
            instructions=full_instructions,
            name=TransactionHistoryAgent.name,
            tools=[account_mcp, transaction_mcp, handoff_to_triage_agent],
        )

        # Expose tools in default_options so CustomHandoffBuilder can
        # detect them and avoid injecting duplicate handoff tools.
        agent.default_options["tools"] = [
            account_mcp,
            transaction_mcp,
            handoff_to_triage_agent,
        ]
        return agent
