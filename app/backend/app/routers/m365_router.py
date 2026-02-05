"""M365 Agent SDK router for Teams/Copilot integration.

This router exposes the /api/messages endpoint for the Bot Framework protocol,
enabling the banking assistant to work with Microsoft Teams and Copilot.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Request, Response, Depends
from dependency_injector.wiring import Provide, inject

from app.config.container_azure_chat import Container
from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy initialization flags
_m365_initialized = False
_m365_adapter = None
_m365_storage = None
_m365_connection_manager = None


def _ensure_m365_initialized():
    """Lazily initialize M365 Agent SDK components."""
    global _m365_initialized, _m365_adapter, _m365_storage, _m365_connection_manager
    
    if _m365_initialized:
        return True
    
    try:
        from microsoft_agents.hosting.fastapi import CloudAdapter
        from microsoft_agents.hosting.core import MemoryStorage
        from microsoft_agents.authentication.msal import MsalConnectionManager
        from microsoft_agents.activity import load_configuration_from_env
        
        # Load M365 configuration from environment
        agents_sdk_config = load_configuration_from_env(os.environ)
        
        # Create storage and connection manager
        _m365_storage = MemoryStorage()
        _m365_connection_manager = MsalConnectionManager(**agents_sdk_config)
        
        # Create adapter
        _m365_adapter = CloudAdapter(connection_manager=_m365_connection_manager)
        
        _m365_initialized = True
        logger.info("M365 Agent SDK initialized successfully")
        return True
        
    except ImportError as e:
        logger.warning(f"M365 Agent SDK not available: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize M365 Agent SDK: {e}", exc_info=True)
        return False


@router.post("/api/messages")
@inject
async def messages_endpoint(
    request: Request,
    handoff_orchestrator=Depends(Provide[Container.handoff_orchestrator])
):
    """Main endpoint for Teams/Copilot messages.
    
    This endpoint follows the Bot Framework protocol and handles:
    - User messages (type: message)
    - Adaptive Card actions (type: invoke with action data)
    - Conversation updates (members added/removed)
    
    The orchestrator is injected via dependency injection, allowing
    the same agent logic to be used for both ChatKit and M365 channels.
    """
    if not _ensure_m365_initialized():
        return Response(
            content='{"error": "M365 Agent SDK not configured"}',
            status_code=503,
            media_type="application/json"
        )
    
    try:
        from microsoft_agents.hosting.fastapi import start_agent_process
        from app.agents.m365.banking_activity_handler import BankingActivityHandler
        
        # Create a factory function that returns the injected orchestrator
        def orchestrator_factory():
            return handoff_orchestrator
        
        # Create the activity handler with the orchestrator factory
        handler = BankingActivityHandler(
            orchestrator_factory=orchestrator_factory
        )
        
        # Process the request using the M365 adapter
        return await start_agent_process(
            request,
            handler,
            _m365_adapter
        )
        
    except Exception as e:
        logger.error(f"Error processing M365 message: {e}", exc_info=True)
        return Response(
            content=f'{{"error": "{str(e)}"}}',
            status_code=500,
            media_type="application/json"
        )


@router.get("/api/messages")
async def health_check():
    """Health check endpoint for Bot Framework.
    
    The Bot Framework connector uses this to verify the endpoint is reachable.
    """
    initialized = _ensure_m365_initialized()
    return {
        "status": "OK" if initialized else "M365 SDK not configured",
        "channel": "M365 Agent SDK",
        "capabilities": ["teams", "copilot"] if initialized else []
    }


@router.post("/api/messages/invoke")
@inject
async def invoke_endpoint(
    request: Request,
    handoff_orchestrator=Depends(Provide[Container.handoff_orchestrator])
):
    """Handle invoke activities (Adaptive Card actions, etc.).
    
    This is an alternative endpoint for invoke-type activities,
    though most invokes come through /api/messages.
    """
    # Most invoke activities are handled through the main messages endpoint
    # This is here for compatibility with some Bot Framework scenarios
    return await messages_endpoint(request, handoff_orchestrator)
