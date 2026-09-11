import json
import os
import re
import uuid
from importlib.metadata import version
from unittest.mock import patch

from click.testing import CliRunner
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from uipath._cli import cli
from uipath._cli.middlewares import MiddlewareResult
from uipath._cli.models.agent_frameworks import AgentFramework
from uipath._cli.models.project_types import ProjectType


class TestNew:
    def test_new_project_creation(self, runner: CliRunner, temp_dir: str) -> None:
        """Test project creation scenarios."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Test creating a new project
            result = runner.invoke(cli, ["new", "my_project"])
            assert result.exit_code == 0
            assert os.path.exists("main.py")
            assert os.path.exists("pyproject.toml")

    def test_new_project_writes_uipath_json_id(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """uipath.json gets a GUID id up front so later commands don't warn."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "my_project"])
            assert result.exit_code == 0
            with open("uipath.json") as f:
                config = json.load(f)
            uuid.UUID(config["id"])
            assert config["functions"] == {"main": "main.py:main"}

    def test_new_project_without_name(self, runner: CliRunner, temp_dir: str) -> None:
        """Test creating a new project without specifying a name."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", ""])
            assert result.exit_code == 1
            assert "Please specify a name for your project" in result.output

    def test_new_project_with_existing_files(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test creating a new project when files already exist."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Create existing files
            with open("main.py", "w") as f:
                f.write("print('Existing file')")

            result = runner.invoke(cli, ["new", "my_project"])
            assert result.exit_code == 0
            assert "Created 'main.py' file." in result.output

    def test_new_project_middleware_interaction(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Test middleware integration during project creation."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                # Test middleware stopping execution with error
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=False,
                    error_message="Middleware error",
                    should_include_stacktrace=False,
                )

                result = runner.invoke(cli, ["new", "my_project"])
                assert result.exit_code == 1
                assert "Middleware error" in result.output
                assert not os.path.exists("main.py")

                # Test middleware allowing execution
                mock_middleware.return_value = MiddlewareResult(
                    should_continue=True,
                    error_message=None,
                    should_include_stacktrace=False,
                )

                result = runner.invoke(cli, ["new", "my_project"])
                assert result.exit_code == 0
                assert os.path.exists("main.py")

    def test_new_default_type_is_auto(self, runner: CliRunner, temp_dir: str) -> None:
        """Without --type, middlewares receive project_type='auto' so an
        installed agent framework can claim the scaffold; unclaimed, the
        base falls back to a function project."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks", return_value=[]
                ),
            ):
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["new", "my_project"])
                assert result.exit_code == 0
                mock_middleware.assert_called_once_with(
                    "new",
                    "my_project",
                    project_type=ProjectType.AUTO,
                    agent_framework=None,
                )
                assert os.path.exists("uipath.json")

    def test_new_explicit_type_auto_claimed_by_middleware(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type auto lets a framework middleware claim the scaffold."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[AgentFramework.LLAMAINDEX],
                ),
            ):
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "auto"])
                assert result.exit_code == 0
                mock_middleware.assert_called_once_with(
                    "new",
                    "my_agent",
                    project_type=ProjectType.AUTO,
                    agent_framework=None,
                )
                # Claimed by the middleware: no base function scaffold.
                assert not os.path.exists("uipath.json")

    def test_new_type_auto_multiple_installed_requires_explicit_choice(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Auto with several integrations installed must not pick one by
        middleware registration order — it errors before dispatch."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[AgentFramework.LANGCHAIN, AgentFramework.LLAMAINDEX],
                ),
            ):
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_agent"])
                assert result.exit_code == 1
                assert "Multiple agent frameworks are installed" in result.output
                assert "langchain, llamaindex" in result.output
                assert "--type function" in result.output
                assert not os.path.exists("main.py")
                mock_middleware.assert_not_called()

    def test_new_explicit_type_function(self, runner: CliRunner, temp_dir: str) -> None:
        """--type function scaffolds the base function project."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "my_project", "--type", "function"])
            assert result.exit_code == 0
            with open("uipath.json") as f:
                config = json.load(f)
            assert config["functions"] == {"main": "main.py:main"}

    def test_new_type_agent_single_installed_but_unclaimed_errors(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """A resolved framework nothing claims must not fall back to a function scaffold."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[AgentFramework.LANGCHAIN],
                ),
            ):
                # Installed, but its middleware did not claim the command
                # (e.g. an outdated integration).
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 1
                assert (
                    "'uipath-langchain' package is required to scaffold a "
                    "'langchain' agent" in result.output
                )
                assert "pip install uipath-langchain" in result.output
                assert "uv add uipath-langchain" in result.output
                assert not os.path.exists("main.py")
                assert not os.path.exists("uipath.json")

    def test_new_type_agent_no_integration_installed_lists_frameworks(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type agent with nothing installed lists every framework and package."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks", return_value=[]
                ),
            ):
                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 1
                assert "No agent framework integration is installed" in result.output
                for framework in AgentFramework:
                    assert framework.package in result.output
                assert not os.path.exists("main.py")
                mock_middleware.assert_not_called()

    def test_new_type_agent_uses_the_single_installed_framework(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type agent without --agent-framework picks the one installed integration."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[AgentFramework.LLAMAINDEX],
                ),
            ):
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 0
                assert "Using the installed 'llamaindex' agent framework" in (
                    result.output
                )
                mock_middleware.assert_called_once_with(
                    "new",
                    "my_agent",
                    project_type=ProjectType.AGENT,
                    agent_framework=AgentFramework.LLAMAINDEX,
                )

    def test_new_type_agent_multiple_installed_requires_explicit_choice(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Several integrations installed (langchain included) must be disambiguated."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[AgentFramework.LLAMAINDEX, AgentFramework.LANGCHAIN],
                ),
            ):
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 1
                assert "Multiple agent frameworks are installed" in result.output
                assert "langchain, llamaindex" in result.output
                mock_middleware.assert_not_called()

    def test_new_type_agent_ambiguous_installed_frameworks_error(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Several non-langchain integrations installed: ask the user to pick."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[
                        AgentFramework.LLAMAINDEX,
                        AgentFramework.PYDANTIC_AI,
                    ],
                ),
            ):
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 1
                assert "Multiple agent frameworks are installed" in result.output
                assert "llamaindex, pydantic-ai" in result.output
                assert not os.path.exists("main.py")
                mock_middleware.assert_not_called()

    def test_new_agent_framework_forwarded_to_middlewares(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """An explicit --agent-framework reaches the middleware chain unchanged."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(
                    cli,
                    [
                        "new",
                        "my_agent",
                        "--type",
                        "agent",
                        "--agent-framework",
                        "pydantic-ai",
                    ],
                )
                assert result.exit_code == 0
                mock_middleware.assert_called_once_with(
                    "new",
                    "my_agent",
                    project_type=ProjectType.AGENT,
                    agent_framework=AgentFramework.PYDANTIC_AI,
                )

    def test_new_agent_framework_not_installed_names_package(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """The error for an unhandled framework names its integration package."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(
                    cli,
                    [
                        "new",
                        "my_agent",
                        "--type",
                        "agent",
                        "--agent-framework",
                        "microsoft-agent-framework",
                    ],
                )
                assert result.exit_code == 1
                assert (
                    "'uipath-agent-framework' package is required to scaffold a "
                    "'microsoft-agent-framework' agent" in result.output
                )
                assert "uv add uipath-agent-framework" in result.output
                assert not os.path.exists("main.py")

    def test_new_agent_framework_requires_agent_type(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--agent-framework without --type agent is rejected."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            for extra_args in (
                [],  # implicit --type auto
                ["--type", "auto"],
                ["--type", "function"],
            ):
                result = runner.invoke(
                    cli,
                    ["new", "my_project", "--agent-framework", "langchain"]
                    + extra_args,
                )
                assert result.exit_code == 1
                assert (
                    "`--agent-framework` can only be used together with "
                    "`--type agent`" in result.output
                )
                assert not os.path.exists("main.py")

    def test_new_invalid_type_rejected(self, runner: CliRunner, temp_dir: str) -> None:
        """Unknown --type values are rejected by click."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "my_project", "--type", "workflow"])
            assert result.exit_code == 2
            assert not os.path.exists("main.py")

    def test_new_invalid_agent_framework_rejected(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Unknown --agent-framework values are rejected by click."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(
                cli,
                ["new", "my_agent", "--type", "agent", "--agent-framework", "crewai"],
            )
            assert result.exit_code == 2
            assert not os.path.exists("main.py")

    def test_new_project_error_handling(self, runner: CliRunner, temp_dir: str) -> None:
        """Test error handling in new command."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Mock middleware to allow execution
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                # Simulate an error during project creation
                with patch("uipath._cli.cli_new.generate_script") as mock_generate:
                    mock_generate.side_effect = Exception("Generation error")
                    result = runner.invoke(cli, ["new", "my_project"])
                    assert result.exit_code == 1
                    assert "Created 'main.py' file." not in result.output


