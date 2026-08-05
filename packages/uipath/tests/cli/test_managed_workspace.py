from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from uipath._cli._managed_workspace import wrap_with_managed_workspace
from uipath.runtime import HydrationRuntime


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("job_id", "enabled"),
    [(None, True), ("job-id", False)],
)
async def test_skips_managed_workspace_when_not_applicable(
    job_id: str | None,
    enabled: bool,
) -> None:
    delegate = Mock()
    factory = Mock(get_storage=AsyncMock())
    context = Mock(job_id=job_id)
    cleanup = AsyncExitStack()

    with patch("uipath._cli._managed_workspace.UiPath") as client_type:
        runtime = await wrap_with_managed_workspace(
            delegate,
            context=context,
            factory=factory,
            enabled=enabled,
            cleanup=cleanup,
        )

    assert runtime is delegate
    factory.get_storage.assert_not_awaited()
    client_type.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_missing_managed_workspace_storage() -> None:
    factory = Mock(get_storage=AsyncMock(return_value=None))
    context = Mock(job_id="job-id")

    with pytest.raises(
        RuntimeError,
        match="advertises managed workspace support but provides no storage",
    ):
        await wrap_with_managed_workspace(
            Mock(),
            context=context,
            factory=factory,
            enabled=True,
            cleanup=AsyncExitStack(),
        )


@pytest.mark.asyncio
async def test_creates_hydration_runtime_for_non_conversational_job(
    tmp_path: Path,
) -> None:
    delegate = Mock(dispose=AsyncMock())
    storage = Mock()
    factory = Mock(get_storage=AsyncMock(return_value=storage))
    context = Mock(
        job_id="job-id",
        folder_key="folder-key",
        conversation_id=None,
        exchange_id=None,
    )
    workspace = Mock(path=tmp_path, dispose=AsyncMock())
    client = Mock(attachments=Mock(), jobs=Mock())
    cleanup = AsyncExitStack()

    with (
        patch("uipath._cli._managed_workspace.UiPath", return_value=client),
        patch(
            "uipath._cli._managed_workspace.Workspace.create",
            return_value=workspace,
        ),
    ):
        runtime = await wrap_with_managed_workspace(
            delegate,
            context=context,
            factory=factory,
            enabled=True,
            cleanup=cleanup,
        )

    assert isinstance(runtime, HydrationRuntime)
    await cleanup.aclose()


@pytest.mark.asyncio
async def test_disposes_workspace_when_runtime_construction_fails(
    tmp_path: Path,
) -> None:
    delegate = Mock(dispose=AsyncMock())
    factory = Mock(get_storage=AsyncMock(return_value=Mock()))
    context = Mock(job_id="job-id", folder_key=None)
    workspace = Mock(path=tmp_path, dispose=AsyncMock())
    cleanup = AsyncExitStack()

    with (
        patch("uipath._cli._managed_workspace.UiPath"),
        patch(
            "uipath._cli._managed_workspace.Workspace.create",
            return_value=workspace,
        ),
        patch(
            "uipath._cli._managed_workspace.WorkspaceHydrator",
            side_effect=RuntimeError("construction failed"),
        ),
        pytest.raises(RuntimeError, match="construction failed"),
    ):
        await wrap_with_managed_workspace(
            delegate,
            context=context,
            factory=factory,
            enabled=True,
            cleanup=cleanup,
        )

    workspace.dispose.assert_awaited_once()
