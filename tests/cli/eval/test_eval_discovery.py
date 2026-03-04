"""Tests for eval CLI auto-discovery of entrypoints and eval sets."""

import json
import os
from unittest.mock import AsyncMock, Mock, patch

from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult


def _middleware_continue():
    return MiddlewareResult(
        should_continue=True,
        error_message=None,
        should_include_stacktrace=False,
    )


def _make_mock_factory(entrypoints: list[str]):
    """Create a mock runtime factory with given entrypoints."""
    mock_factory = Mock()
    mock_factory.discover_entrypoints.return_value = entrypoints
    mock_factory.get_settings = AsyncMock(return_value=None)
    mock_factory.dispose = AsyncMock()

    mock_runtime = Mock()
    mock_runtime.get_schema = AsyncMock(
        return_value=Mock(metadata=None, input_schema=None, output_schema=None)
    )
    mock_runtime.dispose = AsyncMock()
    mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

    return mock_factory


class TestEvalDiscoveryMultipleEntrypoints:
    """Tests for when multiple entrypoints exist and none is specified."""

    def test_multiple_entrypoints_shows_usage_help(
        self, runner: CliRunner, temp_dir: str
    ):
        """When multiple entrypoints exist, show available entrypoints and eval sets."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create uipath.json with multiple functions
            uipath_config = {
                "functions": {
                    "agent_a": "src/agent_a.py:main",
                    "agent_b": "src/agent_b.py:main",
                }
            }
            with open("uipath.json", "w") as f:
                json.dump(uipath_config, f)

            # Create eval sets directory with one eval set
            os.makedirs("evaluations/eval-sets", exist_ok=True)
            eval_set = {
                "version": 1.0,
                "id": "test-set",
                "name": "Test Set",
                "evaluatorRefs": [],
                "evaluations": [],
            }
            with open("evaluations/eval-sets/test-set.json", "w") as f:
                json.dump(eval_set, f)

            mock_factory = _make_mock_factory(["agent_a", "agent_b"])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code == 0
            assert "Available entrypoints:" in result.output
            assert "agent_a" in result.output
            assert "agent_b" in result.output
            assert "Available eval sets:" in result.output
            assert "evaluations" in result.output and "test-set.json" in result.output
            assert "Usage: uipath eval <entrypoint> <eval_set>" in result.output
            assert "Example:" in result.output

    def test_multiple_entrypoints_no_eval_sets(self, runner: CliRunner, temp_dir: str):
        """When multiple entrypoints exist and no eval sets, show both sections."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"a": "a.py:main", "b": "b.py:main"}}, f)

            mock_factory = _make_mock_factory(["a", "b"])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code == 0
            assert "Available entrypoints:" in result.output
            assert "a" in result.output
            assert "b" in result.output
            assert "No eval sets found" in result.output


class TestEvalDiscoveryMultipleEvalSets:
    """Tests for when multiple eval sets exist and none is specified."""

    def test_multiple_eval_sets_shows_usage_help(
        self, runner: CliRunner, temp_dir: str
    ):
        """When one entrypoint but multiple eval sets, show available eval sets."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"my_agent": "src/main.py:main"}}, f)

            # Create two eval sets
            os.makedirs("evaluations/eval-sets", exist_ok=True)
            for name in ["set-a.json", "set-b.json"]:
                eval_set = {
                    "version": 1.0,
                    "id": name,
                    "name": name,
                    "evaluatorRefs": [],
                    "evaluations": [],
                }
                with open(f"evaluations/eval-sets/{name}", "w") as f:
                    json.dump(eval_set, f)

            mock_factory = _make_mock_factory(["my_agent"])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code == 0
            assert "Available entrypoints:" in result.output
            assert "my_agent" in result.output
            assert "Available eval sets:" in result.output
            assert "set-a.json" in result.output
            assert "set-b.json" in result.output
            assert "Usage: uipath eval <entrypoint> <eval_set>" in result.output
            assert "Example: uipath eval my_agent" in result.output

    def test_eval_sets_show_full_relative_path(self, runner: CliRunner, temp_dir: str):
        """Eval sets in the help message should show the full relative path."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"agent": "main.py:main"}}, f)

            os.makedirs("evaluations/eval-sets", exist_ok=True)
            for name in ["alpha.json", "beta.json"]:
                with open(f"evaluations/eval-sets/{name}", "w") as f:
                    json.dump(
                        {
                            "version": 1.0,
                            "id": name,
                            "name": name,
                            "evaluatorRefs": [],
                            "evaluations": [],
                        },
                        f,
                    )

            mock_factory = _make_mock_factory(["agent"])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                result = runner.invoke(cli, ["eval"])

            # Should contain full relative paths, not just filenames
            output = result.output.replace("\\", "/")
            assert "evaluations/eval-sets/alpha.json" in output
            assert "evaluations/eval-sets/beta.json" in output


