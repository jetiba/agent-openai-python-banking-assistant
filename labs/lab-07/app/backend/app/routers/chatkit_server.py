"""Simplified ChatKit server for Lab 7 — Single Foundry v2 Agent.

No tools, no handoff, no MCP. Conversation history is managed server-side
by Azure AI Foundry (OOB session management). Thread metadata for the
ChatKit UI is kept in a lightweight MemoryStore.
"""

import logging
import uuid
from typing import AsyncIterator

from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    InputContext,
    TextContentPart,
    Thread,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdated,
    UserMessageItem,
)

from app.agents.account_agent import AccountAgent
from app.routers.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class BankingAssistantChatKitServer(ChatKitServer):
    """ChatKit server backed by a single conversational agent.

    A built Agent instance is cached per ChatKit thread so that the
    Foundry v2 backend can maintain conversation continuity within
    the same thread.
    """

    # Class-level store shared across all requests (ChatKit UI thread list)
    metadata_store = MemoryStore()

    # Cache of built Agent instances keyed by ChatKit thread ID
    _agents: dict[str, object] = {}

    def __init__(self, account_agent: AccountAgent):
        super().__init__(BankingAssistantChatKitServer.metadata_store)
        self.account_agent = account_agent

    async def _get_agent(self, thread_id: str):
        """Return a cached Agent for the thread, building one if needed."""
        if thread_id not in BankingAssistantChatKitServer._agents:
            agent = await self.account_agent.build_af_agent()
            BankingAssistantChatKitServer._agents[thread_id] = agent
        return BankingAssistantChatKitServer._agents[thread_id]

    # ------------------------------------------------------------------ #
    #  ChatKit respond — async generator yielding SSE events              #
    # ------------------------------------------------------------------ #
    async def respond(
        self,
        thread: Thread,
        input: UserMessageItem,
        context: InputContext,
    ) -> AsyncIterator:
        """Stream a single-agent response as ChatKit events."""

        # 1. Extract plain text from the ChatKit user message
        text = ""
        for part in input.content:
            if hasattr(part, "text"):
                text += part.text

        logger.info("Thread %s — user: %s", thread.id, text[:80])

        # 2. Get (or build) the agent for this thread
        agent = await self._get_agent(thread.id)

        # 3. Stream the agent response, converting chunks → ChatKit events
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        accumulated = ""
        started = False

        async for chunk in agent.run(text, stream=True):
            if chunk.text:
                if not started:
                    # Signal the start of an assistant message
                    yield ThreadItemAddedEvent(
                        item=AssistantMessageItem(id=message_id, content=[])
                    )
                    started = True

                accumulated += chunk.text
                yield ThreadItemUpdated(
                    item_id=message_id,
                    delta=AssistantMessageContentPartTextDelta(text=chunk.text),
                )

        # 4. Emit the completed assistant message
        if started:
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id=message_id,
                    content=[TextContentPart(text=accumulated)],
                )
            )

        # 5. Set thread title from the first user message
        if not thread.title or thread.title == "New thread":
            thread.title = text[:50].strip()
            await self.store.save_thread(thread, context)
