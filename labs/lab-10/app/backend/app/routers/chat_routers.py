"""Chat API router for Lab 10 — ChatKit endpoint with handoff orchestration.

Compared to Lab 8's simple keyword triage, this router creates a
``BankingAssistantChatKitServer`` backed by the ``HandoffOrchestrator``
workflow.  The singleton pattern is preserved so that the in-memory
store survives between requests.
"""

import json
import logging

from chatkit.server import NonStreamingResult, StreamingResult
from chatkit.types import ErrorEvent
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from app.config.container import Container
from app.routers.chatkit_server import BankingAssistantChatKitServer
from app.routers.memory_store import MemoryStore

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton ChatKit server — one instance shared across ALL requests so
# the in-memory store (thread state) survives between messages.
_chatkit_server: BankingAssistantChatKitServer | None = None


async def wrap_stream_with_error_handling(streaming_result):
    """Wrap the SSE stream to catch errors and emit them as error events.

    Ensures that any errors during streaming are sent to the client as
    error events within the SSE stream, rather than causing the HTTP
    connection to fail.
    """
    try:
        async for chunk in streaming_result:
            yield chunk
    except Exception as e:
        logger.error("Error during SSE streaming: %s", e, exc_info=True)
        error_event = ErrorEvent(
            message=f"An error occurred during streaming: {e!s}",
            allow_retry=True,
        )
        error_data = error_event.model_dump(mode="json")
        error_line = f"data: {json.dumps(error_data)}\n\n"
        yield error_line.encode("utf-8")


def _get_chatkit_server(origin: str | None = None) -> BankingAssistantChatKitServer:
    """Lazily create and return the singleton ChatKit server."""
    global _chatkit_server
    if _chatkit_server is None:
        handoff_orchestrator = Container.handoff_orchestrator()
        store = MemoryStore()
        _chatkit_server = BankingAssistantChatKitServer(
            handoff_orchestrator=handoff_orchestrator,
            store=store,
            origin=origin,
        )
        logger.info("ChatKit server singleton created (store id=%s)", id(store))
    return _chatkit_server


@router.api_route("/chatkit", methods=["GET", "POST"])
async def chat(request: Request):
    """Process ChatKit protocol requests with multi-agent handoff."""
    origin = request.headers.get("origin")
    chatkit_server = _get_chatkit_server(origin=origin)
    try:
        body = await request.body()
        response = await chatkit_server.process(body, context={})

        if isinstance(response, StreamingResult):
            wrapped = wrap_stream_with_error_handling(response)
            return StreamingResponse(
                content=wrapped,
                media_type="text/event-stream",
            )
        elif isinstance(response, NonStreamingResult):
            if response.json is None:
                return JSONResponse(
                    content=None,
                    media_type="application/json",
                    headers={"content-type": "application/json"},
                )
            data = (
                response.json
                if isinstance(response.json, bytes)
                else response.json.encode()
            )
            return StreamingResponse(
                content=iter([data]),
                media_type="application/json",
            )
    except Exception as e:
        logger.error("Error processing chat request: %s", e, exc_info=True)
        error_event = f'event: error\ndata: {{"error": "{e!s}"}}\n\n'
        return StreamingResponse(
            content=iter([error_event]),
            media_type="text/event-stream",
            status_code=500,
        )
