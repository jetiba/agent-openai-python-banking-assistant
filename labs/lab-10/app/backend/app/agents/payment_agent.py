"""Payment agent for Lab 10 — Full payment specialist with all MCP servers.

Compared to Lab 9 (Payment MCP + scan_invoice), this agent now connects
to **all three** MCP servers because the payment workflow requires:

* **Account MCP** — look up account IDs and payment methods
* **Transaction MCP** — check if a bill has already been paid
* **Payment MCP** — submit the actual payment (with human approval)

New in Lab 10:
* ``handoff_to_triage_agent`` tool — routes back to triage
* ``approval_mode`` on Payment MCP — ``processPayment`` requires
  explicit user approval before execution.
"""

import logging
from datetime import datetime

from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.azure import AzureAIClient

from app.helpers.document_intelligence_scanner import (
    DocumentIntelligenceInvoiceScanHelper,
)

logger = logging.getLogger(__name__)


# ── Handoff tool ──────────────────────────────────────────────────────
@tool(
    name="handoff_to_TriageAgent",
    description="Handoff to the triage-agent agent.",
)
def handoff_to_triage_agent(context: str | None = None) -> str:
    """Transfer the conversation back to the triage agent."""
    return "Handoff to TriageAgent"


class PaymentAgent:
    """Banking assistant specialist — invoice scanning and payment processing."""

    instructions = """
    You are a personal financial advisor for Woodgrove Bank who helps users
    with their recurrent bill payments.

    The user may want to pay the bill uploading a photo of the bill, or may
    start the payment checking transactions history for a specific payee.

    For the bill payment you need to know: bill id or invoice number, payee
    name, and the total amount.  If you don't have enough information, ask
    the user to provide the missing details.

    Current date and time: {current_date_time}
    Always use the below logged-in user details to retrieve account info:
       {user_mail}

    **Workflow:**
    1. If the user uploads an invoice image, scan it with ``scan_invoice``
       and always ask the user to confirm the extracted data.
    2. Check if the bill has already been paid using transaction history.
    3. Ask for the payment method based on available methods on the account.
    4. If bank transfer, check if the payee is in the beneficiaries list.
       If not, ask for the payee bank code.
    5. Check if the selected payment method has enough funds.
    6. Before submitting, present payment details and ask for confirmation.
    7. Use ``processPayment`` to submit. Include the invoice ID in the
       payment description (e.g. "payment for invoice 1527248").

    **Rules:**
    - Payment status is 'paid' for CreditCard, 'pending' for BankTransfer.
    - Extract a payment category from the payee name (utilities, rent, etc.).
    - Don't guess accountId or paymentMethodId — always use functions.
    - Use markdown tables to display extracted data and payment details.
    - If the user asks about account info or transaction history unrelated
      to a payment flow, hand off via handoff_to_TriageAgent.

    # Upload image example
    user: please help me pay this bill [attachment_id: atc_3a0a727d]
    assistant: Let me scan that invoice for you…
    """

    name = "PaymentAgent"
    description = (
        "This agent manages user payments: invoice scanning, payment "
        "requests, and bill payments."
    )

    def __init__(
        self,
        azure_ai_client: AzureAIClient,
        document_scanner_helper: DocumentIntelligenceInvoiceScanHelper,
        account_api_mcp_url: str,
        transaction_api_mcp_url: str,
        payment_api_mcp_url: str,
    ):
        self.azure_ai_client = azure_ai_client
        self.document_scanner_helper = document_scanner_helper
        self.account_api_mcp_url = account_api_mcp_url
        self.transaction_api_mcp_url = transaction_api_mcp_url
        self.payment_api_mcp_url = payment_api_mcp_url

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent with all MCP tools + scan_invoice."""
        logger.info("Building PaymentAgent with Account + Transaction + Payment MCP tools")

        account_mcp = MCPStreamableHTTPTool(
            name="account-api",
            url=self.account_api_mcp_url,
            description="Account lookup: accounts, payment methods, beneficiaries.",
        )

        transaction_mcp = MCPStreamableHTTPTool(
            name="transaction-api",
            url=self.transaction_api_mcp_url,
            description="Transaction history: check if a bill was already paid.",
        )

        payment_mcp = MCPStreamableHTTPTool(
            name="payment-api",
            url=self.payment_api_mcp_url,
            description="Payment processing: submit and process payments.",
            approval_mode={"always_require_approval": ["processPayment"]},
        )

        user_mail = "bob.user@contoso.com"
        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_instructions = PaymentAgent.instructions.format(
            current_date_time=current_date_time,
            user_mail=user_mail,
        )

        agent = Agent(
            client=self.azure_ai_client,
            instructions=full_instructions,
            name=PaymentAgent.name,
            tools=[
                account_mcp,
                transaction_mcp,
                payment_mcp,
                self.document_scanner_helper.scan_invoice,
                handoff_to_triage_agent,
            ],
        )

        # Expose tools in default_options so CustomHandoffBuilder can
        # detect them and avoid injecting duplicate handoff tools.
        agent.default_options["tools"] = [
            account_mcp,
            transaction_mcp,
            payment_mcp,
            self.document_scanner_helper.scan_invoice,
            handoff_to_triage_agent,
        ]
        return agent
