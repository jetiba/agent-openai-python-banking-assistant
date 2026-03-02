"""Custom ChatKit types for Lab 10 — client-managed widgets.

Extends ChatKit's built-in ``ThreadItemBase`` to support **client-managed
widgets** — lightweight thread items whose rendering is handled entirely by
the frontend.  The server only sends the widget *name* and *args*; the
React client resolves the matching component and renders it.

This is used for the **tool-approval** flow: when the agent requests
approval for a function call (e.g. ``processPayment``), the server emits a
``ClientWidgetItem`` with the tool name, arguments, call-id, and
request-id.  The frontend renders an Approve / Reject card and sends
the user's decision back via a ChatKit custom action.
"""

from typing import Annotated, Any, Literal

from chatkit.types import (
    AssistantMessageItem,
    ClientToolCallItem,
    EndOfTurnItem,
    HiddenContextItem,
    TaskItem,
    ThreadItemBase,
    UserMessageItem,
    WidgetItem,
    WorkflowItem,
)
from pydantic import BaseModel, Field


class ClientWidgetItem(ThreadItemBase):
    """A thread item whose rendering is delegated to the client.

    Unlike ``WidgetItem`` (server-managed), the server only provides the
    widget ``name`` and ``args``.  The frontend maps *name* → React
    component and passes *args* as props.
    """

    type: Literal["client_widget"] = "client_widget"
    name: Annotated[
        str,
        Field(
            description="The name of the pre-built widget to render on the client side."
        ),
    ]
    args: dict[str, Any] | None


# Extended ThreadItem union that includes ClientWidgetItem.
ThreadItem = Annotated[
    UserMessageItem
    | AssistantMessageItem
    | ClientToolCallItem
    | WidgetItem
    | WorkflowItem
    | TaskItem
    | HiddenContextItem
    | EndOfTurnItem
    | ClientWidgetItem,
    Field(discriminator="type"),
]
"""Union of all thread item variants provided by ChatKit + the custom ClientWidgetItem."""


class CustomThreadItemDoneEvent(BaseModel):
    """Event emitted when a thread item (including client widgets) is done."""

    type: Literal["thread.item.done"] = "thread.item.done"
    item: ThreadItem
