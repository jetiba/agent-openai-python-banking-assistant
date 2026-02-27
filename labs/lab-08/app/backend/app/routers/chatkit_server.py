"""ChatKit server for Lab 8 — Simple triage between AccountAgent and PaymentAgent.

Compared to Lab 7 this server:
* Accepts attachments via the two-phase ChatKit upload protocol.
* Routes each message to either **AccountAgent** (general banking Q&A) or
  **PaymentAgent** (invoice scanning & bill payments) using a lightweight
  keyword + attachment heuristic.

Uses MAF's built-in ``stream_agent_response`` helper for ChatKit event
conversion — same pattern as Lab 7.
"""

import logging
from typing import AsyncIterator, Any

from chatkit.server import ChatKitServer
from chatkit.types import ThreadMetadata, UserMessageItem

from agent_framework import AgentSession
from agent_framework.chatkit import stream_agent_response, simple_to_agent_input

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

    Uses MAF's ``stream_agent_response`` for SSE event conversion.
    A fresh Agent instance is built per request to avoid stale state.
    """

    def __init__(
        self,
        account_agent: AccountAgent,
        payment_agent: PaymentAgent,
        store: MemoryStore,
        origin: str | None = None,
    ):
        if origin is None:
            origin = "http://localhost:8001"
        attachment_store = AttachmentMetadataStore(
            base_url=origin,
            metadata_store=store,
        )
        super().__init__(store, attachment_store)
        self.account_agent = account_agent
        self.payment_agent = payment_agent
        self.sessions: dict[str, AgentSession] = {}

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
    #  ChatKit respond — async generator yielding SSE events              #
    # ------------------------------------------------------------------ #

    async def respond(
        self,
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator:
        """Stream a triaged response as ChatKit events."""

        # Handle the case where input is None (e.g. after tool output)
        if input is None:
            logger.warning("Thread %s — respond() called with input=None, skipping", thread.id)
            return

        # 1. Convert ChatKit user message → MAF messages
        messages = await simple_to_agent_input(input)
        if not messages:
            logger.warning("Thread %s — no agent messages from input, skipping", thread.id)
            return

        # Extract plain-text and attachment info
        user_text = ""
        for part in input.content:
            if hasattr(part, "text"):
                user_text += part.text

        attachment_ids = []
        if input.attachments:
            attachment_ids = [a.id for a in input.attachments]
        has_attachments = len(attachment_ids) > 0

        # 2. Triage: choose the right agent
        if self._should_use_payment_agent(user_text, has_attachments):
            agent = await self.payment_agent.build_af_agent()
            # Append attachment reference so the agent can call scan_invoice
            if attachment_ids:
                user_text += f" [attachment_id: {attachment_ids[0]}]"
            logger.info("Thread %s → PaymentAgent — user: %s", thread.id, user_text[:80])
        else:
            agent = await self.account_agent.build_af_agent()
            logger.info("Thread %s → AccountAgent — user: %s", thread.id, user_text[:80])

        # 3. Get or create a session for this ChatKit thread
        if thread.id not in self.sessions:
            self.sessions[thread.id] = agent.create_session()
        session = self.sessions[thread.id]

        # 4. Stream agent response using MAF's built-in helper
        try:
            response_stream = agent.run(user_text, stream=True, session=session)
            async for event in stream_agent_response(response_stream, thread.id):
                yield event
            logger.info("Thread %s — stream finished", thread.id)
        except Exception:
            logger.exception("Thread %s — error during agent.run streaming", thread.id)
            raise

        # 5. Set thread title from the first user message
        if not thread.title or thread.title == "New thread":
            if user_text.strip():
                thread.title = user_text[:50].strip()
                await self.store.save_thread(thread, context)
