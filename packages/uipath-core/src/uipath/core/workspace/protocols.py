"""Service protocols for workspace hydration backend interactions."""

from __future__ import annotations

from typing import Protocol, overload, runtime_checkable
from uuid import UUID


@runtime_checkable
class AttachmentsProtocol(Protocol):
    """Subset of the UiPath attachments service used by workspace hydration."""

    async def download_async(
        self,
        *,
        key: UUID,
        destination_path: str,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> str:
        """Download an attachment to a local path."""

    # Overloads mirror the concrete AttachmentsService: content XOR source_path,
    # so the real service is a structural subtype of this protocol.
    @overload
    async def upload_async(
        self,
        *,
        name: str,
        content: str | bytes,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> UUID: ...

    @overload
    async def upload_async(
        self,
        *,
        name: str,
        source_path: str,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> UUID: ...

    async def upload_async(
        self,
        *,
        name: str,
        content: str | bytes | None = None,
        source_path: str | None = None,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> UUID:
        """Upload content or a local file and return its attachment key."""


@runtime_checkable
class JobsProtocol(Protocol):
    """Subset of the UiPath jobs service used by workspace hydration."""

    async def list_attachments_async(
        self,
        *,
        job_key: UUID,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> list[str]:
        """List the attachment ids linked to a job."""

    async def link_attachment_async(
        self,
        *,
        job_key: UUID,
        attachment_key: UUID,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> None:
        """Link an existing attachment to a job."""
