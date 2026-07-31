"""Tests for resource overwrites context ordering in the eval CLI.

The overwrites context must be entered before the runtime is created:
building the agent graph resolves folder-scoped resources (e.g. escalation
memory spaces) at tool-creation time, and those lookups need the
overwritten folder paths.
"""

import json
import os
from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult
from uipath.platform.common._bindings import _resource_overwrites


def _middleware_continue() -> MiddlewareResult:
    return MiddlewareResult(
        should_continue=True,
        error_message=None,
        should_include_stacktrace=False,
    )


def _write_project_files() -> None:
    with open("uipath.json", "w") as f:
        json.dump({"functions": {"agent": "main.py:main"}}, f)

    os.makedirs("evaluations/eval-sets", exist_ok=True)
    eval_set = {
        "version": "1.0",
        "id": "test-set",
        "name": "Test Set",
        "evaluatorRefs": [],
        "evaluations": [],
    }
    with open("evaluations/eval-sets/test-set.json", "w") as f:
        json.dump(eval_set, f)


def _make_mock_runtime() -> Mock:
    mock_runtime = Mock()
    mock_runtime.get_schema = AsyncMock(
        return_value=Mock(metadata=None, input_schema=None, output_schema=None)
    )
    mock_runtime.dispose = AsyncMock()
    return mock_runtime


def _make_mock_factory(mock_runtime: Mock) -> Mock:
    mock_factory = Mock()
    mock_factory.discover_entrypoints.return_value = ["agent"]
    mock_factory.get_settings = AsyncMock(return_value=None)
    mock_factory.dispose = AsyncMock()
    mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)
    return mock_factory


def _enter_base_patches(stack: ExitStack, mock_factory: Mock) -> None:
    stack.enter_context(
        patch(
            "uipath._cli.cli_eval.Middlewares.next",
            return_value=_middleware_continue(),
        )
    )
    stack.enter_context(
        patch(
            "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
            return_value=mock_factory,
        )
    )
    stack.enter_context(
        patch("uipath._cli.cli_eval.setup_reporting_prereq", return_value=False)
    )
    stack.enter_context(
        patch(
            "uipath._cli.cli_eval.EvalHelpers.load_evaluators",
            new=AsyncMock(return_value=[]),
        )
    )
    stack.enter_context(
        patch("uipath._cli.cli_eval.evaluate", new=AsyncMock(return_value=None))
    )


class TestEvalResourceOverwritesOrdering:
    def test_overwrites_context_active_when_runtime_is_created(
        self, runner: CliRunner, temp_dir: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """new_runtime must run inside the resource overwrites context."""
        monkeypatch.setenv("UIPATH_PROJECT_ID", "project-123")

        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project_files()

            overwrite = Mock()
            overwrites = {"memorySpace.MemorySpace": overwrite}
            overwrites_seen_by_new_runtime: list[Any] = []

            mock_runtime = _make_mock_runtime()

            async def new_runtime(*args: Any, **kwargs: Any) -> Mock:
                overwrites_seen_by_new_runtime.append(_resource_overwrites.get())
                return mock_runtime

            mock_factory = _make_mock_factory(mock_runtime)
            mock_factory.new_runtime = AsyncMock(side_effect=new_runtime)

            mock_studio_client = Mock()
            mock_studio_client.get_resource_overwrites = AsyncMock(
                return_value=overwrites
            )

            with ExitStack() as stack:
                _enter_base_patches(stack, mock_factory)
                stack.enter_context(
                    patch(
                        "uipath._cli.cli_eval.StudioClient",
                        return_value=mock_studio_client,
                    )
                )
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code == 0
            mock_studio_client.get_resource_overwrites.assert_awaited_once()
            assert overwrites_seen_by_new_runtime == [overwrites]
            mock_runtime.dispose.assert_awaited_once()

    def test_no_project_id_runs_without_overwrites(
        self, runner: CliRunner, temp_dir: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UIPATH_PROJECT_ID", raising=False)

        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project_files()

            overwrites_seen_by_new_runtime: list[Any] = []
            mock_runtime = _make_mock_runtime()

            async def new_runtime(*args: Any, **kwargs: Any) -> Mock:
                overwrites_seen_by_new_runtime.append(_resource_overwrites.get())
                return mock_runtime

            mock_factory = _make_mock_factory(mock_runtime)
            mock_factory.new_runtime = AsyncMock(side_effect=new_runtime)

            with ExitStack() as stack:
                _enter_base_patches(stack, mock_factory)
                mock_studio_client_cls = stack.enter_context(
                    patch("uipath._cli.cli_eval.StudioClient")
                )
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code == 0
            mock_studio_client_cls.assert_not_called()
            assert overwrites_seen_by_new_runtime == [None]
            mock_runtime.dispose.assert_awaited_once()

    def test_runtime_disposed_when_schema_loading_fails(
        self, runner: CliRunner, temp_dir: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UIPATH_PROJECT_ID", raising=False)

        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project_files()

            mock_runtime = _make_mock_runtime()
            mock_runtime.get_schema = AsyncMock(
                side_effect=RuntimeError("schema loading failed")
            )
            mock_factory = _make_mock_factory(mock_runtime)

            with ExitStack() as stack:
                _enter_base_patches(stack, mock_factory)
                stack.enter_context(patch("uipath._cli.cli_eval.StudioClient"))
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code != 0
            mock_runtime.dispose.assert_awaited_once()
