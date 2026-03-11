"""Simplified ChatKit server for Lab 7 — Single Foundry v2 Agent with Provider.

Uses MAF's built-in ``stream_agent_response`` helper for ChatKit event
conversion. Sessions are bound to Foundry conversations so that message
history is managed server-side via AzureAIProjectAgentProvider.
"""

import logging
from typing import AsyncIterator, Any

from chatkit.server import ChatKitServer
from chatkit.types import ThreadMetadata, UserMessageItem

from agent_framework import AgentSession
from agent_framework.chatkit import stream_agent_response, simple_to_agent_input

from app.agents.account_agent import AccountAgent
from app.routers.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class BankingAssistantChatKitServer(ChatKitServer):
    """ChatKit server backed by a single conversational agent using AzureAIProjectAgentProvider.

    Uses MAF's ``stream_agent_response`` for SSE event conversion.
    Sessions are bound to Foundry conversations (conversation IDs) so that
    the server manages history automatically.
    """

    def __init__(self, account_agent: AccountAgent, store: MemoryStore):
        super().__init__(store)
        self.account_agent = account_agent
        # Map ChatKit thread id → Foundry conversation id
        self._thread_conversations: dict[str, str] = {}
        # Map conversation id → AgentSession
        self._sessions: dict[str, AgentSession] = {}

    # ------------------------------------------------------------------ #
    #  ChatKit respond — async generator yielding SSE events              #
    # ------------------------------------------------------------------ #
    async def respond(
        self,
        thread: ThreadMetadata,
        input: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator:
        """Stream a single-agent response as ChatKit events."""

        # Handle the case where input is None (e.g. after tool output)
        if input is None:
            logger.warning("Thread %s — respond() called with input=None, skipping", thread.id)
            return

        # 1. Convert ChatKit user message → MAF messages
        messages = await simple_to_agent_input(input)
        if not messages:
            logger.warning("Thread %s — no agent messages from input, skipping", thread.id)
            return

        # Extract plain-text for logging / thread title
        user_text = ""
        for part in input.content:
            if hasattr(part, "text"):
                user_text += part.text
        logger.info("Thread %s — user: %s", thread.id, user_text[:80])

        # 2. Build the agent (cached after first call)
        agent = await self.account_agent.build_af_agent()
        logger.info("Thread %s — agent built successfully", thread.id)

        # 3. Get or create a Foundry conversation + session for this ChatKit thread
        if thread.id not in self._thread_conversations:
            conversation_id, session = await self.account_agent.create_conversation_session()
            self._thread_conversations[thread.id] = conversation_id
            self._sessions[conversation_id] = session
            logger.info(
                "Thread %s — created Foundry conversation %s",
                thread.id, conversation_id,
            )
        else:
            conversation_id = self._thread_conversations[thread.id]
            if conversation_id not in self._sessions:
                session = await self.account_agent.get_session_for_conversation(conversation_id)
                self._sessions[conversation_id] = session
            else:
                session = self._sessions[conversation_id]
            logger.info(
                "Thread %s — reusing Foundry conversation %s",
                thread.id, conversation_id,
            )

        # 4. Stream agent response using MAF's built-in helper
        try:
            response_stream = agent.run(
                user_text, stream=True, session=session, options={"store": True},
            )
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
