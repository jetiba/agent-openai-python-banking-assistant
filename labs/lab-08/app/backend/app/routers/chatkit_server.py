"""ChatKit server for Lab 8 — Simple triage between AccountAgent and PaymentAgent.

Compared to Lab 7 this server:
* Accepts attachments via the two-phase ChatKit upload protocol.
* Routes each message to either **AccountAgent** (general banking Q&A) or
  **PaymentAgent** (invoice scanning & bill payments) using a lightweight
  keyword + attachment heuristic.
"""

import logging
import uuid
from typing import Any

from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    TextContentPart,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdated,
    UserMessageItem,
)

from app.agents.account_agent import AccountAgent
from app.agents.payment_agent import PaymentAgent
from app.routers.attachment_store import AttachmentMetadataStore
from app.routers.memory_store import MemoryStore

logger = logging.getLogger(__name__)

# Keywords that hint at payment / invoice intent.
PAYMENT_KEYWORDS = {"pay", "payment", "invoice", "bill", "scan", "receipt"}


class BankingAssistantChatKitServer(ChatKitServer):
    """ChatKit server with simple per-message triage.

    Routing heuristic:
    * If the message contains **attachments** → PaymentAgent
    * If the message text contains any of ``PAYMENT_KEYWORDS`` → PaymentAgent
    * Otherwise → AccountAgent
    """

    metadata_store = MemoryStore()
    _account_agents: dict[str, object] = {}
    _payment_agents: dict[str, object] = {}

    def __init__(
        self,
        account_agent: AccountAgent,
        payment_agent: PaymentAgent,
        origin: str | None = None,
    ):
        if origin is None:
            origin = "http://localhost:8001"
        attachment_store = AttachmentMetadataStore(
            base_url=origin,
            metadata_store=BankingAssistantChatKitServer.metadata_store,
        )
        super().__init__(
            BankingAssistantChatKitServer.metadata_store,
            attachment_store,
        )
        self.account_agent = account_agent
        self.payment_agent = payment_agent

    # ------------------------------------------------------------------ #
    #  Agent cache helpers                                                 #
    # ------------------------------------------------------------------ #

    async def _get_account_agent(self, thread_id: str):
        if thread_id not in BankingAssistantChatKitServer._account_agents:
            agent = await self.account_agent.build_af_agent()
            BankingAssistantChatKitServer._account_agents[thread_id] = agent
        return BankingAssistantChatKitServer._account_agents[thread_id]

    async def _get_payment_agent(self, thread_id: str):
        if thread_id not in BankingAssistantChatKitServer._payment_agents:
            agent = await self.payment_agent.build_af_agent()
            BankingAssistantChatKitServer._payment_agents[thread_id] = agent
        return BankingAssistantChatKitServer._payment_agents[thread_id]

    # ------------------------------------------------------------------ #
    #  Triage                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _should_use_payment_agent(text: str, has_attachments: bool) -> bool:
        """Simple keyword & attachment based triage."""
        if has_attachments:
            return True
        words = set(text.lower().split())
        return bool(words & PAYMENT_KEYWORDS)

    # ------------------------------------------------------------------ #
    #  Respond                                                             #
    # ------------------------------------------------------------------ #

    async def respond(self, thread, input, context):
        # Extract text from the user message
        text = ""
        for part in input.content:
            if hasattr(part, "text"):
                text += part.text

        # Extract attachment ids (if any)
        attachment_ids = []
        if input.attachments:
            attachment_ids = [a.id for a in input.attachments]
        has_attachments = len(attachment_ids) > 0

        # Triage: choose the right agent
        if self._should_use_payment_agent(text, has_attachments):
            agent = await self._get_payment_agent(thread.id)
            # Append attachment reference so the agent can call scan_invoice
            if attachment_ids:
                text += f" [attachment_id: {attachment_ids[0]}]"
            logger.info("Thread %s → PaymentAgent — user: %s", thread.id, text[:80])
        else:
            agent = await self._get_account_agent(thread.id)
            logger.info("Thread %s → AccountAgent — user: %s", thread.id, text[:80])

        # Stream model response
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        accumulated = ""
        started = False

        async for chunk in agent.run(text, stream=True):
            if chunk.text:
                if not started:
                    yield ThreadItemAddedEvent(
                        item=AssistantMessageItem(id=message_id, content=[])
                    )
                    started = True
                accumulated += chunk.text
                yield ThreadItemUpdated(
                    item_id=message_id,
                    delta=AssistantMessageContentPartTextDelta(text=chunk.text),
                )

        if started:
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id=message_id, content=[TextContentPart(text=accumulated)]
                )
            )

        # Update thread title on first message
        if not thread.title or thread.title == "New thread":
            thread.title = text[:50].strip()
            await self.store.save_thread(thread, context)