class TestUipathScaffoldPin:
    """The scaffolded pin must admit the uipath release it ships with."""

    def test_scaffold_pin_admits_installed_uipath(self) -> None:
        """Guard: fails on every minor bump so the scaffold gets reviewed.

        When this fails, review the scaffold in ``cli_new.py`` (pin constant,
        ``main.py`` template, post-scaffold hints) for the new minor, then bump
        ``UIPATH_SCAFFOLD_MINOR``.
        """
        from uipath._cli.cli_new import UIPATH_SCAFFOLD_MINOR

        installed = Version(version("uipath"))
        installed_minor = f"{installed.major}.{installed.minor}"
        assert UIPATH_SCAFFOLD_MINOR == installed_minor, (
            f"uipath minor changed to {installed_minor} but UIPATH_SCAFFOLD_MINOR is "
            f"{UIPATH_SCAFFOLD_MINOR}; review the scaffold in cli_new.py (pin, "
            f"template, hints) and bump the constant"
        )

    def test_scaffolded_pin_contains_installed_uipath(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Regression guard: runs against the real installed package, not a mock.

        A stale range would make ``uv sync`` downgrade the project's venv right
        after ``uipath new``.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "demo"])
            assert result.exit_code == 0
            with open("pyproject.toml") as f:
                content = f.read()
            match = re.search(r'"uipath([^"]*)"', content)
            assert match is not None, content
            pin = SpecifierSet(match.group(1))
            installed = version("uipath")
            assert pin.contains(installed, prereleases=True), (
                f"scaffolded pin '{pin}' does not contain installed uipath {installed}"
            )


