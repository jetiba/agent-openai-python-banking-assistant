"""Payment agent for Lab 9 — Foundry v2 agent with DI tool + Payment API MCP.

Compared to Lab 8 (scan_invoice only), this agent now also connects to
the Payment API via MCP Streamable HTTP to process actual payments after
scanning invoices.
"""

import logging
from datetime import datetime

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.azure import AzureAIClient

from app.helpers.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper

logger = logging.getLogger(__name__)


class PaymentAgent:
    """A payment assistant with invoice scanning and MCP payment processing.

    Combines the local ``scan_invoice`` tool (Azure Document Intelligence) with
    the Payment API MCP server to provide end-to-end invoice-to-payment flow.
    """

    instructions = """
    You are a personal financial advisor for Woodgrove Bank who helps users
    with bill payments.  You can scan invoices and process payments.

    Current date and time: {current_date_time}

    You have access to the following capabilities:

    **Invoice Scanning** (scan_invoice tool):
    When a user uploads an invoice or document (indicated by
    [attachment_id: <id>]), use the scan_invoice tool with the provided
    attachment id to extract data such as vendor name, invoice ID, date,
    and total amount.

    **Payment API** (MCP tool — processPayment):
    After extracting invoice data, you can process the payment by calling
    processPayment with the account_id, amount, description, timestamp,
    and optionally recipient_name, payment_type, etc.

    **Workflow:**
    1. If the user uploads an invoice, use scan_invoice to extract details.
    2. Present the extracted invoice data in a clear markdown table.
    3. Ask the user to confirm before processing.
    4. When confirmed, use processPayment to submit the payment.

    Always use markdown to format your response.
    Always be helpful, concise, and professional.
    Verify amounts before processing and always confirm with the user.

    # Upload image example
    user: please help me pay this bill [attachment_id: atc_3a0a727d]
    assistant: Let me scan that invoice for you…
    """

    name = "PaymentAgent"
    description = "A payment assistant that scans invoices and processes payments."

    def __init__(
        self,
        azure_ai_client: AzureAIClient,
        document_scanner_helper: DocumentIntelligenceInvoiceScanHelper,
        payment_api_mcp_url: str,
    ):
        self.azure_ai_client = azure_ai_client
        self.document_scanner_helper = document_scanner_helper
        self.payment_api_mcp_url = payment_api_mcp_url

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent with scan_invoice + Payment MCP."""
        logger.info("Initializing Payment Agent with DI tool + Payment MCP")

        payment_mcp = MCPStreamableHTTPTool(
            name="payment-api",
            url=self.payment_api_mcp_url,
            description="Payment processing: submit and process payments.",
        )

        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_instructions = PaymentAgent.instructions.format(
            current_date_time=current_date_time,
        )

        agent = Agent(
            client=self.azure_ai_client,
            instructions=full_instructions,
            name=PaymentAgent.name,
            tools=[self.document_scanner_helper.scan_invoice, payment_mcp],
        )
        return agent
