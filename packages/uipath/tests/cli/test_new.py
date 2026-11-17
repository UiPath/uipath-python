import json
import os
import re
import uuid
from importlib.metadata import version
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from uipath._cli import cli
from uipath._cli._utils._constants import AGENT_FRAMEWORKS_DOCS_URL
from uipath._cli.cli_new import installed_agent_frameworks
from uipath._cli.middlewares import MiddlewareResult
from uipath._cli.models.agent_frameworks import AgentFramework


def _framework(package: str) -> AgentFramework:
    """An installed agent framework whose scaffold claims the project."""
    return AgentFramework(
        package=package,
        scaffold=MagicMock(return_value=MiddlewareResult(should_continue=False)),
    )


def _scaffold_of(framework: AgentFramework) -> MagicMock:
    """The mock behind a `_framework()` scaffold, to assert calls on."""
    return cast(MagicMock, framework.scaffold)


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

    def test_new_dir_scaffolds_into_that_directory(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--dir creates the directory and writes the project there, not in cwd."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(
                cli, ["new", "my_project", "--dir", "my_project", "--type", "function"]
            )
            assert result.exit_code == 0, result.output
            for file in ("main.py", "pyproject.toml", "uipath.json"):
                assert os.path.exists(os.path.join("my_project", file))
                assert not os.path.exists(file)
            with open(os.path.join("my_project", "pyproject.toml")) as f:
                assert 'name = "my_project"' in f.read()
            # The hints point into the directory the project landed in.
            assert "Creating new project my_project in 'my_project'" in result.output
            assert "cd my_project && uipath init" in result.output

    def test_new_dir_creates_nested_directories(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """A --dir several levels deep is created whole, like `mkdir -p`."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(
                cli, ["new", "demo", "--dir", os.path.join("a", "b", "demo")]
            )
            assert result.exit_code == 0, result.output
            assert os.path.exists(os.path.join("a", "b", "demo", "uipath.json"))

    def test_new_dir_accepts_an_existing_directory(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """An existing --dir is scaffolded into, matching the in-place overwrite."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            os.makedirs("existing")
            with open(os.path.join("existing", "notes.txt"), "w") as f:
                f.write("keep me")

            result = runner.invoke(cli, ["new", "demo", "--dir", "existing"])
            assert result.exit_code == 0, result.output
            assert os.path.exists(os.path.join("existing", "main.py"))
            assert os.path.exists(os.path.join("existing", "notes.txt"))

    def test_new_dir_is_the_cwd_while_agent_frameworks_scaffold(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Agent frameworks scaffold into cwd, so --dir becomes cwd for them.

        The frameworks live in their own packages and know nothing about
        `--dir`; the base CLI switches into the directory around the chain
        and switches back afterwards.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            outer = os.getcwd()
            seen: list[str] = []

            def scaffold(*_args: object, **_kwargs: object) -> MiddlewareResult:
                seen.append(os.getcwd())
                with open("langgraph.json", "w") as f:
                    f.write("{}")
                return MiddlewareResult(should_continue=False)

            with patch(
                "uipath._cli.cli_new.Middlewares.next", side_effect=scaffold
            ) as mock_middleware:
                result = runner.invoke(cli, ["new", "my_agent", "--dir", "my_agent"])
                assert result.exit_code == 0, result.output
                # Still the name alone: the frameworks are not told about --dir.
                mock_middleware.assert_called_once_with("new", "my_agent")

            assert seen == [os.path.join(outer, "my_agent")]
            assert os.getcwd() == outer
            assert os.path.exists(os.path.join("my_agent", "langgraph.json"))
            assert not os.path.exists("langgraph.json")

    def test_new_dir_cwd_is_restored_when_a_framework_fails(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """A framework error inside --dir must not leave the process moved."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            outer = os.getcwd()
            with patch(
                "uipath._cli.cli_new.Middlewares.next",
                side_effect=RuntimeError("scaffold exploded"),
            ):
                result = runner.invoke(cli, ["new", "my_agent", "--dir", "my_agent"])
                assert result.exit_code != 0
            assert os.getcwd() == outer

    def test_new_dir_with_the_chosen_agent_framework(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--agent-framework dispatch also runs inside --dir."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            outer = os.getcwd()
            seen: list[str] = []

            def scaffold(_name: str) -> MiddlewareResult:
                seen.append(os.getcwd())
                return MiddlewareResult(should_continue=False)

            framework = AgentFramework(
                package="uipath-langchain", scaffold=MagicMock(side_effect=scaffold)
            )
            with patch(
                "uipath._cli.cli_new.installed_agent_frameworks",
                return_value=[framework],
            ):
                result = runner.invoke(
                    cli,
                    [
                        "new",
                        "my_agent",
                        "--dir",
                        "agents/my_agent",
                        "--type",
                        "agent",
                        "--agent-framework",
                        "uipath-langchain",
                    ],
                )
                assert result.exit_code == 0, result.output
            assert seen == [os.path.join(outer, "agents", "my_agent")]
            assert os.getcwd() == outer

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

    def test_new_default_type_consults_the_agent_frameworks(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Without --type, an installed agent framework gets first refusal.

        The chain is called with the project name only: the base CLI decides
        whether frameworks are consulted at all, so they need to know nothing
        about project types.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["new", "my_project"])
                assert result.exit_code == 0
                mock_middleware.assert_called_once_with("new", "my_project")
                # Nothing claimed it, so the base function scaffold runs.
                assert os.path.exists("uipath.json")

    def test_new_type_auto_claimed_by_a_framework(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type auto lets an agent framework claim the scaffold."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "auto"])
                assert result.exit_code == 0
                mock_middleware.assert_called_once_with("new", "my_agent")
                # Claimed by a framework: no base function scaffold.
                assert not os.path.exists("uipath.json")

    def test_new_type_function_never_consults_agent_frameworks(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type function must always produce a function project.

        The middleware chain is skipped entirely, so an installed agent
        framework cannot intercept the scaffold no matter what it claims.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_project", "--type", "function"])
                assert result.exit_code == 0
                mock_middleware.assert_not_called()
                with open("uipath.json") as f:
                    config = json.load(f)
                assert config["functions"] == {"main": "main.py:main"}

    def test_new_type_agent_scaffolds_through_the_framework(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type agent with a framework installed hands over to it."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=False)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 0
                mock_middleware.assert_called_once_with("new", "my_agent")
                assert not os.path.exists("uipath.json")

    def test_new_type_agent_without_a_framework_errors(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--type agent is a guarantee: never silently a function project."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware:
                mock_middleware.return_value = MiddlewareResult(should_continue=True)

                result = runner.invoke(cli, ["new", "my_agent", "--type", "agent"])
                assert result.exit_code == 1
                assert "No agent framework is installed" in result.output
                assert AGENT_FRAMEWORKS_DOCS_URL in result.output
                assert "--type function" in result.output
                assert not os.path.exists("main.py")
                assert not os.path.exists("uipath.json")

    def test_new_multiple_frameworks_warn_and_use_the_first_discovered(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Several frameworks installed: warn, then scaffold with the first.

        Erroring here would break environments that scaffolded fine before
        `--type` existed, so the old behaviour stays the default and the
        warning points at `--agent-framework` for choosing explicitly.
        """
        with runner.isolated_filesystem(temp_dir=temp_dir):
            for extra_args in ([], ["--type", "auto"], ["--type", "agent"]):
                first = _framework("uipath-llamaindex")
                other = _framework("uipath-langchain")
                with (
                    patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                    patch(
                        "uipath._cli.cli_new.installed_agent_frameworks",
                        return_value=[first, other],
                    ),
                ):
                    result = runner.invoke(cli, ["new", "my_agent"] + extra_args)
                    assert result.exit_code == 0
                    assert "Multiple agent frameworks are installed" in result.output
                    # listed in discovery order, so the first named is the pick
                    assert "uipath-llamaindex, uipath-langchain" in result.output
                    assert "first one discovered: 'uipath-llamaindex'" in result.output
                    assert "--agent-framework" in result.output
                    _scaffold_of(first).assert_called_once_with("my_agent")
                    _scaffold_of(other).assert_not_called()
                    mock_middleware.assert_not_called()
                    # claimed by the framework: no base function scaffold
                    assert not os.path.exists("uipath.json")

    def test_agent_framework_scaffolds_with_the_chosen_one_only(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """--agent-framework dispatches to that framework and nothing else."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            chosen = _framework("uipath-llamaindex")
            other = _framework("uipath-langchain")
            with (
                patch("uipath._cli.cli_new.Middlewares.next") as mock_middleware,
                patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[other, chosen],
                ),
            ):
                result = runner.invoke(
                    cli,
                    [
                        "new",
                        "my_agent",
                        "--type",
                        "agent",
                        "--agent-framework",
                        "uipath-llamaindex",
                    ],
                )
                assert result.exit_code == 0
                _scaffold_of(chosen).assert_called_once_with("my_agent")
                _scaffold_of(other).assert_not_called()
                # The chain would have let the first registered one claim it.
                mock_middleware.assert_not_called()
                assert not os.path.exists("uipath.json")

    def test_agent_framework_takes_the_package_name_only(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """One spelling: the package, exactly as the error messages list it."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            chosen = _framework("uipath-langchain")
            for requested, expected_exit in (("uipath-langchain", 0), ("langchain", 1)):
                with patch(
                    "uipath._cli.cli_new.installed_agent_frameworks",
                    return_value=[chosen, _framework("uipath-llamaindex")],
                ):
                    result = runner.invoke(
                        cli,
                        [
                            "new",
                            "my_agent",
                            "--type",
                            "agent",
                            "--agent-framework",
                            requested,
                        ],
                    )
                    assert result.exit_code == expected_exit
            _scaffold_of(chosen).assert_called_once_with("my_agent")

    def test_agent_framework_not_installed_errors(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Asking for a framework that isn't installed names the ones that are."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            installed = _framework("uipath-langchain")
            with patch(
                "uipath._cli.cli_new.installed_agent_frameworks",
                return_value=[installed],
            ):
                result = runner.invoke(
                    cli,
                    [
                        "new",
                        "my_agent",
                        "--type",
                        "agent",
                        "--agent-framework",
                        "uipath-crewai",
                    ],
                )
                assert result.exit_code == 1
                assert (
                    "No installed agent framework matches 'uipath-crewai'"
                    in result.output
                )
                assert "Installed: uipath-langchain." in result.output
                assert AGENT_FRAMEWORKS_DOCS_URL in result.output
                _scaffold_of(installed).assert_not_called()
                assert not os.path.exists("main.py")

    def test_agent_framework_with_none_installed_errors(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            with patch(
                "uipath._cli.cli_new.installed_agent_frameworks", return_value=[]
            ):
                result = runner.invoke(
                    cli,
                    [
                        "new",
                        "my_agent",
                        "--type",
                        "agent",
                        "--agent-framework",
                        "uipath-langchain",
                    ],
                )
                assert result.exit_code == 1
                assert "No agent framework is installed." in result.output
                assert not os.path.exists("main.py")

    def test_agent_framework_requires_type_agent(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """The flag names an agent framework, so it only makes sense for agents."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            for extra_args in ([], ["--type", "auto"], ["--type", "function"]):
                result = runner.invoke(
                    cli,
                    ["new", "my_project", "--agent-framework", "uipath-langchain"]
                    + extra_args,
                )
                assert result.exit_code == 1
                assert (
                    "`--agent-framework` can only be used together with "
                    "`--type agent`" in result.output
                )
                assert not os.path.exists("main.py")

    def test_installed_agent_frameworks_are_named_after_their_package(self) -> None:
        """Frameworks come from the registered middlewares, not a static list."""

        def fake_middleware(name: str) -> MiddlewareResult:  # pragma: no cover
            return MiddlewareResult(should_continue=True)

        fake_middleware.__module__ = "uipath_langchain._cli.cli_new"
        entry_point = SimpleNamespace(
            module="uipath_langchain.middlewares",
            dist=SimpleNamespace(name="uipath-langchain"),
        )

        with patch(
            "uipath._cli.cli_new.Middlewares.get", return_value=[fake_middleware]
        ):
            with patch(
                "uipath._cli.cli_new.importlib.metadata.entry_points",
                return_value=[entry_point],
            ):
                (framework,) = installed_agent_frameworks()
                assert framework.package == "uipath-langchain"
                assert framework.scaffold is fake_middleware
            # Registered in-process instead of through an entry point: there is
            # no package to name it with, so it is not one to choose between.
            with patch(
                "uipath._cli.cli_new.importlib.metadata.entry_points", return_value=[]
            ):
                assert installed_agent_frameworks() == []

    def test_new_invalid_type_rejected(self, runner: CliRunner, temp_dir: str) -> None:
        """Unknown --type values are rejected by click."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["new", "my_project", "--type", "workflow"])
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
            floors = {str(s.version) for s in pin if s.operator == ">="}
            assert floors == {installed}, (
                f"scaffolded pin '{pin}' must floor at the installed uipath {installed}: "
                "a Robot refuses a project on an older uipath than it supports"
            )