class TestClaimsScaffold:
    """The gate every framework integration shares."""

    def test_auto_is_claimed_by_any_framework(self) -> None:
        """`--type auto`: whichever integration is installed wins."""
        for framework in AgentFramework:
            assert framework.claims_scaffold(ProjectType.AUTO, None) is True

    def test_function_is_never_claimed(self) -> None:
        """Regression guard for #1543: a function scaffold stays a function."""
        for framework in AgentFramework:
            assert framework.claims_scaffold(ProjectType.FUNCTION, None) is False
            assert framework.claims_scaffold(ProjectType.FUNCTION, framework) is False

    def test_agent_is_claimed_only_by_the_named_framework(self) -> None:
        for framework in AgentFramework:
            assert framework.claims_scaffold(ProjectType.AGENT, framework) is True
            others = (other for other in AgentFramework if other is not framework)
            for other in others:
                assert framework.claims_scaffold(ProjectType.AGENT, other) is False

    def test_agent_without_a_framework_is_not_claimed(self) -> None:
        """The CLI resolves the framework first; an unset one claims nothing."""
        for framework in AgentFramework:
            assert framework.claims_scaffold(ProjectType.AGENT, None) is False

    def test_plain_strings_gate_the_same_way(self) -> None:
        """Older callers pass raw strings; StrEnum equality covers them."""
        langchain = AgentFramework.LANGCHAIN
        assert langchain.claims_scaffold("auto", None) is True
        assert langchain.claims_scaffold("agent", "langchain") is True
        assert langchain.claims_scaffold("agent", "pydantic-ai") is False
        assert langchain.claims_scaffold("function", None) is False
