# type: ignore
import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult
from uipath.runtime import (
    ConversationalWorkspaceRuntime,
    HydrationRuntime,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    get_workspace_path,
)


def _middleware_continue():
    return MiddlewareResult(
        should_continue=True,
        error_message=None,
        should_include_stacktrace=False,
    )


async def _empty_async_gen(*args, **kwargs):
    """An async generator that yields nothing (simulates empty runtime.stream)."""
    if False:  # pragma: no cover
        yield


def _make_mock_factory(entrypoints: list[str]):
    """Create a mock runtime factory with given entrypoints."""
    mock_factory = Mock()
    mock_factory.discover_entrypoints.return_value = entrypoints
    mock_factory.get_settings = AsyncMock(return_value=None)
    mock_factory.dispose = AsyncMock()

    mock_runtime = Mock()
    mock_runtime.execute = AsyncMock(return_value=Mock(status="SUCCESSFUL"))
    mock_runtime.stream = Mock(side_effect=_empty_async_gen)
    mock_runtime.dispose = AsyncMock()
    mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

    return mock_factory


@asynccontextmanager
async def _mock_resource_overwrites_context(*args, **kwargs):
    yield


@pytest.fixture
def entrypoint():
    return "main"


@pytest.fixture
def simple_script() -> str:
    if os.path.isfile("mocks/simple_script.py"):
        with open("mocks/simple_script.py", "r") as file:
            data = file.read()
    else:
        with open("tests/cli/mocks/simple_script.py", "r") as file:
            data = file.read()
    return data


@pytest.fixture
def mock_env_vars():
    return {
        "UIPATH_CONFIG_PATH": "test_config.json",
        "UIPATH_JOB_KEY": "test-job-id",
        "UIPATH_TRACE_ID": "test-trace-id",
        "UIPATH_TRACING_ENABLED": "true",
        "UIPATH_PARENT_SPAN_ID": "test-parent-span",
        "UIPATH_ROOT_SPAN_ID": "test-root-span",
        "UIPATH_ORGANIZATION_ID": "test-org-id",
        "UIPATH_TENANT_ID": "test-tenant-id",
        "UIPATH_PROCESS_UUID": "test-process-id",
        "UIPATH_FOLDER_KEY": "test-folder-key",
        "LOG_LEVEL": "DEBUG",
    }


def create_uipath_json(script_path: str, entrypoint_name: str = "main"):
    """Helper to create uipath.json with functions."""
    return {"functions": {entrypoint_name: f"{script_path}:main"}}


