"""Chat API router for Lab 8 — ChatKit endpoint with simple triage.

Compared to Lab 7 this router injects **both** AccountAgent and PaymentAgent
and passes the request ``origin`` header so the AttachmentMetadataStore can
build correct upload / preview URLs.
"""

import logging

from dependency_injector.wiring import Depends, Provide
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.agents.account_agent import AccountAgent
from app.agents.payment_agent import PaymentAgent
from app.config.container import Container
from app.routers.chatkit_server import BankingAssistantChatKitServer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.api_route("/chatkit", methods=["GET", "POST"])
async def chat(
    request: Request,
    account_agent: AccountAgent = Depends(Provide[Container.account_agent]),
    payment_agent: PaymentAgent = Depends(Provide[Container.payment_agent]),
):
    origin = request.headers.get("origin")
    chatkit_server = BankingAssistantChatKitServer(
        account_agent=account_agent,
        payment_agent=payment_agent,
        origin=origin,
    )
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
        logger.error("Error: %s", e, exc_info=True)
        error_event = f'event: error\ndata: {{"error": "{str(e)}"}}\n\n'
        return StreamingResponse(
            content=iter([error_event]), media_type="text/event-stream", status_code=500
        )
