"""ChatKit events handler for Lab 10 — maps WorkflowEvent → ChatKit SSE events.

The ``ChatKitEventsHandler`` translates Agent Framework ``WorkflowEvent``
objects (text streaming, function calls/results, handoffs, approval
requests) into ChatKit ``ThreadStreamEvent`` objects that the frontend
can render as chat messages, progress tasks, and interactive widgets.

Key mappings:
* ``output`` / text          → ``ThreadItemAddedEvent`` / ``ThreadItemUpdated``
* ``output`` / function_call → ``TaskItem`` with descriptive title
* ``output`` / function_result → ``TaskItem`` with completed title
* ``handoff_sent``           → ``TaskItem`` with agent name
* ``output`` / function_approval_request → ``ClientWidgetItem``
"""

import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, AsyncIterable

from agent_framework import AgentResponseUpdate, Content, WorkflowEvent
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    CustomTask,
    ProgressUpdateEvent,
    TaskItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadItemUpdate,
    ThreadItemUpdated,
    ThreadStreamEvent,
)

from app.common.chatkit.types import ClientWidgetItem, CustomThreadItemDoneEvent

logger = logging.getLogger(__name__)


# ── Descriptive titles for MCP tool calls ────────────────────────────
# Maps tool function names → user-friendly start/end descriptions
# shown as progress tasks in the chat UI.

event_description_map: dict[str, str | dict[str, str]] = {
    "started": "Processing your request …",
    "getAccountsByUserName": {
        "start": "Looking up your account for your user name…",
        "end": "Retrieved your accounts",
    },
    "getAccountDetails": {
        "start": "Fetching your account details…",
        "end": "Fetched your account details",
    },
    "getPaymentMethodDetails": {
        "start": "Fetching your payment method details…",
        "end": "Fetched your payment method details",
    },
    "getRegisteredBeneficiary": {
        "start": "Looking up registered beneficiaries…",
        "end": "Retrieved your beneficiaries",
    },
    "getLastTransactions": {
        "start": "Fetching recent transactions…",
        "end": "Retrieved recent transactions",
    },
    "getTransactionsByRecipientName": {
        "start": "Searching transactions for the recipient…",
        "end": "Found transactions for the recipient",
    },
    "scan_invoice": {
        "start": "Extracting data from the uploaded image…",
        "end": "Data extracted from the uploaded image",
    },
    "processPayment": {
        "start": "Processing your payment…",
        "end": "Payment processed",
    },
    "getCreditCards": {
        "start": "Retrieving your credit cards…",
        "end": "Retrieved your credit cards",
    },
    "getCardDetails": {
        "start": "Fetching your credit card details…",
        "end": "Fetched your credit card details",
    },
    "getCardTransactions": {
        "start": "Looking up transactions for your credit card…",
        "end": "Retrieved transactions for your credit card",
    },
}


