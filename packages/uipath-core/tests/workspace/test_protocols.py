"""Structural-conformance tests for the workspace hydration protocols."""

from __future__ import annotations

from uuid import UUID, uuid4

from uipath.core.workspace import AttachmentsProtocol, JobsProtocol


class _FakeAttachments:
    async def download_async(
        self,
        *,
        key: UUID,
        destination_path: str,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> str:
        return destination_path

    async def upload_async(
        self,
        *,
        name: str,
        content: str | bytes | None = None,
        source_path: str | None = None,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> UUID:
        return uuid4()


class _FakeJobs:
    async def list_attachments_async(
        self,
        *,
        job_key: UUID,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> list[str]:
        return []

    async def link_attachment_async(
        self,
        *,
        job_key: UUID,
        attachment_key: UUID,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> None:
        return None


class _NotAService:
    pass


def test_attachments_service_satisfies_protocol() -> None:
    assert isinstance(_FakeAttachments(), AttachmentsProtocol)


def test_jobs_service_satisfies_protocol() -> None:
    assert isinstance(_FakeJobs(), JobsProtocol)


def test_unrelated_object_does_not_satisfy_protocols() -> None:
    assert not isinstance(_NotAService(), AttachmentsProtocol)
    assert not isinstance(_NotAService(), JobsProtocol)
