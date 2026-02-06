"""Banking Activity Handler for M365 Agent SDK.

This handler bridges Teams/Copilot messages to the existing HandoffOrchestrator,
converting between the Bot Framework activity protocol and Agent Framework events.
"""

import logging
from typing import Dict, Any, Optional, Callable

from microsoft_agents.hosting.core import (
    ActivityHandler,
    TurnContext,
    MessageFactory,
)
from microsoft_agents.activity import (
    ChannelAccount,
    Attachment,
    Activity,
    ActivityTypes,
)

from app.agents.azure_chat.handoff.handoff_orchestrator import HandoffOrchestrator
from .m365_events_handler import M365EventsHandler, M365Response
from .adaptive_cards import build_welcome_card, build_error_card

logger = logging.getLogger(__name__)


class BankingActivityHandler(ActivityHandler):
    """Activity handler that receives messages from Teams/Copilot
    and forwards them to the existing banking orchestrator.
    
    This class acts as the bridge between the M365 Agent SDK protocol
    and the Agent Framework-based orchestration layer.
    """
    
    # Class-level storage for conversation state (in production, use persistent storage)
    _conversation_orchestrators: Dict[str, HandoffOrchestrator] = {}
    # Map Teams conversation IDs to orchestrator thread IDs
    _conversation_thread_map: Dict[str, str] = {}
    
    def __init__(
        self,
        orchestrator_factory,  # Callable that creates HandoffOrchestrator
    ):
        """Initialize the activity handler.
        
        Args:
            orchestrator_factory: Factory function to create HandoffOrchestrator instances
        """
        super().__init__()
        self._orchestrator_factory = orchestrator_factory
    
    def _get_or_create_orchestrator(self, conversation_id: str) -> HandoffOrchestrator:
        """Get existing orchestrator for conversation or create a new one."""
        if conversation_id not in self._conversation_orchestrators:
            self._conversation_orchestrators[conversation_id] = self._orchestrator_factory()
        return self._conversation_orchestrators[conversation_id]
    
    def _get_thread_id(self, conversation_id: str) -> Optional[str]:
        """Get the orchestrator thread ID for a Teams conversation (None if new)."""
        return self._conversation_thread_map.get(conversation_id)
    
    def _set_thread_id(self, conversation_id: str, thread_id: str):
        """Store the orchestrator thread ID for a Teams conversation."""
        self._conversation_thread_map[conversation_id] = thread_id
    
    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext
    ):
        """Welcome new users when they join the conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                # Send welcome card
                welcome_card = build_welcome_card()
                attachment = Attachment(
                    content_type="application/vnd.microsoft.card.adaptive",
                    content=welcome_card
                )
                await turn_context.send_activity(
                    MessageFactory.attachment(attachment)
                )
    
    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages from Teams/Copilot.
        
        This method:
        1. Extracts the user message
        2. Gets/creates the orchestrator for this conversation
        3. Processes through the Agent Framework workflow
        4. Converts responses to Teams-compatible format
        5. Sends responses back (including Adaptive Cards for approvals)
        """
        user_message = turn_context.activity.text
        conversation_id = turn_context.activity.conversation.id
        
        if not user_message:
            # Check if this is an Adaptive Card action (approval response)
            if turn_context.activity.value:
                await self._handle_card_action(turn_context)
                return
            
            await turn_context.send_activity(
                MessageFactory.text("I didn't receive a message. Please try again.")
            )
            return
        
        logger.info(f"Processing message for conversation: {conversation_id}")
        
        try:
            # Get or create orchestrator for this conversation
            orchestrator = self._get_or_create_orchestrator(conversation_id)
            
            # Send typing indicator while processing
            await turn_context.send_activity(Activity(type=ActivityTypes.typing))
            
            # Process through the orchestrator
            await self._process_with_orchestrator(
                orchestrator,
                user_message,
                conversation_id,
                turn_context
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_card = build_error_card(
                f"An error occurred while processing your request: {str(e)}"
            )
            attachment = Attachment(
                content_type="application/vnd.microsoft.card.adaptive",
                content=error_card
            )
            await turn_context.send_activity(
                MessageFactory.attachment(attachment)
            )
    
    async def _process_with_orchestrator(
        self,
        orchestrator: HandoffOrchestrator,
        message: str,
        conversation_id: str,
        turn_context: TurnContext
    ):
        """Process a message through the orchestrator and send responses.
        
        The orchestrator's processMessageStream yields tuples of:
        (content_chunk: str, is_final: bool, thread_id: str | None)
        """
        
        # Get the thread ID for this conversation (None for new conversations)
        thread_id = self._get_thread_id(conversation_id)
        
        logger.debug(f"Processing with thread_id: {thread_id} (conversation: {conversation_id})")
        
        # Accumulate content chunks
        accumulated_content = ""
        returned_thread_id = None
        
        try:
            async for content, is_final, tid in orchestrator.processMessageStream(message, thread_id):
                # Accumulate text content
                if content:
                    accumulated_content += content
                
                # Capture thread_id when returned
                if tid:
                    returned_thread_id = tid
                
                # On final chunk, send the accumulated response
                if is_final:
                    break
            
            # Store the thread ID mapping for future messages
            if returned_thread_id:
                self._set_thread_id(conversation_id, returned_thread_id)
                logger.debug(f"Stored thread mapping: {conversation_id} -> {returned_thread_id}")
            
            # Send the accumulated response to Teams
            if accumulated_content:
                await turn_context.send_activity(
                    MessageFactory.text(accumulated_content)
                )
            else:
                await turn_context.send_activity(
                    MessageFactory.text("I processed your request but have no response to show.")
                )
                
        except Exception as e:
            logger.error(f"Error in orchestrator processing: {e}", exc_info=True)
            raise
    
    async def _handle_card_action(self, turn_context: TurnContext):
        """Handle Adaptive Card action submissions (like approval/rejection).
        
        This method processes the action data from Adaptive Card button clicks
        and resumes the orchestrator workflow with the user's decision.
        """
        action_data = turn_context.activity.value
        conversation_id = turn_context.activity.conversation.id
        
        if not isinstance(action_data, dict):
            logger.warning(f"Unexpected action data type: {type(action_data)}")
            return
        
        action_type = action_data.get("action")
        
        if action_type == "approval":
            approved = action_data.get("approved", False)
            call_id = action_data.get("call_id")
            request_id = action_data.get("request_id")
            tool_name = action_data.get("tool_name")
            
            logger.info(
                f"Processing approval action: approved={approved}, "
                f"tool={tool_name}, call_id={call_id}"
            )
            
            # Send acknowledgment
            status = "approved" if approved else "rejected"
            await turn_context.send_activity(
                MessageFactory.text(f"✓ Action {status}. Processing...")
            )
            
            # Send typing indicator
            await turn_context.send_activity(Activity(type=ActivityTypes.typing))
            
            try:
                # Get the orchestrator and resume with approval response
                orchestrator = self._get_or_create_orchestrator(conversation_id)
                
                # Process the approval response through the orchestrator
                events = orchestrator.processToolApprovalResponse(
                    thread_id=conversation_id,
                    approved=approved,
                    call_id=call_id,
                    request_id=request_id,
                    tool_name=tool_name
                )
                
                # Convert and send responses
                handler = M365EventsHandler()
                async for response in handler.handle_events(events):
                    if response.text:
                        await turn_context.send_activity(
                            MessageFactory.text(response.text)
                        )
                    if response.adaptive_card:
                        attachment = Attachment(
                            content_type="application/vnd.microsoft.card.adaptive",
                            content=response.adaptive_card
                        )
                        await turn_context.send_activity(
                            MessageFactory.attachment(attachment)
                        )
                        
            except Exception as e:
                logger.error(f"Error processing approval: {e}", exc_info=True)
                error_card = build_error_card(
                    f"Failed to process your response: {str(e)}"
                )
                attachment = Attachment(
                    content_type="application/vnd.microsoft.card.adaptive",
                    content=error_card
                )
                await turn_context.send_activity(
                    MessageFactory.attachment(attachment)
                )
        else:
            logger.warning(f"Unknown action type: {action_type}")
    
    async def on_turn(self, turn_context: TurnContext):
        """Override to add logging and error handling."""
        logger.debug(f"Received activity type: {turn_context.activity.type}")
        await super().on_turn(turn_context)