class ChatKitEventsHandler:
    """Stateful handler that converts a stream of ``WorkflowEvent`` into
    ChatKit ``ThreadStreamEvent`` objects.

    A new instance should be created for **each** respond / action call
    to keep message-assembly state isolated.
    """

    def __init__(self) -> None:
        self.message_started: bool = False
        self.accumulated_text: str = ""
        self.content_index: int = 0
        # Maps call_id → tool name so we can show a descriptive title
        # when the function_result arrives (which only carries the call_id).
        self.tool_name_id_map: dict[str, str] = {}

    # ── Text streaming helper ────────────────────────────────────────

    def _handle_text_content(
        self, thread_id: str, message_id: str, text: str
    ) -> ThreadStreamEvent:
        """Emit the first text chunk as ``ThreadItemAddedEvent``, subsequent
        chunks as ``ThreadItemUpdated`` (delta)."""

        if not self.message_started:
            assistant_message = AssistantMessageItem(
                id=message_id,
                thread_id=thread_id,
                type="assistant_message",
                content=[AssistantMessageContent(text=text)],
                created_at=datetime.now(),
            )
            self.message_started = True
            self.accumulated_text = text
            return ThreadItemAddedEvent(
                type="thread.item.added", item=assistant_message
            )

        self.accumulated_text += text
        self.content_index += 1

        return ThreadItemUpdated(
            type="thread.item.updated",
            item_id=f"itm_{uuid.uuid4().hex[:8]}",
            update=AssistantMessageContentPartTextDelta(
                content_index=self.content_index,
                delta=text,
            ),
        )

    # ── Main event loop ──────────────────────────────────────────────

    async def handle_events(
        self,
        thread_id: str,
        events: AsyncIterable[WorkflowEvent],
    ) -> AsyncGenerator[ThreadStreamEvent, None]:
        """Async generator that yields ChatKit events for each workflow event."""

        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        async for event in events:
            # ── Skip internal lifecycle events ───────────────────────
            if event.type in (
                "status",
                "executor_invoked",
                "executor_completed",
                "superstep_started",
                "superstep_completed",
                "request_info",
            ):
                continue

            # ── Handoff indicator ────────────────────────────────────
            if event.type == "handoff_sent":
                title = f"Connected to {event.data.target} "
                task = CustomTask(title=title, icon="check-circle-filled")
                task_item = TaskItem(
                    thread_id=thread_id,
                    id=f"tsk_{uuid.uuid4().hex[:8]}",
                    task=task,
                    created_at=datetime.now(),
                )
                yield ThreadItemAddedEvent(item=task_item)

            # ── Agent output events ──────────────────────────────────
            elif event.type == "output":
                if not isinstance(event.data, AgentResponseUpdate):
                    continue
                # Skip triage agent chatter
                if event.executor_id == "triage_agent":
                    continue
                if not event.data.contents or not isinstance(
                    event.data.contents, list
                ):
                    continue

                contents = event.data.contents

                # ── Text streaming ───────────────────────────────────
                if all(item.type == "text" for item in contents):
                    text_update = contents[0].text  # type: ignore[attr-defined]
                    yield self._handle_text_content(
                        thread_id=thread_id,
                        message_id=message_id,
                        text=text_update,
                    )

                # ── Function call (start) ────────────────────────────
                elif all(item.type == "function_call" for item in contents):
                    fc = contents[0]  # type: ignore[index]
                    if fc.name:
                        call_id = fc.call_id
                        self.tool_name_id_map[call_id] = fc.name
                        desc = event_description_map.get(fc.name)
                        title = (
                            desc["start"]
                            if isinstance(desc, dict)
                            else (fc.name if desc is None else desc)
                        )
                        task = CustomTask(title=title, icon="search")
                        task_item = TaskItem(
                            thread_id=thread_id,
                            id=call_id,
                            task=task,
                            created_at=datetime.now(),
                        )
                        yield ThreadItemAddedEvent(item=task_item)

                # ── Function result (end) ────────────────────────────
                elif all(item.type == "function_result" for item in contents):
                    fr = contents[0]  # type: ignore[index]
                    if fr.call_id:
                        tool_name = self.tool_name_id_map.get(
                            fr.call_id, fr.call_id
                        )
                        desc = event_description_map.get(tool_name)
                        title = (
                            desc["end"]
                            if isinstance(desc, dict)
                            else (tool_name if desc is None else tool_name)
                        )
                        task = CustomTask(
                            title=title, icon="check-circle-filled"
                        )
                        task_item = TaskItem(
                            thread_id=thread_id,
                            id=fr.call_id,
                            task=task,
                            created_at=datetime.now(),
                        )
                        yield ThreadItemAddedEvent(item=task_item)

                # ── Function approval request ────────────────────────
                elif all(
                    item.type == "function_approval_request" for item in contents
                ):
                    approval_content: Content = contents[0].function_call  # type: ignore[attr-defined]
                    tool_name = approval_content.name
                    parsed_args = approval_content.arguments

                    # Emit a client-managed widget so the frontend can
                    # render Approve / Reject buttons with its own
                    # component.
                    client_widget_item = ClientWidgetItem(
                        id=f"wdg_{uuid.uuid4().hex[:8]}",
                        thread_id=thread_id,
                        created_at=datetime.now(),
                        name="tool_approval_request",
                        args={
                            "tool_name": tool_name,
                            "tool_args": parsed_args,
                            "call_id": approval_content.call_id,
                            "request_id": approval_content.id,
                        },
                    )
                    yield CustomThreadItemDoneEvent(  # type: ignore[misc]
                        type="thread.item.done", item=client_widget_item
                    )

            # ── Fallback progress indicator ──────────────────────────
            else:
                desc = event_description_map.get(event.type, event.type)
                yield ProgressUpdateEvent(text=desc, icon="atom")  # type: ignore[arg-type]

        # ── Finalise the assistant message ────────────────────────────
        if self.message_started:
            final_message = AssistantMessageItem(
                id=message_id,
                thread_id=thread_id,
                type="assistant_message",
                content=(
                    [AssistantMessageContent(text=self.accumulated_text)]
                    if self.accumulated_text
                    else []
                ),
                created_at=datetime.now(),
            )
            yield ThreadItemDoneEvent(
                type="thread.item.done", item=final_message
            )