class TestRun:
    class TestFileInput:
        def test_run_input_file_not_found(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            with runner.isolated_filesystem(temp_dir=temp_dir):
                script_file = "entrypoint.py"
                file_path = os.path.join(temp_dir, script_file)
                with open(file_path, "w") as f:
                    f.write("def main(input): return input")

                # Create uipath.json
                with open("uipath.json", "w") as f:
                    import json

                    json.dump(create_uipath_json(script_file), f)

                result = runner.invoke(
                    cli, ["run", entrypoint, "--file", "not-here.json"]
                )
                assert result.exit_code != 0
                assert "Error: Invalid value for '-f' / '--file'" in result.output

        def test_run_invalid_input_file(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            file_name = "not-json.txt"
            with runner.isolated_filesystem(temp_dir=temp_dir):
                script_file = "entrypoint.py"
                script_file_path = os.path.join(temp_dir, script_file)
                with open(script_file_path, "w") as f:
                    f.write("def main(input): return input")

                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "w") as f:
                    f.write("file content")

                # Create uipath.json
                with open("uipath.json", "w") as f:
                    import json

                    json.dump(create_uipath_json(script_file_path), f)

                result = runner.invoke(cli, ["run", "main", "--file", file_path])
                assert result.exit_code == 1
                assert "Invalid Input File Extension" in result.output

        def test_run_input_file_success(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
        ):
            file_name = "input.json"
            json_content = """
            {
                "input_key": "input_value"
            }"""

            with runner.isolated_filesystem(temp_dir=temp_dir):
                script_file = "entrypoint.py"
                script_file_path = os.path.join(temp_dir, script_file)
                with open(script_file_path, "w") as f:
                    f.write("def main(input): return input")

                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "w") as f:
                    f.write(json_content)

                # Create uipath.json
                with open("uipath.json", "w") as f:
                    import json

                    json.dump(create_uipath_json(script_file), f)

                with patch("uipath._cli.cli_run.Middlewares.next") as mock_middleware:
                    mock_middleware.return_value = MiddlewareResult(
                        should_continue=False,
                        info_message="Execution succeeded",
                        error_message=None,
                        should_include_stacktrace=False,
                    )
                    result = runner.invoke(
                        cli, ["run", entrypoint, "--file", file_path]
                    )
                    assert result.exit_code == 0
                    assert "Successful execution." in result.output

    class TestMiddleware:
        def test_autodiscover_entrypoint(self, runner: CliRunner, temp_dir: str):
            """When exactly one entrypoint exists, it is auto-resolved."""
            with runner.isolated_filesystem(temp_dir=temp_dir):
                mock_factory = _make_mock_factory(["my_agent"])

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=mock_factory,
                    ),
                    patch(
                        "uipath._cli.cli_run.ResourceOverwritesContext",
                        side_effect=_mock_resource_overwrites_context,
                    ),
                ):
                    result = runner.invoke(cli, ["run"])

                assert result.exit_code == 0, (
                    f"output: {result.output!r}, exception: {result.exception}"
                )
                assert "Successful execution." in result.output
                mock_factory.new_runtime.assert_awaited_once()
                assert mock_factory.new_runtime.call_args[0][0] == "my_agent"

        def test_no_entrypoint_multiple_available(
            self, runner: CliRunner, temp_dir: str
        ):
            """When multiple entrypoints exist and none specified, show usage help."""
            with runner.isolated_filesystem(temp_dir=temp_dir):
                mock_factory = _make_mock_factory(["agent_a", "agent_b"])

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=mock_factory,
                    ),
                ):
                    result = runner.invoke(cli, ["run"])

                assert result.exit_code == 0
                assert "Available entrypoints:" in result.output
                assert "agent_a" in result.output
                assert "agent_b" in result.output
                assert "Usage: uipath run" in result.output
                mock_factory.new_runtime.assert_not_awaited()

        def test_no_entrypoint_none_available(self, runner: CliRunner, temp_dir: str):
            """When no entrypoints exist and none specified, show usage help."""
            with runner.isolated_filesystem(temp_dir=temp_dir):
                mock_factory = _make_mock_factory([])

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=mock_factory,
                    ),
                ):
                    result = runner.invoke(cli, ["run"])

                assert result.exit_code == 0
                assert "No entrypoints found" in result.output
                assert "Usage: uipath run" in result.output
                mock_factory.new_runtime.assert_not_awaited()

        def test_script_not_found(
            self, runner: CliRunner, temp_dir: str, entrypoint: str
        ):
            with runner.isolated_filesystem(temp_dir=temp_dir):
                # Create uipath.json but no actual script file
                with open("uipath.json", "w") as f:
                    import json

                    json.dump(create_uipath_json("nonexistent.py"), f)

                result = runner.invoke(cli, ["run", entrypoint])
                assert result.exit_code == 1
                assert "not found" in result.output.lower()

        def test_successful_execution(
            self,
            runner: CliRunner,
            temp_dir: str,
            entrypoint: str,
            mock_env_vars: dict,
            simple_script: str,
        ):
            input_file_name = "input.json"
            output_file_name = "output.json"
            input_json_content = """
            {
                "message": "Hello world",
                "repeat": 2
            }"""
            with runner.isolated_filesystem(temp_dir=temp_dir):
                # create input file
                input_file_path = os.path.join(temp_dir, input_file_name)
                output_file_path = os.path.join(temp_dir, output_file_name)
                with open(input_file_path, "w") as f:
                    f.write(input_json_content)

                # Create test script
                script_file = "entrypoint.py"
                script_file_path = os.path.join(temp_dir, script_file)
                with open(script_file_path, "w") as f:
                    f.write(simple_script)

                # create uipath.json
                with open("uipath.json", "w") as f:
                    import json

                    json.dump(create_uipath_json(script_file_path), f)

                result = runner.invoke(
                    cli,
                    [
                        "run",
                        "main",
                        "--input-file",
                        input_file_path,
                        "--output-file",
                        output_file_path,
                    ],
                )
                assert result.exit_code == 0
                assert "Successful execution." in result.output
                assert result.output.count("Hello world") >= 2
                assert os.path.exists(output_file_path)
                with open(output_file_path, "r") as f:
                    output = f.read()
                    assert output.count("Hello world") >= 2

        def test_installs_workspace_runtimes_before_chat_runtime(
            self,
            runner: CliRunner,
            temp_dir: str,
            monkeypatch: pytest.MonkeyPatch,
        ):
            factory = _make_mock_factory(["main"])
            base_runtime = factory.new_runtime.return_value
            storage = Mock()
            factory.get_storage = AsyncMock(return_value=storage)
            factory.get_settings = AsyncMock(
                return_value=UiPathRuntimeFactorySettings(managed_workspace=True)
            )
            chat_bridge = Mock()
            chat_runtime = Mock(
                execute=AsyncMock(return_value=Mock()),
                dispose=AsyncMock(),
            )
            client = Mock(attachments=Mock(), jobs=Mock())

            monkeypatch.setenv("UIPATH_JOB_KEY", "00000000-0000-0000-0000-000000000001")
            monkeypatch.setenv("UIPATH_TRACING_ENABLED", "false")

            with runner.isolated_filesystem(temp_dir=temp_dir):
                with open("uipath.json", "w") as file:
                    json.dump(
                        {
                            "fpsProperties": {
                                "conversationalService.conversationId": "conversation-id",
                                "conversationalService.exchangeId": "exchange-id",
                            }
                        },
                        file,
                    )

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=factory,
                    ),
                    patch(
                        "uipath._cli.cli_run.ResourceOverwritesContext",
                        side_effect=_mock_resource_overwrites_context,
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPath",
                        return_value=client,
                    ),
                    patch(
                        "uipath._cli.cli_run.get_chat_bridge",
                        return_value=chat_bridge,
                    ),
                    patch("uipath._cli.cli_run.UiPathChatRuntime") as chat_runtime_type,
                ):
                    chat_runtime_type.return_value = chat_runtime
                    result = runner.invoke(cli, ["run", "main"])

            assert result.exit_code == 0, (
                f"output: {result.output!r}, exception: {result.exception}"
            )
            wrapped_runtime = chat_runtime_type.call_args.kwargs["delegate"]
            assert isinstance(wrapped_runtime, ConversationalWorkspaceRuntime)
            assert isinstance(wrapped_runtime.delegate, HydrationRuntime)
            assert wrapped_runtime.delegate.delegate is base_runtime
            assert wrapped_runtime.registry_store is None
            assert (
                wrapped_runtime.delegate.registry_store.runtime_id
                == "00000000-0000-0000-0000-000000000001"
            )
            assert not wrapped_runtime.delegate.workspace.path.exists()
            factory.get_storage.assert_awaited_once()
            chat_runtime.dispose.assert_awaited_once()
            base_runtime.dispose.assert_awaited_once()

        def test_suspended_workspace_takes_precedence_over_conversation_snapshot(
            self,
            runner: CliRunner,
            temp_dir: str,
            monkeypatch: pytest.MonkeyPatch,
        ):
            conversation_attachment_key = UUID(int=1)
            suspended_attachment_key = UUID(int=2)
            job_key = UUID(int=3)
            attachment_contents = {
                conversation_attachment_key: b"conversation",
                suspended_attachment_key: b"suspended",
            }

            async def download_attachment(key, destination_path, **_):
                Path(destination_path).write_bytes(attachment_contents[key])

            attachments = Mock(
                download_async=AsyncMock(side_effect=download_attachment),
                upload_async=AsyncMock(return_value=UUID(int=4)),
            )
            client = Mock(
                attachments=attachments,
                jobs=Mock(link_attachment_async=AsyncMock()),
            )
            storage = Mock(
                get_value=AsyncMock(
                    return_value={
                        "notes.txt": {
                            "attachment_key": str(suspended_attachment_key),
                            "sha256": hashlib.sha256(b"suspended").hexdigest(),
                            "size": len(b"suspended"),
                            "uploaded_at": "2026-01-01T00:00:00+00:00",
                            "attachment_name": ".uipath-workspace~1notes.txt",
                        }
                    }
                ),
                set_value=AsyncMock(),
            )
            observed_contents = []

            async def stream_runtime(*_, **__):
                observed_contents.append(
                    (get_workspace_path() / "notes.txt").read_text(encoding="utf-8")
                )
                yield UiPathRuntimeResult(status=UiPathRuntimeStatus.SUCCESSFUL)

            base_runtime = Mock(
                stream=Mock(side_effect=stream_runtime),
                dispose=AsyncMock(),
            )
            factory = Mock(
                discover_entrypoints=Mock(return_value=["main"]),
                new_runtime=AsyncMock(return_value=base_runtime),
                get_settings=AsyncMock(
                    return_value=UiPathRuntimeFactorySettings(managed_workspace=True)
                ),
                get_storage=AsyncMock(return_value=storage),
                dispose=AsyncMock(),
            )
            chat_runtime = Mock(dispose=AsyncMock())

            async def execute_chat(input, options):
                workspace_runtime = chat_runtime_type.call_args.kwargs["delegate"]
                return await workspace_runtime.execute(input, options=options)

            chat_runtime.execute = AsyncMock(side_effect=execute_chat)

            monkeypatch.setenv("UIPATH_JOB_KEY", str(job_key))
            monkeypatch.setenv("UIPATH_TRACING_ENABLED", "false")

            input = {
                "uipath__conversation_meta_events": [
                    {
                        "metaEvent": {
                            "workspaceFiles": [
                                {
                                    "path": "notes.txt",
                                    "attachmentKey": str(conversation_attachment_key),
                                }
                            ]
                        }
                    }
                ]
            }

            with runner.isolated_filesystem(temp_dir=temp_dir):
                with open("uipath.json", "w") as file:
                    json.dump(
                        {
                            "fpsProperties": {
                                "conversationalService.conversationId": "conversation-id",
                                "conversationalService.exchangeId": "exchange-id",
                            }
                        },
                        file,
                    )

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=factory,
                    ),
                    patch(
                        "uipath._cli.cli_run.ResourceOverwritesContext",
                        side_effect=_mock_resource_overwrites_context,
                    ),
                    patch("uipath._cli.cli_run.UiPath", return_value=client),
                    patch("uipath._cli.cli_run.get_chat_bridge"),
                    patch("uipath._cli.cli_run.UiPathChatRuntime") as chat_runtime_type,
                ):
                    chat_runtime_type.return_value = chat_runtime
                    result = runner.invoke(
                        cli,
                        ["run", "main", json.dumps(input)],
                    )

            assert result.exit_code == 0, (
                f"output: {result.output!r}, exception: {result.exception}"
            )
            assert observed_contents == ["suspended"]
            downloaded_keys = [
                call.kwargs["key"]
                for call in attachments.download_async.await_args_list
            ]
            assert downloaded_keys == [
                conversation_attachment_key,
                suspended_attachment_key,
            ]
            base_runtime.dispose.assert_awaited_once()

        def test_disposes_runtime_when_managed_workspace_has_no_storage(
            self,
            runner: CliRunner,
            temp_dir: str,
            monkeypatch: pytest.MonkeyPatch,
        ):
            factory = _make_mock_factory(["main"])
            base_runtime = factory.new_runtime.return_value
            factory.get_settings = AsyncMock(
                return_value=UiPathRuntimeFactorySettings(managed_workspace=True)
            )
            factory.get_storage = AsyncMock(return_value=None)

            monkeypatch.setenv("UIPATH_JOB_KEY", "job-id")
            monkeypatch.setenv("UIPATH_TRACING_ENABLED", "false")

            with runner.isolated_filesystem(temp_dir=temp_dir):
                with open("uipath.json", "w") as file:
                    json.dump({}, file)

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=factory,
                    ),
                    patch(
                        "uipath._cli.cli_run.ResourceOverwritesContext",
                        side_effect=_mock_resource_overwrites_context,
                    ),
                ):
                    runner.invoke(cli, ["run", "main"])

            base_runtime.dispose.assert_awaited_once()
            factory.dispose.assert_awaited_once()

        def test_cleanup_continues_after_workspace_construction_failure(
            self,
            runner: CliRunner,
            temp_dir: str,
            monkeypatch: pytest.MonkeyPatch,
        ):
            factory = _make_mock_factory(["main"])
            base_runtime = factory.new_runtime.return_value
            factory.get_settings = AsyncMock(
                return_value=UiPathRuntimeFactorySettings(managed_workspace=True)
            )
            factory.get_storage = AsyncMock(return_value=Mock())
            workspace = Mock(
                path=Path(temp_dir),
                dispose=AsyncMock(side_effect=RuntimeError("cleanup failed")),
            )

            monkeypatch.setenv("UIPATH_JOB_KEY", "job-id")
            monkeypatch.setenv("UIPATH_TRACING_ENABLED", "false")

            with runner.isolated_filesystem(temp_dir=temp_dir):
                with open("uipath.json", "w") as file:
                    json.dump({}, file)

                with (
                    patch(
                        "uipath._cli.cli_run.Middlewares.next",
                        return_value=_middleware_continue(),
                    ),
                    patch(
                        "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                        return_value=factory,
                    ),
                    patch(
                        "uipath._cli.cli_run.ResourceOverwritesContext",
                        side_effect=_mock_resource_overwrites_context,
                    ),
                    patch("uipath._cli.cli_run.UiPath"),
                    patch(
                        "uipath._cli.cli_run.Workspace.create",
                        return_value=workspace,
                    ),
                    patch(
                        "uipath._cli.cli_run.WorkspaceHydrator",
                        side_effect=RuntimeError("construction failed"),
                    ),
                ):
                    runner.invoke(cli, ["run", "main"])

            workspace.dispose.assert_awaited_once()
            base_runtime.dispose.assert_awaited_once()
            factory.dispose.assert_awaited_once()

    def test_no_main_function_found(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict,
    ):
        input_file_name = "input.json"
        input_json_content = """
                {
                    "message": "Hello world",
                    "repeat": 2
                }"""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # create input file
            input_file_path = os.path.join(temp_dir, input_file_name)
            with open(input_file_path, "w") as f:
                f.write(input_json_content)

            # Create test script without main function
            script_file = "entrypoint.py"
            script_file_path = os.path.join(temp_dir, script_file)
            with open(script_file_path, "w") as f:
                f.write("print(0)")

            # create uipath.json
            with open("uipath.json", "w") as f:
                import json

                json.dump(create_uipath_json(script_file), f)

            result = runner.invoke(cli, ["run", entrypoint, "{}"])
            assert result.exit_code == 1
            assert (
                "not found" in result.output.lower()
                or "missing" in result.output.lower()
            )

    def test_pydantic_model_execution(
        self,
        runner: CliRunner,
        temp_dir: str,
        entrypoint: str,
        mock_env_vars: dict,
    ):
        """Test successful execution with Pydantic models."""
        pydantic_script = """
from pydantic import BaseModel, Field


class PersonIn(BaseModel):
    name: str
    age: int
    email: str | None = None


class PersonOut(BaseModel):
    name: str
    age: int
    email: str | None = None
    is_adult: bool
    greeting: str


def main(input_data: PersonIn) -> PersonOut:
    return PersonOut(
        name=input_data.name,
        age=input_data.age,
        email=input_data.email,
        is_adult=input_data.age >= 18,
        greeting=f"Hello, {input_data.name}!"
    )
"""

        input_file_name = "input.json"
        output_file_name = "output.json"
        input_json_content = """
        {
            "name": "John Doe",
            "age": 25,
            "email": "john@example.com"
        }"""

        with runner.isolated_filesystem(temp_dir=temp_dir):
            # create input file
            input_file_path = os.path.join(temp_dir, input_file_name)
            output_file_path = os.path.join(temp_dir, output_file_name)
            with open(input_file_path, "w") as f:
                f.write(input_json_content)

            # Create test script
            script_file = "entrypoint.py"
            script_file_path = os.path.join(temp_dir, script_file)
            with open(script_file_path, "w") as f:
                f.write(pydantic_script)

            # create uipath.json
            with open("uipath.json", "w") as f:
                import json

                json.dump(create_uipath_json(script_file_path), f)

            result = runner.invoke(
                cli,
                [
                    "run",
                    "main",
                    "--input-file",
                    input_file_path,
                    "--output-file",
                    output_file_path,
                ],
            )

            assert result.exit_code == 0
            assert "Successful execution." in result.output
            assert os.path.exists(output_file_path)

            with open(output_file_path, "r") as f:
                import json

                output_data = json.load(f)
                assert output_data["name"] == "John Doe"
                assert output_data["age"] == 25
                assert output_data["email"] == "john@example.com"
                assert output_data["is_adult"] is True
                assert output_data["greeting"] == "Hello, John Doe!"


