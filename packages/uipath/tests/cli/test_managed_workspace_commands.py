from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tests.cli.utils.workspace_fakes import (
    REGISTRY,
    FakeSdk,
    FileRuntime,
    MemoryStorage,
    WorkspaceFactory,
)
from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult
from uipath.runtime import UiPathRuntimeStatus
from uipath.runtime.debug.detached import DetachedDebugBridge

JOB_ID = str(uuid.uuid4())


@pytest.fixture
def job_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UIPATH_JOB_KEY", JOB_ID)
    monkeypatch.setenv("UIPATH_TRACING_ENABLED", "false")


@asynccontextmanager
async def _no_resource_overwrites(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield


def _continue() -> MiddlewareResult:
    return MiddlewareResult(should_continue=True)


def _suspending_factory(storage: MemoryStorage) -> WorkspaceFactory:
    return WorkspaceFactory(
        FileRuntime(write="draft", status=UiPathRuntimeStatus.SUSPENDED),
        storage=storage,
    )


def _uploaded(sdk: FakeSdk) -> list[bytes]:
    return list(sdk.attachments.blobs.values())


def test_run_uploads_the_workspace_when_a_job_suspends(
    runner: CliRunner, temp_dir: str, sdk: FakeSdk, job_env: None
) -> None:
    storage = MemoryStorage()
    factory = _suspending_factory(storage)

    with runner.isolated_filesystem(temp_dir=temp_dir):
        with (
            patch("uipath._cli.cli_run.Middlewares.next", return_value=_continue()),
            patch(
                "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                return_value=factory,
            ),
            patch(
                "uipath._cli.cli_run.ResourceOverwritesContext",
                side_effect=_no_resource_overwrites,
            ),
        ):
            result = runner.invoke(cli, ["run", "main", "{}"])

    assert result.exit_code == 0, result.output
    assert _uploaded(sdk) == [b"draft"]
    assert (JOB_ID, *REGISTRY) in storage.values


@pytest.mark.parametrize("command", ["run", "debug"])
def test_successful_conversation_exchange_uploads_the_workspace(
    command: str,
    runner: CliRunner,
    temp_dir: str,
    sdk: FakeSdk,
    job_env: None,
) -> None:
    factory = WorkspaceFactory(FileRuntime(write="notes"), storage=MemoryStorage())
    module = f"uipath._cli.cli_{command}"

    with runner.isolated_filesystem(temp_dir=temp_dir):
        Path("uipath.json").write_text(
            json.dumps(
                {"fpsProperties": {"conversationalService.conversationId": "conv-1"}}
            )
        )
        with (
            patch(f"{module}.Middlewares.next", return_value=_continue()),
            patch(f"{module}.UiPathRuntimeFactoryRegistry.get", return_value=factory),
            patch(
                "uipath._cli.cli_run.ResourceOverwritesContext",
                side_effect=_no_resource_overwrites,
            ),
            patch(
                "uipath._cli.cli_debug.get_debug_bridge",
                return_value=DetachedDebugBridge(),
            ),
        ):
            result = runner.invoke(cli, [command, "main", "{}"])

    assert result.exit_code == 0, result.output
    assert _uploaded(sdk) == [b"notes"]


def test_run_without_a_job_leaves_the_runtime_unwrapped(
    runner: CliRunner, temp_dir: str, sdk: FakeSdk, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("UIPATH_JOB_KEY", raising=False)
    factory = _suspending_factory(MemoryStorage())

    with runner.isolated_filesystem(temp_dir=temp_dir):
        with (
            patch("uipath._cli.cli_run.Middlewares.next", return_value=_continue()),
            patch(
                "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                return_value=factory,
            ),
            patch(
                "uipath._cli.cli_run.ResourceOverwritesContext",
                side_effect=_no_resource_overwrites,
            ),
        ):
            result = runner.invoke(cli, ["run", "main", "{}"])

    assert "Managed Workspace Unavailable" in result.output
    assert _uploaded(sdk) == []


def test_debug_uploads_the_workspace_when_a_job_suspends(
    runner: CliRunner, temp_dir: str, sdk: FakeSdk, job_env: None
) -> None:
    storage = MemoryStorage()
    factory = _suspending_factory(storage)

    with runner.isolated_filesystem(temp_dir=temp_dir):
        with (
            patch("uipath._cli.cli_debug.Middlewares.next", return_value=_continue()),
            patch(
                "uipath._cli.cli_debug.UiPathRuntimeFactoryRegistry.get",
                return_value=factory,
            ),
            patch(
                "uipath._cli.cli_debug.get_debug_bridge",
                return_value=DetachedDebugBridge(),
            ),
        ):
            result = runner.invoke(cli, ["debug", "main", "{}"])

    assert result.exit_code == 0, result.output
    assert _uploaded(sdk) == [b"draft"]
    assert (JOB_ID, *REGISTRY) in storage.values
