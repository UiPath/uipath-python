"""Tests for debug command tool simulation functionality."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli._evals.mocks.mocks import (
    clear_execution_context,
    is_tool_simulated,
)
from uipath._cli._evals.mocks.types import (
    LLMMockingStrategy,
    MockingContext,
    MockingStrategyType,
    ToolSimulation,
)
from uipath._cli.cli_debug import load_simulation_config
from uipath._cli.middlewares import MiddlewareResult


@pytest.fixture
def valid_simulation_config() -> dict[str, Any]:
    """Create a valid simulation.json configuration."""
    return {
        "instructions": "Always give a negative outlook on stock prospects",
        "inputGenerationInstructions": "",
        "simulateInput": False,
        "enabled": True,
        "toolsToSimulate": [
            {"name": "Web Reader"},
            {"name": "Web Search"},
            {"name": "Web Summary"},
        ],
    }


@pytest.fixture
def disabled_simulation_config() -> dict[str, Any]:
    """Create a disabled simulation.json configuration."""
    return {
        "instructions": "Test instructions",
        "enabled": False,
        "toolsToSimulate": [{"name": "Test Tool"}],
    }


@pytest.fixture
def empty_tools_simulation_config() -> dict[str, Any]:
    """Create simulation config with no tools."""
    return {
        "instructions": "Test instructions",
        "enabled": True,
        "toolsToSimulate": [],
    }


class TestLoadSimulationConfig:
    """Tests for the load_simulation_config function."""

    def test_returns_none_when_file_does_not_exist(self, temp_dir: str):
        """Test that None is returned when simulation.json doesn't exist."""
        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()
            assert result is None

    def test_loads_valid_simulation_config(
        self, temp_dir: str, valid_simulation_config: dict[str, Any]
    ):
        """Test loading a valid simulation configuration."""
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(valid_simulation_config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()

            assert result is not None
            assert isinstance(result, MockingContext)
            assert result.name == "debug-simulation"
            assert result.strategy is not None
            assert isinstance(result.strategy, LLMMockingStrategy)
            assert result.strategy.prompt == valid_simulation_config["instructions"]
            assert len(result.strategy.tools_to_simulate) == 3
            assert result.strategy.tools_to_simulate[0].name == "Web Reader"

    def test_returns_none_when_disabled(
        self, temp_dir: str, disabled_simulation_config: dict[str, Any]
    ):
        """Test that None is returned when simulation is disabled."""
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(disabled_simulation_config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()
            assert result is None

    def test_returns_none_when_no_tools_to_simulate(
        self, temp_dir: str, empty_tools_simulation_config: dict[str, Any]
    ):
        """Test that None is returned when toolsToSimulate is empty."""
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(empty_tools_simulation_config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()
            assert result is None

    def test_handles_malformed_json(self, temp_dir: str):
        """Test that malformed JSON is handled gracefully."""
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()
            assert result is None

    def test_handles_missing_required_fields(self, temp_dir: str):
        """Test that missing required fields are handled gracefully."""
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump({"enabled": True}, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()
            # Should return None because toolsToSimulate is missing/empty
            assert result is None

    def test_creates_mocking_context_with_empty_inputs(
        self, temp_dir: str, valid_simulation_config: dict[str, Any]
    ):
        """Test that MockingContext is created with empty inputs."""
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(valid_simulation_config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()

            assert result is not None
            assert result.inputs == {}

    def test_uses_default_empty_instructions_when_missing(self, temp_dir: str):
        """Test that empty string is used when instructions field is missing."""
        config = {
            "enabled": True,
            "toolsToSimulate": [{"name": "Test Tool"}],
        }
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()

            assert result is not None
            assert isinstance(result.strategy, LLMMockingStrategy)
            assert result.strategy.prompt == ""


class TestDebugCommandSimulationIntegration:
    """Integration tests for debug command with simulation."""

    @pytest.fixture
    def mock_runtime(self):
        """Create a mock runtime for testing."""
        runtime = Mock()
        runtime.execute = Mock(return_value=Mock(status="SUCCESSFUL", output={}))
        runtime.dispose = Mock()
        return runtime

    @pytest.fixture
    def mock_factory(self, mock_runtime):
        """Create a mock factory that returns mock runtime."""
        factory = Mock()
        factory.new_runtime = Mock(return_value=mock_runtime)
        factory.dispose = Mock()
        return factory

    def test_debug_without_simulation_file(self, runner: CliRunner, temp_dir: str):
        """Test debug command when simulation.json doesn't exist."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            script_file = "entrypoint.py"
            with open(script_file, "w") as f:
                f.write("def main(input): return {'result': 'success'}")

            # Create uipath.json
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": f"{script_file}:main"}}, f)

            with patch("uipath._cli.cli_debug.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=False,
                    info_message="Execution succeeded",
                    error_message=None,
                    should_include_stacktrace=False,
                )
                result = runner.invoke(cli, ["debug", "main", "{}"])
                assert result.exit_code == 0

    def test_debug_with_simulation_file_sets_context(
        self, runner: CliRunner, temp_dir: str, valid_simulation_config: dict[str, Any]
    ):
        """Test that debug command sets execution context when simulation.json exists."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            script_file = "entrypoint.py"
            with open(script_file, "w") as f:
                f.write(
                    """
from uipath.eval.mocks import mockable

@mockable(name="Web Reader")
def web_reader(url: str) -> str:
    return "Original content"

def main(input):
    return {'result': web_reader('https://test.com')}
"""
                )

            # Create uipath.json
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": f"{script_file}:main"}}, f)

            # Create a MockingContext to return from load_simulation_config
            mocking_strategy = LLMMockingStrategy(
                type=MockingStrategyType.LLM,
                prompt=valid_simulation_config["instructions"],
                tools_to_simulate=[
                    ToolSimulation(name=tool["name"])
                    for tool in valid_simulation_config["toolsToSimulate"]
                ],
            )
            mock_mocking_context = MockingContext(
                strategy=mocking_strategy,
                name="debug-simulation",
                inputs={},
            )

            # Track if set_execution_context was called
            with patch(
                "uipath._cli.cli_debug.set_execution_context"
            ) as mock_set_context:
                with patch(
                    "uipath._cli.cli_debug.clear_execution_context"
                ) as mock_clear_context:
                    # Mock load_simulation_config to return the MockingContext
                    with patch(
                        "uipath._cli.cli_debug.load_simulation_config"
                    ) as mock_load_config:
                        mock_load_config.return_value = mock_mocking_context

                        with patch(
                            "uipath._cli.cli_debug.Middlewares.next"
                        ) as mock_middleware:
                            # Set should_continue=True so the debug execution logic runs
                            mock_middleware.return_value = MiddlewareResult(
                                should_continue=True,
                                info_message=None,
                                error_message=None,
                                should_include_stacktrace=False,
                            )

                            # Mock the runtime factory and execution
                            with patch(
                                "uipath._cli.cli_debug.UiPathRuntimeFactoryRegistry.get"
                            ) as mock_factory_get:
                                mock_runtime = Mock()
                                mock_runtime.execute = Mock(
                                    return_value=Mock(status="SUCCESSFUL", output={})
                                )
                                mock_runtime.dispose = Mock()

                                mock_factory = Mock()
                                mock_factory.new_runtime = Mock(
                                    return_value=mock_runtime
                                )
                                mock_factory.dispose = Mock()
                                mock_factory_get.return_value = mock_factory

                                # Mock debug bridge to avoid SignalR/console issues
                                with patch("uipath._cli.cli_debug.get_debug_bridge"):
                                    with patch(
                                        "uipath._cli.cli_debug.UiPathDebugRuntime"
                                    ) as mock_debug_runtime_class:
                                        mock_debug_runtime = Mock()
                                        mock_debug_runtime.execute = Mock(
                                            return_value=Mock(
                                                status="SUCCESSFUL", output={}
                                            )
                                        )
                                        mock_debug_runtime.dispose = Mock()
                                        mock_debug_runtime_class.return_value = (
                                            mock_debug_runtime
                                        )

                                        runner.invoke(cli, ["debug", "main", "{}"])

                                        # Verify set_execution_context was called
                                        assert mock_set_context.called
                                        # Verify the MockingContext passed has the right structure
                                        call_args = mock_set_context.call_args
                                        mocking_ctx = call_args[0][0]
                                        assert isinstance(mocking_ctx, MockingContext)
                                        assert mocking_ctx.strategy is not None
                                        assert isinstance(
                                            mocking_ctx.strategy, LLMMockingStrategy
                                        )
                                        assert (
                                            len(mocking_ctx.strategy.tools_to_simulate)
                                            == 3
                                        )

                                        # Verify clear_execution_context was called in finally block
                                        assert mock_clear_context.called

    def test_debug_clears_context_on_error(
        self, runner: CliRunner, temp_dir: str, valid_simulation_config: dict[str, Any]
    ):
        """Test that execution context is cleared even when an error occurs."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create simulation.json
            with open("simulation.json", "w") as f:
                json.dump(valid_simulation_config, f)

            script_file = "entrypoint.py"
            with open(script_file, "w") as f:
                f.write("def main(input): raise Exception('Test error')")

            # Create uipath.json
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": f"{script_file}:main"}}, f)

            # Create a MockingContext to return from load_simulation_config
            mocking_strategy = LLMMockingStrategy(
                type=MockingStrategyType.LLM,
                prompt="Test instructions",
                tools_to_simulate=[ToolSimulation(name="Test Tool")],
            )
            mock_mocking_context = MockingContext(
                strategy=mocking_strategy,
                name="test-simulation",
                inputs={},
            )

            with patch(
                "uipath._cli.cli_debug.clear_execution_context"
            ) as mock_clear_context:
                with patch(
                    "uipath._cli.cli_debug.load_simulation_config"
                ) as mock_load_config:
                    # Mock load_simulation_config to return a MockingContext
                    mock_load_config.return_value = mock_mocking_context

                    with patch(
                        "uipath._cli.cli_debug.Middlewares.next"
                    ) as mock_middleware:
                        mock_middleware.return_value = MiddlewareResult(
                            should_continue=True,
                            info_message=None,
                            error_message=None,
                            should_include_stacktrace=False,
                        )

                        # Mock the runtime factory and execution to simulate an error
                        with patch(
                            "uipath._cli.cli_debug.UiPathRuntimeFactoryRegistry.get"
                        ) as mock_factory_get:
                            mock_runtime = Mock()
                            # Make execute raise an exception to simulate an error
                            mock_runtime.execute = Mock(
                                side_effect=Exception("Test error during execution")
                            )
                            mock_runtime.dispose = Mock()

                            mock_factory = Mock()
                            mock_factory.new_runtime = Mock(return_value=mock_runtime)
                            mock_factory.dispose = Mock()
                            mock_factory_get.return_value = mock_factory

                            # Mock debug bridge to avoid SignalR/console issues
                            with patch("uipath._cli.cli_debug.get_debug_bridge"):
                                with patch(
                                    "uipath._cli.cli_debug.UiPathDebugRuntime"
                                ) as mock_debug_runtime_class:
                                    mock_debug_runtime = Mock()
                                    # Make the debug runtime raise an exception
                                    mock_debug_runtime.execute = Mock(
                                        side_effect=Exception("Test error")
                                    )
                                    mock_debug_runtime.dispose = Mock()
                                    mock_debug_runtime_class.return_value = (
                                        mock_debug_runtime
                                    )

                                    # This will raise an exception during execution
                                    runner.invoke(cli, ["debug", "main", "{}"])

                                    # Verify clear_execution_context was still called
                                    assert mock_clear_context.called

    def test_simulation_config_enables_tool_mocking(
        self, temp_dir: str, valid_simulation_config: dict[str, Any]
    ):
        """Test that tools marked in simulation config are detected as simulated."""
        # Clear any existing context
        clear_execution_context()

        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(valid_simulation_config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            mocking_ctx = load_simulation_config()
            assert mocking_ctx is not None

            # Manually set context (simulating what debug command does)
            from uipath._cli._evals._span_collection import ExecutionSpanCollector

            span_collector = ExecutionSpanCollector()
            from uipath._cli._evals.mocks.mocks import set_execution_context

            set_execution_context(mocking_ctx, span_collector, "test-execution-id")

            # Verify tools are detected as simulated
            assert is_tool_simulated("Web Reader") is True
            assert is_tool_simulated("Web Search") is True
            assert is_tool_simulated("Web Summary") is True
            assert is_tool_simulated("Non Simulated Tool") is False

            # Clean up
            clear_execution_context()

    def test_disabled_simulation_does_not_set_context(
        self,
        runner: CliRunner,
        temp_dir: str,
        disabled_simulation_config: dict[str, Any],
    ):
        """Test that disabled simulation doesn't set execution context."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create disabled simulation.json
            with open("simulation.json", "w") as f:
                json.dump(disabled_simulation_config, f)

            script_file = "entrypoint.py"
            with open(script_file, "w") as f:
                f.write("def main(input): return {'result': 'success'}")

            # Create uipath.json
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"main": f"{script_file}:main"}}, f)

            with patch(
                "uipath._cli.cli_debug.set_execution_context"
            ) as mock_set_context:
                with patch("uipath._cli.cli_debug.Middlewares.next") as mock_middleware:
                    mock_middleware.return_value = MiddlewareResult(
                        should_continue=False,
                        info_message="Execution succeeded",
                        error_message=None,
                        should_include_stacktrace=False,
                    )

                    runner.invoke(cli, ["debug", "main", "{}"])

                    # Verify set_execution_context was NOT called
                    assert not mock_set_context.called


class TestSimulationConfigFields:
    """Test various field combinations in simulation.json."""

    def test_enabled_defaults_to_true_when_missing(self, temp_dir: str):
        """Test that 'enabled' defaults to true when not specified."""
        config = {
            "instructions": "Test",
            "toolsToSimulate": [{"name": "Test Tool"}],
        }
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            result = load_simulation_config()
            # Should load successfully since enabled defaults to true
            assert result is not None

    def test_handles_tool_name_normalization(self, temp_dir: str):
        """Test that tool names with underscores work correctly."""
        config = {
            "enabled": True,
            "instructions": "Test",
            "toolsToSimulate": [
                {"name": "Web_Reader"},
                {"name": "Web Search"},
            ],
        }
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            mocking_ctx = load_simulation_config()
            assert mocking_ctx is not None

            # Set context to test name normalization
            from uipath._cli._evals._span_collection import ExecutionSpanCollector
            from uipath._cli._evals.mocks.mocks import set_execution_context

            span_collector = ExecutionSpanCollector()
            set_execution_context(mocking_ctx, span_collector, "test-id")

            # Both underscore and space versions should be detected
            assert is_tool_simulated("Web_Reader") is True
            assert is_tool_simulated("Web Reader") is True
            assert is_tool_simulated("Web Search") is True

            clear_execution_context()

    def test_handles_tool_name_case_insensitive(self, temp_dir: str):
        """Test that tool name comparison is case-insensitive."""
        config = {
            "enabled": True,
            "instructions": "Test",
            "toolsToSimulate": [
                {"name": "Web Reader"},
                {"name": "Web Search"},
            ],
        }
        simulation_path = Path(temp_dir) / "simulation.json"
        with open(simulation_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        with patch("uipath._cli.cli_debug.Path.cwd", return_value=Path(temp_dir)):
            mocking_ctx = load_simulation_config()
            assert mocking_ctx is not None

            from uipath._cli._evals._span_collection import ExecutionSpanCollector
            from uipath._cli._evals.mocks.mocks import set_execution_context

            span_collector = ExecutionSpanCollector()
            set_execution_context(mocking_ctx, span_collector, "test-id")

            # Case-insensitive matching should work
            assert is_tool_simulated("web reader") is True
            assert is_tool_simulated("WEB READER") is True
            assert is_tool_simulated("Web reader") is True
            assert is_tool_simulated("web search") is True
            assert is_tool_simulated("WEB SEARCH") is True
            assert is_tool_simulated("Non Existent Tool") is False

            clear_execution_context()