_SIMULATION_JSON = {
    "enabled": True,
    "toolsToSimulate": [{"name": "check_syntax"}, {"name": "check_style"}],
    "instructions": "Simulate.",
}


class TestRunSimulation:
    """Tests for the --simulation flag on the run command."""

    def _make_factory(self):
        factory = Mock()
        runtime = Mock()
        runtime.stream = Mock(side_effect=_empty_async_gen)
        runtime.dispose = AsyncMock()
        runtime.get_schema = AsyncMock(return_value=Mock(metadata=None))
        factory.discover_entrypoints.return_value = ["main"]
        factory.get_settings = AsyncMock(return_value=None)
        factory.dispose = AsyncMock()
        factory.new_runtime = AsyncMock(return_value=runtime)
        return factory, runtime

    def test_invalid_simulation_json_exits_with_error(
        self, runner: CliRunner, temp_dir: str
    ):
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": "main.py:main"}}, f)
            with open("main.py", "w") as f:
                f.write("async def main(input): return {}")

            result = runner.invoke(
                cli, ["run", "main", "--simulation", "{ not valid json }"]
            )
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_simulation_wraps_runtime_with_mock_runtime(
        self, runner: CliRunner, temp_dir: str
    ):
        factory, _ = self._make_factory()

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": "main.py:main"}}, f)
            with open("main.py", "w") as f:
                f.write("async def main(input): return {}")

            with (
                patch(
                    "uipath._cli.cli_run.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                    return_value=factory,
                ),
                patch(
                    "uipath._cli.cli_run.ResourceOverwritesContext",
                    side_effect=_mock_resource_overwrites_context,
                ),
                patch("uipath._cli.cli_run.UiPathMockRuntime") as mock_cls,
            ):
                mock_cls.return_value = Mock(
                    stream=Mock(side_effect=_empty_async_gen),
                    dispose=AsyncMock(),
                    get_schema=AsyncMock(return_value=Mock(metadata=None)),
                )
                runner.invoke(
                    cli,
                    ["run", "main", "--simulation", json.dumps(_SIMULATION_JSON)],
                )

        assert mock_cls.called
        assert mock_cls.call_args.kwargs["mocking_context"] is not None

    def test_simulation_disabled_does_not_wrap_runtime(
        self, runner: CliRunner, temp_dir: str
    ):
        factory, _ = self._make_factory()
        disabled = {**_SIMULATION_JSON, "enabled": False}

        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": "main.py:main"}}, f)
            with open("main.py", "w") as f:
                f.write("async def main(input): return {}")

            with (
                patch(
                    "uipath._cli.cli_run.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_run.UiPathRuntimeFactoryRegistry.get",
                    return_value=factory,
                ),
                patch(
                    "uipath._cli.cli_run.ResourceOverwritesContext",
                    side_effect=_mock_resource_overwrites_context,
                ),
                patch("uipath._cli.cli_run.UiPathMockRuntime") as mock_cls,
            ):
                runner.invoke(
                    cli, ["run", "main", "--simulation", json.dumps(disabled)]
                )

        assert not mock_cls.called
