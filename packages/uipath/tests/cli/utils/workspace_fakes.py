from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeResult,
    UiPathRuntimeSchema,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
    get_workspace_path,
)
from uipath.runtime.events import UiPathRuntimeEvent

OPTED_IN = UiPathRuntimeFactorySettings(managed_workspace=True)
REGISTRY = ("workspace", "attachments")


class FakeAttachments:
    def __init__(self) -> None:
        self.blobs: dict[UUID, bytes] = {}
        self.folder_keys: list[str | None] = []

    async def upload_async(
        self,
        *,
        name: str,
        content: str | bytes | None = None,
        source_path: str | None = None,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> UUID:
        self.folder_keys.append(folder_key)
        key = uuid4()
        if source_path is not None:
            self.blobs[key] = Path(source_path).read_bytes()
        elif isinstance(content, str):
            self.blobs[key] = content.encode()
        else:
            self.blobs[key] = content or b""
        return key

    async def download_async(
        self,
        *,
        key: UUID,
        destination_path: str,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> str:
        self.folder_keys.append(folder_key)
        Path(destination_path).write_bytes(self.blobs[key])
        return destination_path


class FakeJobs:
    def __init__(self) -> None:
        self.links: list[tuple[UUID, UUID]] = []
        self.folder_keys: list[str | None] = []

    async def list_attachments_async(
        self,
        *,
        job_key: UUID,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> list[str]:
        self.folder_keys.append(folder_key)
        return [str(attachment) for job, attachment in self.links if job == job_key]

    async def link_attachment_async(
        self,
        *,
        job_key: UUID,
        attachment_key: UUID,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> None:
        self.folder_keys.append(folder_key)
        self.links.append((job_key, attachment_key))


class FakeSdk:
    """Stands in for ``UiPath()``: the attachment and job APIs are the network boundary."""

    def __init__(self) -> None:
        self.attachments = FakeAttachments()
        self.jobs = FakeJobs()


class MemoryStorage:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str], Any] = {}

    async def set_value(
        self, runtime_id: str, namespace: str, key: str, value: Any
    ) -> None:
        self.values[(runtime_id, namespace, key)] = value

    async def get_value(self, runtime_id: str, namespace: str, key: str) -> Any:
        return self.values.get((runtime_id, namespace, key))


class FileRuntime:
    """Writes or reads one workspace file, the way an agent's file tools would."""

    def __init__(
        self,
        *,
        write: str | None = None,
        status: UiPathRuntimeStatus = UiPathRuntimeStatus.SUCCESSFUL,
    ) -> None:
        self.write = write
        self.status = status
        self.workspace_path: Path | None = None

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        self.workspace_path = get_workspace_path()
        report = self.workspace_path / "report.md"
        if self.write is not None:
            report.write_text(self.write)
        content = report.read_text() if report.exists() else None
        return UiPathRuntimeResult(status=self.status, output={"report": content})

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield await self.execute(input, options)

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath="main",
            uniqueId="main",
            type="agent",
            input={"type": "object", "properties": {}},
            output={"type": "object", "properties": {}},
        )

    async def dispose(self) -> None:
        pass


class WorkspaceFactory:
    """A factory that opts in to the managed workspace and hands out ``FileRuntime``s."""

    def __init__(
        self,
        runtime: FileRuntime,
        *,
        storage: MemoryStorage | None,
        settings: UiPathRuntimeFactorySettings | None = OPTED_IN,
    ) -> None:
        self.runtime = runtime
        self.storage = storage
        self.settings = settings

    def discover_entrypoints(self) -> list[str]:
        return ["main"]

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return self.settings

    async def get_storage(self) -> MemoryStorage | None:
        return self.storage

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs: Any
    ) -> FileRuntime:
        return self.runtime

    async def dispose(self) -> None:
        pass
