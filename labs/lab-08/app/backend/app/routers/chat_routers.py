"""Chat API router for Lab 8 — ChatKit endpoint with attachment support.

Extends Lab 7's singleton pattern with PaymentAgent triage.  The request
``origin`` header is captured on the first call so that the
``AttachmentMetadataStore`` can build correct upload / preview URLs.
"""

import logging

from chatkit.server import NonStreamingResult, StreamingResult
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from app.config.container import Container
from app.routers.chatkit_server import BankingAssistantChatKitServer
from app.routers.memory_store import MemoryStore

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton ChatKit server — one instance shared across ALL requests so the
# in-memory MemoryStore (thread state) survives between messages.
_chatkit_server: BankingAssistantChatKitServer | None = None


def _get_chatkit_server(origin: str | None = None) -> BankingAssistantChatKitServer:
    """Lazily create and return the singleton ChatKit server."""
    global _chatkit_server
    if _chatkit_server is None:
        account_agent = Container.account_agent()
        payment_agent = Container.payment_agent()
        store = MemoryStore()
        _chatkit_server = BankingAssistantChatKitServer(
            account_agent=account_agent,
            payment_agent=payment_agent,
            store=store,
            origin=origin,
        )
        logger.info("ChatKit server singleton created (store id=%s)", id(store))
    return _chatkit_server


@router.api_route("/chatkit", methods=["GET", "POST"])
async def chat(request: Request):
    """Process ChatKit protocol requests with simple agent triage."""
    origin = request.headers.get("origin")
    chatkit_server = _get_chatkit_server(origin=origin)
    try:
        body = await request.body()
        response = await chatkit_server.process(body, context={})

        if isinstance(response, StreamingResult):
            return StreamingResponse(
                content=response,
                media_type="text/event-stream",
            )
        elif isinstance(response, NonStreamingResult):
            return JSONResponse(
                content=None,
                media_type="application/json",
                headers={"content-type": "application/json"},
            ) if response.json is None else StreamingResponse(
                content=iter([response.json if isinstance(response.json, bytes) else response.json.encode()]),
                media_type="application/json",
            )
    except Exception as e:
        logger.error("Error processing chat request: %s", e, exc_info=True)
        error_event = f'event: error\ndata: {{"error": "{str(e)}"}}\n\n'
        return StreamingResponse(
            content=iter([error_event]),
            media_type="text/event-stream",
            status_code=500,
        )
