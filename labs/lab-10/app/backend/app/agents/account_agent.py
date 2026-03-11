"""Account agent for Lab 10 — Specialist with Account MCP only.

Compared to Lab 9 (Account + Transaction MCP merged), this agent is
slimmed back to **Account MCP only**.  Transaction history is now handled
by the dedicated ``TransactionHistoryAgent``.

New in Lab 10:
* ``handoff_to_triage_agent`` tool — allows the agent to hand the
  conversation back to the triage agent when the request is outside its
  scope (e.g. transaction or payment queries).
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


class AccountAgent:
    """Banking assistant specialist — account information via MCP."""

    instructions = """
    You are a personal banking assistant for Woodgrove Bank who helps users
    with **account inquiries only**.

    Current date and time: {current_date_time}
    Always use the below logged-in user details to retrieve account info:
       {user_mail}

    You have access to the following capabilities via the Account API MCP:

    - Look up accounts by username (getAccountsByUserName)
    - Get account details and payment methods (getAccountDetails)
    - List registered beneficiaries (getRegisteredBeneficiary)
    - View credit cards (getCreditCards) and card details (getCardDetails)

    **Guidelines:**
    - When a user asks about their accounts, use their username to look up
      accounts first, then fetch details as needed.
    - Present financial data in clear, well-formatted markdown tables.
    - Always be helpful, concise, and professional.
    - If the user asks about transaction history or payments, hand off to
      the appropriate specialist by calling handoff_to_TriageAgent.
    """

    name = "AccountAgent"
    description = (
        "This agent manages user bank account information such as "
        "account details, payment methods, cards, and beneficiaries."
    )

    def __init__(
        self,
        azure_ai_client: AzureAIClient,
        account_api_mcp_url: str,
    ):
        self.azure_ai_client = azure_ai_client
        self.account_api_mcp_url = account_api_mcp_url

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent with Account MCP tool."""
        logger.info("Building AccountAgent with Account MCP tool")

        account_mcp = MCPStreamableHTTPTool(
            name="account-api",
            url=self.account_api_mcp_url,
            description="Account management: lookup accounts, details, beneficiaries, credit cards.",
        )

        user_mail = "bob.user@contoso.com"
        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_instructions = AccountAgent.instructions.format(
            current_date_time=current_date_time,
            user_mail=user_mail,
        )

        agent = Agent(
            client=self.azure_ai_client,
            instructions=full_instructions,
            name=AccountAgent.name,
            tools=[account_mcp, handoff_to_triage_agent],
        )

        # Expose tools in default_options so CustomHandoffBuilder can
        # detect them and avoid injecting duplicate handoff tools.
        agent.default_options["tools"] = [account_mcp, handoff_to_triage_agent]
        return agent
