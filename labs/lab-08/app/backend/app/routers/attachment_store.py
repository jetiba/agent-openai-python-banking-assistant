"""Attachment metadata store for Lab 8 — two-phase ChatKit upload.

Creates attachment records with ``upload_url`` and ``preview_url`` that the
ChatKit frontend uses to POST file bytes and display image thumbnails.
Metadata is persisted in the provided MemoryStore instance.
"""

from typing import Any

from chatkit.store import AttachmentStore
from chatkit.types import (
    Attachment,
    AttachmentCreateParams,
    FileAttachment,
    ImageAttachment,
)
from pydantic import AnyUrl

from app.routers.memory_store import MemoryStore


class AttachmentMetadataStore(AttachmentStore[dict[str, Any]]):
    """AttachmentStore backed by an in-memory MemoryStore."""

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        metadata_store: MemoryStore | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.metadata_store = metadata_store

    async def create_attachment(
        self, input: AttachmentCreateParams, context: dict[str, Any]
    ) -> Attachment:
        """Create an attachment with upload URL for two-phase upload."""
        attachment_id = self.generate_attachment_id(input.mime_type, context)
        upload_url = f"{self.base_url}/upload/{attachment_id}"

        if input.mime_type.startswith("image/"):
            preview_url = f"{self.base_url}/preview/{attachment_id}"
            attachment = ImageAttachment(
                id=attachment_id,
                type="image",
                mime_type=input.mime_type,
                name=input.name,
                upload_url=AnyUrl(upload_url),
                preview_url=AnyUrl(preview_url),
            )
        else:
            attachment = FileAttachment(
                id=attachment_id,
                type="file",
                mime_type=input.mime_type,
                name=input.name,
                upload_url=AnyUrl(upload_url),
            )

        if self.metadata_store is not None:
            await self.metadata_store.save_attachment(attachment, context)

        return attachment

    async def delete_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> None:
        if self.metadata_store is not None:
            await self.metadata_store.delete_attachment(attachment_id, context)
