"""Attachment upload / preview endpoints for Lab 8.

Implements the two-phase ChatKit attachment protocol:
1. ChatKit frontend calls ``POST /upload/{attachment_id}`` to push the file
   bytes into Azure Blob Storage.
2. The UI requests ``GET /preview/{attachment_id}`` to display a thumbnail.
"""

import logging
from io import BytesIO

from dependency_injector.wiring import Depends, Provide
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse

from app.config.container import Container
from app.helpers.blob_proxy import BlobStorageProxy

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_USER_ID = "demo_user"

# Lazy reference to the shared MemoryStore kept by the ChatKit server.
_memory_store = None


def _get_memory_store():
    global _memory_store
    if _memory_store is None:
        from app.routers.chatkit_server import BankingAssistantChatKitServer

        _memory_store = BankingAssistantChatKitServer.metadata_store
    return _memory_store


@router.post("/upload/{attachment_id}")
async def upload_file(
    attachment_id: str,
    file: UploadFile = File(...),
    blob_proxy: BlobStorageProxy = Depends(Provide[Container.blob_proxy]),
):
    """Handle file upload for two-phase ChatKit upload."""
    logger.info("Receiving file upload for attachment: %s", attachment_id)
    try:
        contents = await file.read()
        blob_proxy.store_file(contents, attachment_id)
        logger.info(
            "Saved %d bytes for %s as attachment %s",
            len(contents),
            file.filename,
            attachment_id,
        )
        store = _get_memory_store()
        attachment = await store.load_attachment(
            attachment_id, {"user_id": DEFAULT_USER_ID}
        )
        attachment.upload_url = None
        await store.save_attachment(attachment, {"user_id": DEFAULT_USER_ID})
        return JSONResponse(content=attachment.model_dump(mode="json"))
    except Exception as e:
        logger.error("Error uploading: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to upload: {str(e)}"},
        )


@router.get("/preview/{attachment_id}")
async def preview_image(
    attachment_id: str,
    blob_proxy: BlobStorageProxy = Depends(Provide[Container.blob_proxy]),
):
    """Serve image preview / thumbnail."""
    try:
        try:
            file_bytes = blob_proxy.get_file_as_bytes(attachment_id)
        except Exception:
            return JSONResponse(status_code=404, content={"error": "File not found"})

        store = _get_memory_store()
        try:
            attachment = await store.load_attachment(
                attachment_id, {"user_id": DEFAULT_USER_ID}
            )
            media_type = attachment.mime_type
        except Exception:
            media_type = "application/octet-stream"

        return StreamingResponse(BytesIO(file_bytes), media_type=media_type)
    except Exception as e:
        logger.error("Error serving preview: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
