"""Chat API router for Lab 7 — ChatKit endpoint."""

import logging

from dependency_injector.wiring import Depends, Provide
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.agents.account_agent import AccountAgent
from app.config.container import Container
from app.routers.chatkit_server import BankingAssistantChatKitServer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route("/chatkit", methods=["GET", "POST"])
async def chat(
    request: Request,
    account_agent: AccountAgent = Depends(Provide[Container.account_agent]),
):
    """Process ChatKit protocol requests via a single Foundry v2 agent."""
    chatkit_server = BankingAssistantChatKitServer(account_agent=account_agent)
    try:
        body = await request.body()
        response = await chatkit_server.process_request(body)
        return StreamingResponse(
            content=response.body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    except Exception as e:
        logger.error("Error processing chat request: %s", e, exc_info=True)
        error_event = f'event: error\ndata: {{"error": "{str(e)}"}}\n\n'
        return StreamingResponse(
            content=iter([error_event]),
            media_type="text/event-stream",
            status_code=500,
        )
