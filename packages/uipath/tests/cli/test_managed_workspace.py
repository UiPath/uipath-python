from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from tests.cli.utils.workspace_fakes import (
    OPTED_IN,
    FakeSdk,
    FileRuntime,
    MemoryStorage,
    WorkspaceFactory,
)
from uipath._utils._managed_workspace import wrap_with_managed_workspace
from uipath.platform.constants import ENV_FOLDER_KEY
from uipath.runtime import (
    UiPathRuntimeFactorySettings,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)

JOB_ID = str(uuid4())


async def _run(
    runtime: FileRuntime,
    storage: MemoryStorage | None,
    *,
    settings: UiPathRuntimeFactorySettings | None = OPTED_IN,
    job_id: str | None = JOB_ID,
    conversation_id: str | None = None,
) -> UiPathRuntimeResult:
    wrapped = await wrap_with_managed_workspace(
        runtime,
        factory=WorkspaceFactory(runtime, storage=storage),
        settings=settings,
        runtime_id="runtime-1",
        job_id=job_id,
        conversation_id=conversation_id,
    )
    try:
        return await wrapped.execute()
    finally:
        await wrapped.dispose()


async def test_files_written_before_a_suspend_are_back_after_resume(
    sdk: FakeSdk,
) -> None:
    storage = MemoryStorage()

    await _run(
        FileRuntime(write="draft", status=UiPathRuntimeStatus.SUSPENDED), storage
    )
    resumed = await _run(FileRuntime(), storage)

    assert resumed.output == {"report": "draft"}


async def test_uploads_are_linked_to_the_job(sdk: FakeSdk) -> None:
    await _run(
        FileRuntime(write="draft", status=UiPathRuntimeStatus.SUSPENDED),
        MemoryStorage(),
    )

    assert [job for job, _ in sdk.jobs.links] == [UUID(JOB_ID)]
    assert list(sdk.attachments.blobs.values()) == [b"draft"]


async def test_attachment_calls_use_the_job_folder(
    sdk: FakeSdk, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_FOLDER_KEY, "folder-1")
    storage = MemoryStorage()

    await _run(
        FileRuntime(write="draft", status=UiPathRuntimeStatus.SUSPENDED), storage
    )
    await _run(FileRuntime(), storage)

    assert sdk.attachments.folder_keys
    assert sdk.jobs.folder_keys
    assert set(sdk.attachments.folder_keys + sdk.jobs.folder_keys) == {"folder-1"}


async def test_successful_run_outside_a_conversation_uploads_nothing(
    sdk: FakeSdk,
) -> None:
    await _run(FileRuntime(write="final"), MemoryStorage())

    assert sdk.attachments.blobs == {}


async def test_successful_exchange_in_a_conversation_keeps_files_for_the_next(
    sdk: FakeSdk,
) -> None:
    storage = MemoryStorage()

    await _run(FileRuntime(write="notes"), storage, conversation_id="conv-1")
    next_exchange = await _run(FileRuntime(), storage, conversation_id="conv-1")

    assert next_exchange.output == {"report": "notes"}


async def test_dispose_removes_the_workspace_folder(sdk: FakeSdk) -> None:
    runtime = FileRuntime(write="draft", status=UiPathRuntimeStatus.SUSPENDED)

    await _run(runtime, MemoryStorage())

    assert runtime.workspace_path is not None
    assert not runtime.workspace_path.exists()


@pytest.mark.parametrize(
    ("settings", "job_id", "storage"),
    [
        pytest.param(None, JOB_ID, MemoryStorage(), id="factory-without-settings"),
        pytest.param(
            UiPathRuntimeFactorySettings(),
            JOB_ID,
            MemoryStorage(),
            id="factory-not-opted-in",
        ),
        pytest.param(OPTED_IN, None, MemoryStorage(), id="not-a-job"),
        pytest.param(OPTED_IN, JOB_ID, None, id="factory-without-storage"),
    ],
)
async def test_runtime_is_left_unwrapped(
    settings: UiPathRuntimeFactorySettings | None,
    job_id: str | None,
    storage: MemoryStorage | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_sdk() -> FakeSdk:
        raise AssertionError("the SDK must not be built for an unwrapped runtime")

    monkeypatch.setattr("uipath._utils._managed_workspace.UiPath", no_sdk)
    runtime = FileRuntime()

    wrapped = await wrap_with_managed_workspace(
        runtime,
        factory=WorkspaceFactory(runtime, storage=storage),
        settings=settings,
        runtime_id="runtime-1",
        job_id=job_id,
    )

    assert wrapped is runtime
