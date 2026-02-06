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
    """Lazily initialize M365 Agent SDK components.
    
    Uses User Assigned Managed Identity for authentication (no client secret required).
    Environment variables expected:
    - M365_APP_ID: Bot App ID (Managed Identity Client ID)
    - M365_APP_TENANT_ID: Azure AD Tenant ID
    """
    global _m365_initialized, _m365_adapter, _m365_storage, _m365_connection_manager
    
    if _m365_initialized:
        return True
    
    try:
        from microsoft_agents.hosting.fastapi import CloudAdapter
        from microsoft_agents.hosting.core import MemoryStorage, AuthTypes, AgentAuthConfiguration
        from microsoft_agents.authentication.msal import MsalConnectionManager
        
        # Get M365 configuration from environment
        bot_app_id = os.environ.get("M365_APP_ID")
        tenant_id = os.environ.get("M365_APP_TENANT_ID")
        
        if not bot_app_id:
            logger.warning("M365_APP_ID not configured, M365 integration disabled")
            return False
        
        # Create storage
        _m365_storage = MemoryStorage()
        
        # Create AgentAuthConfiguration for User Assigned Managed Identity
        service_connection_config = AgentAuthConfiguration(
            client_id=bot_app_id,
            tenant_id=tenant_id or "",
            auth_type=AuthTypes.user_managed_identity,
            connection_name="SERVICE_CONNECTION",
        )
        
        # Create connection manager with the configuration object
        _m365_connection_manager = MsalConnectionManager(
            connections_configurations={
                "SERVICE_CONNECTION": service_connection_config
            }
        )
        
        # Create adapter
        _m365_adapter = CloudAdapter(connection_manager=_m365_connection_manager)
        
        _m365_initialized = True
        logger.info(f"M365 Agent SDK initialized successfully with App ID: {bot_app_id[:8]}...")
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
        from app.agents.m365.banking_activity_handler import BankingActivityHandler
        
        # Create a factory function that returns the injected orchestrator
        def orchestrator_factory():
            return handoff_orchestrator
        
        # Create the activity handler with the orchestrator factory
        handler = BankingActivityHandler(
            orchestrator_factory=orchestrator_factory
        )
        
        # Process the request using the M365 adapter
        # The CloudAdapter.process() method works with any Agent (including ActivityHandler)
        response = await _m365_adapter.process(request, handler)
        return response or Response(status_code=202)
        
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
