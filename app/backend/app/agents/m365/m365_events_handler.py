"""M365 Events Handler - Maps Agent Framework events to Teams/Copilot responses.

This module provides the translation layer between Agent Framework workflow events
and M365 Agent SDK activity responses, similar to how ChatKitEventsHandler works
for the ChatKit protocol.
"""

import logging
from typing import AsyncGenerator, AsyncIterable, List, Any, Dict
from dataclasses import dataclass

from agent_framework import (
    AgentRunResponseUpdate,
    AgentRunUpdateEvent,
    ExecutorCompletedEvent,
    ExecutorInvokedEvent,
    FunctionApprovalRequestContent,
    FunctionCallContent,
    FunctionResultContent,
    RequestInfoEvent,
    SuperStepCompletedEvent,
    SuperStepStartedEvent,
    TextContent,
    WorkflowEvent,
    WorkflowStatusEvent,
)

from .adaptive_cards import build_approval_card, build_progress_card

logger = logging.getLogger(__name__)


# Tool name to human-friendly description mapping
TOOL_DESCRIPTIONS = {
    "getAccountsByUserName": {
        "start": "Looking up your accounts...",
        "end": "Found your accounts"
    },
    "getAccountDetails": {
        "start": "Fetching account details...",
        "end": "Retrieved account details"
    },
    "getPaymentMethodDetails": {
        "start": "Fetching payment method details...",
        "end": "Retrieved payment methods"
    },
    "getTransactionsByRecipientName": {
        "start": "Searching transactions...",
        "end": "Found transactions"
    },
    "scan_invoice": {
        "start": "Processing uploaded invoice...",
        "end": "Invoice processed"
    },
    "processPayment": {
        "start": "Processing payment...",
        "end": "Payment processed"
    },
    "getCreditCards": {
        "start": "Retrieving credit cards...",
        "end": "Retrieved credit cards"
    },
    "getCardDetails": {
        "start": "Fetching card details...",
        "end": "Retrieved card details"
    },
    "getCardTransactions": {
        "start": "Looking up card transactions...",
        "end": "Retrieved transactions"
    }
}


@dataclass
class M365Response:
    """Represents a response to send back to Teams/Copilot."""
    
    text: str | None = None
    adaptive_card: Dict[str, Any] | None = None
    is_typing: bool = False
    is_final: bool = False


class M365EventsHandler:
    """Handles Agent Framework events and converts them to M365 responses.
    
    This class accumulates streaming text responses and converts special events
    (like function calls and approval requests) into appropriate M365 formats.
    """
    
    def __init__(self) -> None:
        self.accumulated_text = ""
        self.tool_name_id_map: Dict[str, str] = {}
        self.pending_approval: Dict[str, Any] | None = None
    
    async def handle_events(
        self,
        events: AsyncIterable[WorkflowEvent]
    ) -> AsyncGenerator[M365Response, None]:
        """Process Agent Framework events and yield M365 responses.
        
        Args:
            events: Async iterable of workflow events from the orchestrator
            
        Yields:
            M365Response objects ready to be sent to Teams/Copilot
        """
        async for event in events:
            # Skip internal/status events
            if isinstance(event, (
                WorkflowStatusEvent,
                ExecutorInvokedEvent,
                ExecutorCompletedEvent,
                SuperStepStartedEvent,
                SuperStepCompletedEvent,
                RequestInfoEvent
            )):
                continue
            
            if isinstance(event, AgentRunUpdateEvent):
                async for response in self._handle_agent_run_event(event):
                    yield response
        
        # Yield final accumulated text if any
        if self.accumulated_text:
            yield M365Response(
                text=self.accumulated_text,
                is_final=True
            )
    
    async def _handle_agent_run_event(
        self,
        event: AgentRunUpdateEvent
    ) -> AsyncGenerator[M365Response, None]:
        """Handle AgentRunUpdateEvent and yield appropriate responses."""
        
        # Skip triage agent events (internal routing)
        if event.executor_id == "triage_agent":
            return
        
        if not isinstance(event.data, AgentRunResponseUpdate):
            return
        
        if not event.data.contents:
            return
        
        contents = event.data.contents
        
        # Handle text content (streaming response)
        if all(isinstance(item, TextContent) for item in contents):
            text_content: TextContent = contents[0]  # type: ignore
            if text_content.text:
                self.accumulated_text += text_content.text
                # For Teams, we don't stream partial responses
                # We'll send the final accumulated text at the end
                return
        
        # Handle function call start (show progress)
        if all(isinstance(item, FunctionCallContent) for item in contents):
            function_call: FunctionCallContent = contents[0]  # type: ignore
            if function_call.name and function_call.call_id:
                self.tool_name_id_map[function_call.call_id] = function_call.name
                
                # Get human-friendly description
                tool_info = TOOL_DESCRIPTIONS.get(function_call.name, {})
                description = tool_info.get("start", f"Executing {function_call.name}...") if tool_info else f"Executing {function_call.name}..."
                
                # For long-running tools, we could send a typing indicator
                # but Teams handles this differently than ChatKit
                logger.info(f"Tool started: {function_call.name} - {description}")
                yield M365Response(is_typing=True)
        
        # Handle function result (tool completed)
        if all(isinstance(item, FunctionResultContent) for item in contents):
            function_result: FunctionResultContent = contents[0]  # type: ignore
            if function_result.call_id:
                tool_name = self.tool_name_id_map.get(
                    function_result.call_id,
                    function_result.call_id
                )
                if tool_name:
                    tool_info = TOOL_DESCRIPTIONS.get(tool_name, {})
                    description = tool_info.get("end", f"Completed {tool_name}") if tool_info else f"Completed {tool_name}"
                    logger.info(f"Tool completed: {tool_name} - {description}")
        
        # Handle approval request - THIS IS THE KEY PART
        if all(isinstance(item, FunctionApprovalRequestContent) for item in contents):
            approval_request: FunctionApprovalRequestContent = contents[0]  # type: ignore
            
            tool_name = approval_request.function_call.name
            parsed_args = approval_request.function_call.parse_arguments()
            call_id = approval_request.function_call.call_id
            request_id = approval_request.id
            
            logger.info(f"Approval required for tool: {tool_name}")
            
            # Build Adaptive Card for approval
            approval_card = build_approval_card(
                tool_name=tool_name,
                tool_args=parsed_args,
                call_id=call_id,
                request_id=request_id
            )
            
            # Store pending approval info for later reference
            self.pending_approval = {
                "tool_name": tool_name,
                "call_id": call_id,
                "request_id": request_id
            }
            
            # If we have accumulated text, send it first
            if self.accumulated_text:
                yield M365Response(
                    text=self.accumulated_text,
                    is_final=False
                )
                self.accumulated_text = ""
            
            # Then send the approval card
            yield M365Response(
                adaptive_card=approval_card,
                is_final=False
            )
    
    def reset(self) -> None:
        """Reset the handler state for a new conversation turn."""
        self.accumulated_text = ""
        self.tool_name_id_map.clear()
        self.pending_approval = None