class TestEvalDiscoverySingleEntrypointAndEvalSet:
    """Tests for auto-discovery when exactly one entrypoint and one eval set exist."""

    def test_single_entrypoint_and_eval_set_does_not_show_help(
        self, runner: CliRunner, temp_dir: str
    ):
        """When exactly one entrypoint and one eval set, discovery succeeds (no help shown)."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with open("uipath.json", "w") as f:
                json.dump({"functions": {"my_agent": "main.py:main"}}, f)

            os.makedirs("evaluations/eval-sets", exist_ok=True)
            eval_set = {
                "version": 1.0,
                "id": "test-set",
                "name": "Test Set",
                "evaluatorRefs": [],
                "evaluations": [],
            }
            with open("evaluations/eval-sets/test-set.json", "w") as f:
                json.dump(eval_set, f)

            mock_factory = _make_mock_factory(["my_agent"])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                result = runner.invoke(cli, ["eval"])

            # Should NOT show usage help (discovery succeeded)
            assert "Available entrypoints:" not in result.output
            assert "Usage: uipath eval" not in result.output


class TestEvalDiscoveryNoEntrypoints:
    """Tests for when no entrypoints are found."""

    def test_no_entrypoints_shows_helpful_message(
        self, runner: CliRunner, temp_dir: str
    ):
        """When no entrypoints found, show a helpful message."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs("evaluations/eval-sets", exist_ok=True)
            with open("evaluations/eval-sets/test.json", "w") as f:
                json.dump(
                    {
                        "version": 1.0,
                        "id": "t",
                        "name": "t",
                        "evaluatorRefs": [],
                        "evaluations": [],
                    },
                    f,
                )

            mock_factory = _make_mock_factory([])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                result = runner.invoke(cli, ["eval"])

            assert result.exit_code == 0
            assert "No entrypoints found" in result.output
            assert "Usage: uipath eval <entrypoint> <eval_set>" in result.output


class TestEvalDiscoveryExplicitArgs:
    """Tests for when entrypoint and/or eval set are explicitly provided."""

    def test_explicit_entrypoint_skips_entrypoint_discovery(
        self, runner: CliRunner, temp_dir: str
    ):
        """When entrypoint is provided, skip entrypoint discovery but still discover eval sets."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs("evaluations/eval-sets", exist_ok=True)
            for name in ["set-a.json", "set-b.json"]:
                with open(f"evaluations/eval-sets/{name}", "w") as f:
                    json.dump(
                        {
                            "version": 1.0,
                            "id": name,
                            "name": name,
                            "evaluatorRefs": [],
                            "evaluations": [],
                        },
                        f,
                    )

            mock_factory = _make_mock_factory(["agent_a", "agent_b"])

            with (
                patch(
                    "uipath._cli.cli_eval.Middlewares.next",
                    return_value=_middleware_continue(),
                ),
                patch(
                    "uipath._cli.cli_eval.UiPathRuntimeFactoryRegistry.get",
                    return_value=mock_factory,
                ),
                patch(
                    "uipath._cli.cli_eval.setup_reporting_prereq",
                    return_value=False,
                ),
            ):
                # Pass entrypoint explicitly, but no eval set
                result = runner.invoke(cli, ["eval", "agent_a"])

            # Should still show usage help because multiple eval sets
            assert result.exit_code == 0
            assert "Available eval sets:" in result.output
            assert "set-a.json" in result.output
            assert "set-b.json" in result.output
