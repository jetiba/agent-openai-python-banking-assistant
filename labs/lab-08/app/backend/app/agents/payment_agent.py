"""Payment agent for Lab 8 — Foundry v2 agent with Document Intelligence tool.

Introduced in Lab 8 alongside the existing AccountAgent.  While AccountAgent
handles general banking Q&A, this agent specialises in invoice / bill
scanning via the ``scan_invoice`` tool powered by Azure Document Intelligence.

Uses AzureAIProjectAgentProvider for agent creation and Foundry conversation-
based session management.
"""

import logging
from datetime import datetime

from agent_framework import Agent, AgentSession
from agent_framework.azure import AzureAIProjectAgentProvider

from app.helpers.document_intelligence_scanner import DocumentIntelligenceInvoiceScanHelper

logger = logging.getLogger(__name__)


class PaymentAgent:
    """A payment assistant agent that scans invoices using Document Intelligence.

    Uses the ``scan_invoice`` tool to extract structured data from uploaded
    invoice images or PDFs and helps users prepare bill payments.
    """

    instructions = """
    You are a personal financial advisor who helps users with their bill
    payments.  The user may want to pay a bill by uploading a photo or
    document of the bill.

    When an attachment is included in a message (indicated by
    [attachment_id: <id>]), use the ``scan_invoice`` tool with the provided
    attachment id to extract data from the document.  Present the extracted
    fields (vendor name, invoice id, date, total, etc.) clearly in a
    formatted markdown table.

    After scanning, offer to help the user proceed with the payment by
    summarising the key details (payee, amount, due date).

    Current date and time: {current_date_time}

    Always use markdown to format your response.
    Always be helpful, concise, and professional.

    Note: You currently do not have access to any real payment processing
    system.  If a user asks to execute a payment, let them know that this
    feature will be available in a future update and show them the extracted
    invoice details.

    # Upload image example
    user: please help me pay this bill [attachment_id: atc_3a0a727d]
    assistant: Let me scan that invoice for you…
    """

    name = "PaymentAgent"
    description = "A payment assistant that scans invoices and helps with bill payments."

    def __init__(
        self,
        provider: AzureAIProjectAgentProvider,
        document_scanner_helper: DocumentIntelligenceInvoiceScanHelper,
    ):
        self.provider = provider
        self.document_scanner_helper = document_scanner_helper
        self._agent: Agent | None = None

    async def build_af_agent(self) -> Agent:
        """Build and return an Agent Framework agent with the scan_invoice tool."""
        if self._agent is not None:
            return self._agent

        logger.info("Initializing Payment Agent with Document Intelligence tool")

        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_instructions = PaymentAgent.instructions.format(
            current_date_time=current_date_time,
        )

        self._agent = await self.provider.create_agent(
            name=PaymentAgent.name,
            instructions=full_instructions,
            description=PaymentAgent.description,
            tools=[self.document_scanner_helper.scan_invoice],
        )
        return self._agent

    async def create_conversation_session(self) -> tuple[str, AgentSession]:
        """Create a Foundry conversation and return (conversation_id, session)."""
        agent = await self.build_af_agent()

        openai_client = agent.client.project_client.get_openai_client()
        conversation = await openai_client.conversations.create()
        conversation_id = conversation.id
        logger.info("Created Foundry conversation for PaymentAgent: %s", conversation_id)

        session = agent.get_session(service_session_id=conversation_id)
        return conversation_id, session

    async def get_session_for_conversation(self, conversation_id: str) -> AgentSession:
        """Return a session bound to an existing Foundry conversation."""
        agent = await self.build_af_agent()
        return agent.get_session(service_session_id=conversation_id)
