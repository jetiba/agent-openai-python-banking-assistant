"""ChatKit server for Lab 10 — Multi-agent handoff with tool-approval widgets.

Compared to the Lab 8 server (which used keyword-based triage and
``stream_agent_response``), this implementation:

* Delegates **all** routing to the ``HandoffOrchestrator`` workflow.
* Converts ``WorkflowEvent`` → ChatKit events via ``ChatKitEventsHandler``.
* Supports ``action()`` for human-in-the-loop tool approval / rejection.
* Overrides ``_process_events()`` and ``_process_streaming_impl()`` so
  that ``ClientWidgetItem`` and ``CustomThreadItemDoneEvent`` (used for
  approval widgets) participate in the store-persistence and SSE
  streaming pipelines.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, AsyncIterator, Callable

from chatkit.actions import Action
from chatkit.errors import CustomStreamError, ErrorCode, StreamError
from chatkit.server import ChatKitServer, agents_sdk_user_agent_override
from chatkit.types import (
    ClientToolCallItem,
    ErrorEvent,
    HiddenContextItem,
    Page,
    Thread,
    ThreadCreatedEvent,
    ThreadItemDoneEvent,
    ThreadItemRemovedEvent,
    ThreadItemReplacedEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    ThreadUpdatedEvent,
    ThreadsAddClientToolOutputReq,
    ThreadsAddUserMessageReq,
    ThreadsCreateReq,
    ThreadsCustomActionReq,
    ThreadsRetryAfterItemReq,
    StreamingReq,
    UserMessageItem,
    WidgetItem,
)
from chatkit.widgets import Card
from agent_framework_chatkit import ThreadItemConverter

from app.agents._chatkit_events_handler import ChatKitEventsHandler
from app.agents.handoff_orchestrator import HandoffOrchestrator
from app.common.chatkit.types import ClientWidgetItem, CustomThreadItemDoneEvent
from app.routers.attachment_store import AttachmentMetadataStore
from app.routers.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class BankingAssistantChatKitServer(ChatKitServer[dict[str, Any]]):
    """ChatKit server backed by the ``HandoffOrchestrator`` workflow.

    A single long-lived instance is created per application process (the
    ``chat_routers`` singleton pattern).  It owns the ``MemoryStore``,
    ``AttachmentMetadataStore``, and ``ThreadItemConverter``.
    """

    def __init__(
        self,
        handoff_orchestrator: HandoffOrchestrator,
        store: MemoryStore,
        origin: str | None = None,
    ):
        if origin is None:
            origin = "http://localhost:8001"
            logger.warning(
                "Origin header missing; defaulting attachment base_url to %s",
                origin,
            )

        attachment_metadata_store = AttachmentMetadataStore(
            base_url=origin,
            metadata_store=store,
        )
        super().__init__(store, attachment_metadata_store)

        self.converter = ThreadItemConverter()
        self.handoff_orchestrator = handoff_orchestrator

    # ------------------------------------------------------------------ #
    #  Thread title helper                                                 #
    # ------------------------------------------------------------------ #

    async def _update_thread_title(
        self,
        thread: ThreadMetadata,
        user_message: UserMessageItem,
        context: dict[str, Any],
    ) -> None:
        first_text = "Untitled thread"
        for part in user_message.content:
            if hasattr(part, "text") and isinstance(part.text, str):
                first_text = part.text
                break
        thread.title = first_text[:50].strip()
        await self.store.save_thread(thread, context)

    # ------------------------------------------------------------------ #
    #  respond — user message → streaming agent events                     #
    # ------------------------------------------------------------------ #

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        if input_user_message is None:
            logger.debug("Received None user message — skipping")
            return

        logger.info("Processing message for thread %s", thread.id)

        try:
            # Extract attachment IDs
            attachment_ids: list[str] = []
            if input_user_message.attachments:
                attachment_ids = [a.id for a in input_user_message.attachments]

            # Convert to Agent Framework format
            agent_messages = await self.converter.to_agent_input(input_user_message)
            if not agent_messages:
                logger.warning("No messages after conversion")
                return

            last_message = agent_messages[-1]
            text = last_message.text
            if attachment_ids:
                text += f" [attachment_id: {attachment_ids[0]}]"

            # Stream through the handoff orchestrator
            af_events = self.handoff_orchestrator.processMessageStream(text, thread.id)
            handler = ChatKitEventsHandler()
            async for event in handler.handle_events(thread.id, af_events):
                yield event

            # Update thread title on the first message
            if not thread.title or thread.title == "New thread":
                await self._update_thread_title(thread, input_user_message, context)

        except Exception as e:
            logger.error(
                "Error processing message for thread %s: %s",
                thread.id,
                e,
                exc_info=True,
            )
            yield ErrorEvent(
                message=f"An error occurred while processing your message for thread {thread.id}"
            )

    # ------------------------------------------------------------------ #
    #  action — widget actions (e.g. tool approval)                        #
    # ------------------------------------------------------------------ #

    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        logger.info("Received action %s for thread %s", action.type, thread.id)

        try:
            if action.type == "approval":
                approved = action.payload.get("approved", False)
                call_id = action.payload.get("call_id")
                request_id = action.payload.get("request_id")
                tool_name = action.payload.get("tool_name")

                af_events = self.handoff_orchestrator.processToolApprovalResponse(
                    thread.id,
                    approved,
                    call_id=call_id,
                    request_id=request_id,
                    tool_name=tool_name,
                )
                handler = ChatKitEventsHandler()
                async for event in handler.handle_events(thread.id, af_events):
                    yield event

        except Exception as e:
            logger.error(
                "Error processing action for thread %s: %s",
                thread.id,
                e,
                exc_info=True,
            )
            yield ErrorEvent(
                message=f"An error occurred while processing your action for thread {thread.id}"
            )

    # ------------------------------------------------------------------ #
    #  _process_events — add CustomThreadItemDoneEvent persistence         #
    # ------------------------------------------------------------------ #

    async def _process_events(
        self,
        thread: ThreadMetadata,
        context: dict[str, Any],
        stream: Callable[[], AsyncIterator[ThreadStreamEvent]],
    ) -> AsyncIterator[ThreadStreamEvent]:
        await asyncio.sleep(0)  # allow the response to start streaming

        last_thread = thread.model_copy(deep=True)

        try:
            with agents_sdk_user_agent_override():
                async for event in stream():
                    match event:
                        # Persist both standard and custom "done" events
                        case ThreadItemDoneEvent() | CustomThreadItemDoneEvent():
                            await self.store.add_thread_item(
                                thread.id, event.item, context=context  # type: ignore[arg-type]
                            )
                        case ThreadItemRemovedEvent():
                            await self.store.delete_thread_item(
                                thread.id, event.item_id, context=context  # type: ignore[arg-type]
                            )
                        case ThreadItemReplacedEvent():
                            await self.store.save_item(
                                thread.id, event.item, context=context  # type: ignore[arg-type]
                            )

                    # Don't send hidden context items to the client
                    should_swallow = isinstance(event, ThreadItemDoneEvent) and isinstance(
                        event.item, HiddenContextItem
                    )
                    if not should_swallow:
                        yield event

                    # Persist thread changes made during streaming
                    if thread != last_thread:
                        last_thread = thread.model_copy(deep=True)
                        await self.store.save_thread(thread, context=context)  # type: ignore[arg-type]
                        yield ThreadUpdatedEvent(thread=self._to_thread_response(thread))

                if thread != last_thread:
                    last_thread = thread.model_copy(deep=True)
                    await self.store.save_thread(thread, context=context)  # type: ignore[arg-type]
                    yield ThreadUpdatedEvent(thread=self._to_thread_response(thread))

        except CustomStreamError as e:
            yield ErrorEvent(code="custom", message=e.message, allow_retry=e.allow_retry)
        except StreamError as e:
            yield ErrorEvent(code=e.code, allow_retry=e.allow_retry)
        except Exception as e:
            yield ErrorEvent(code=ErrorCode.STREAM_ERROR, allow_retry=True)
            logger.exception(e)

        if thread != last_thread:
            await self.store.save_thread(thread, context=context)  # type: ignore[arg-type]
            yield ThreadUpdatedEvent(thread=self._to_thread_response(thread))

    # ------------------------------------------------------------------ #
    #  _process_streaming_impl — add ThreadsCustomActionReq handling       #
    # ------------------------------------------------------------------ #

    async def _process_streaming_impl(
        self, request: StreamingReq, context: dict[str, Any]
    ) -> AsyncGenerator[ThreadStreamEvent, None]:
        match request:
            case ThreadsCreateReq():
                thread = Thread(
                    id=self.store.generate_thread_id(context),  # type: ignore[arg-type]
                    created_at=datetime.now(),
                    items=Page(),  # type: ignore[call-arg]
                )
                await self.store.save_thread(
                    ThreadMetadata(**thread.model_dump()),
                    context=context,
                )
                yield ThreadCreatedEvent(thread=self._to_thread_response(thread))
                user_message = await self._build_user_message_item(
                    request.params.input, thread, context
                )
                async for event in self._process_new_thread_item_respond(
                    thread, user_message, context
                ):
                    yield event

            case ThreadsAddUserMessageReq():
                thread = await self.store.load_thread(
                    request.params.thread_id, context=context
                )
                user_message = await self._build_user_message_item(
                    request.params.input, thread, context
                )
                async for event in self._process_new_thread_item_respond(
                    thread, user_message, context
                ):
                    yield event

            case ThreadsAddClientToolOutputReq():
                thread = await self.store.load_thread(
                    request.params.thread_id, context=context
                )
                items = await self.store.load_thread_items(
                    thread.id, None, 1, "desc", context
                )
                tool_call = next(
                    (
                        item
                        for item in items.data
                        if isinstance(item, ClientToolCallItem)
                        and item.status == "pending"
                    ),
                    None,
                )
                if not tool_call:
                    raise ValueError(
                        f"Last thread item in {thread.id} was not a ClientToolCallItem"
                    )
                tool_call.output = request.params.result
                tool_call.status = "completed"
                await self.store.save_item(thread.id, tool_call, context=context)
                await self._cleanup_pending_client_tool_call(thread, context)
                async for event in self._process_events(
                    thread, context, lambda: self.respond(thread, None, context)
                ):
                    yield event

            case ThreadsRetryAfterItemReq():
                thread_metadata = await self.store.load_thread(
                    request.params.thread_id, context=context
                )
                items_to_remove: list[Any] = []
                user_message_item = None
                async for item in self._paginate_thread_items_reverse(
                    request.params.thread_id, context
                ):
                    if item.id == request.params.item_id:
                        if not isinstance(item, UserMessageItem):
                            raise ValueError(
                                f"Item {request.params.item_id} is not a user message"
                            )
                        user_message_item = item
                        break
                    items_to_remove.append(item)
                if user_message_item:
                    for item in items_to_remove:
                        await self.store.delete_thread_item(
                            request.params.thread_id, item.id, context=context
                        )
                    async for event in self._process_events(
                        thread_metadata,
                        context,
                        lambda: self.respond(thread_metadata, user_message_item, context),
                    ):
                        yield event

            # ── Custom action (approval widgets) ─────────────────────
            case ThreadsCustomActionReq():
                thread_metadata = await self.store.load_thread(
                    request.params.thread_id, context=context
                )

                item = {}  # type: ignore[assignment]
                if request.params.item_id:
                    item = await self.store.load_item(
                        request.params.thread_id,
                        request.params.item_id,
                        context=context,
                    )

                if item and not isinstance(item, WidgetItem) and not isinstance(
                    item, ClientWidgetItem
                ):
                    yield ErrorEvent(
                        code=ErrorCode.STREAM_ERROR,
                        message=(
                            f"Item {request.params.item_id} is neither a "
                            "WidgetItem nor a ClientWidgetItem"
                        ),
                        allow_retry=False,
                    )
                    return

                # Create a fake WidgetItem wrapper for ClientWidgetItem to
                # satisfy the ``action()`` signature's type expectations.
                fake_widget_item: WidgetItem | None = None
                if isinstance(item, ClientWidgetItem):
                    fake_widget_item = WidgetItem(
                        id=item.id,
                        thread_id=item.thread_id,
                        created_at=item.created_at,
                        widget=Card(children=[]),
                    )
                elif isinstance(item, WidgetItem):
                    fake_widget_item = item

                async for event in self._process_events(
                    thread_metadata,
                    context,
                    lambda: self.action(
                        thread_metadata,
                        request.params.action,
                        fake_widget_item,
                        context,
                    ),
                ):
                    yield event

            case _:
                pass  # unknown request type — ignore
