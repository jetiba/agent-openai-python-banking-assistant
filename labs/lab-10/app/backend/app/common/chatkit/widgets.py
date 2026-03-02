"""Server-managed approval widget for Lab 10.

Builds a ChatKit ``Card`` widget with Approve / Reject buttons for tool
execution approval.  This is used when the agent requests human approval
before calling a sensitive function (e.g. ``processPayment``).

Note: The current implementation uses **client-managed** widgets
(``ClientWidgetItem``) instead of this server-managed card.  This module
is kept as a reference for the server-managed widget pattern.
"""

from typing import Any

from chatkit.actions import ActionConfig
from chatkit.widgets import (
    Box,
    Button,
    Card,
    Col,
    Divider,
    Icon,
    Markdown,
    Row,
    Text,
    Title,
    WidgetRoot,
)


def build_approval_request(
    tool_name: str,
    tool_args: dict[str, Any | None] | None,
    call_id: str,
    request_id: str,
) -> WidgetRoot:
    """Build a server-managed approval request Card widget.

    The card shows:
    * An info icon with title "Approval Required"
    * The tool name and formatted arguments
    * Approve / Reject buttons that emit a ChatKit action of type ``approval``

    Parameters
    ----------
    tool_name:
        The name of the function requiring approval (e.g. ``processPayment``).
    tool_args:
        The function arguments to display to the user.
    call_id:
        The function call ID from the agent framework.
    request_id:
        The request-info event ID for resuming the workflow.
    """
    title = "Approval Required"
    description = "This action requires your approval before proceeding."
    args_str = str(tool_args)
    code_block = f"```py\n{args_str}\n```"

    return Card(
        key="approval_request",
        padding=0,
        size="md",
        children=[
            Col(
                align="center",
                gap=4,
                padding=4,
                children=[
                    Box(
                        background="yellow-400",
                        radius="full",
                        padding=3,
                        children=[
                            Icon(name="info", size="3xl", color="white"),
                        ],
                    ),
                    Col(
                        align="center",
                        gap=1,
                        children=[
                            Title(value=title),
                            Text(value=description, color="secondary"),
                            Markdown(value=f"**{tool_name}**"),
                        ],
                    ),
                ],
            ),
            Markdown(value=code_block),
            Divider(spacing=2),
            Row(
                children=[
                    Button(
                        label="Approve",
                        block=True,
                        onClickAction=ActionConfig(
                            type="approval",
                            payload={
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                                "approved": True,
                                "call_id": call_id,
                                "request_id": request_id,
                            },
                        ),
                    ),
                    Button(
                        label="No",
                        block=True,
                        variant="outline",
                        onClickAction=ActionConfig(
                            type="approval",
                            payload={
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                                "approved": False,
                                "call_id": call_id,
                                "request_id": request_id,
                            },
                        ),
                    ),
                ],
            ),
        ],
    )
