"""Guards for CLI startup cost.

`uipath --help` once took 5-7s. Resolving a command also initialized the runtime
factories, so rendering the help page loaded every installed agent stack. These
tests pin down when factories load, and what `--help` is allowed to import.
"""

import json
import subprocess
import sys
import textwrap
from typing import Any

import pytest
from click.testing import CliRunner

from uipath._cli import _LAZY_COMMANDS, cli, runtimes

# Commands that execute an agent and therefore need the runtime factories.
RUNTIME_COMMANDS = ("debug", "dev", "eval", "init", "run", "server")

# Imported by the agent runtime, never needed to parse arguments or print help.
RUNTIME_STACK = frozenset({"openai", "langgraph", "langchain_core", "uipath_langchain"})


def _run_in_fresh_interpreter(body: str) -> dict[str, Any]:
    """Run a probe in a new interpreter and return the JSON it prints.

    sys.modules is process-global and the rest of the suite has already imported
    the heavy modules, so these probes cannot run in the test process.
    """
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_help_lists_every_command() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    for name in _LAZY_COMMANDS:
        assert name in result.output


def test_help_json_lists_every_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """--format json needs full per-command metadata."""
    # LazyGroup.format_help picks the format out of sys.argv, which CliRunner
    # leaves untouched.
    monkeypatch.setattr(sys, "argv", ["uipath", "--help", "--format", "json"])
    result = CliRunner().invoke(cli, ["--help", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {command["name"] for command in payload["commands"]} == set(_LAZY_COMMANDS)
    # A group's subcommands only appear if the group was really resolved.
    assets = next(c for c in payload["commands"] if c["name"] == "assets")
    assert assets["subcommands"]


def test_help_does_not_import_runtime_stack() -> None:
    """--help must not pull in the agent runtime stack. Regression guard."""
    probe = _run_in_fresh_interpreter(
        f"""
        import json, sys
        from click.testing import CliRunner
        from uipath._cli import cli, runtimes

        result = CliRunner().invoke(cli, ["--help"])
        print(json.dumps({{
            "exit_code": result.exit_code,
            "runtime_stack": sorted({set(RUNTIME_STACK)!r} & sys.modules.keys()),
            "runtime_initialized": runtimes._initialized,
        }}))
        """
    )

    assert probe["exit_code"] == 0
    assert probe["runtime_stack"] == []
    assert probe["runtime_initialized"] is False


def test_subcommand_help_does_not_initialize_runtime() -> None:
    """Printing a runtime command's help must not load its runtime factories."""
    probe = _run_in_fresh_interpreter(
        f"""
        import json
        from click.testing import CliRunner
        from uipath._cli import cli, runtimes

        results = {{}}
        for name in {RUNTIME_COMMANDS!r}:
            results[name] = CliRunner().invoke(cli, [name, "--help"]).exit_code
        print(json.dumps({{
            "exit_codes": results,
            "runtime_initialized": runtimes._initialized,
        }}))
        """
    )

    assert set(probe["exit_codes"].values()) == {0}, probe["exit_codes"]
    assert probe["runtime_initialized"] is False


@pytest.mark.parametrize("name", RUNTIME_COMMANDS)
def test_runtime_command_initializes_runtime_before_running(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every agent-executing command is guarded by @requires_runtime.

    The sentinel raised from the initializer proves the guard runs, and runs
    before the command body, without executing the command for real.
    """

    class Sentinel(Exception):
        pass

    def initialize() -> None:
        raise Sentinel

    monkeypatch.setattr(runtimes, "ensure_runtime_initialized", initialize)
    result = CliRunner().invoke(cli, [name])

    assert isinstance(result.exception, Sentinel), result.output


def test_running_a_runtime_command_initializes_runtime() -> None:
    """Deferring initialization changed when factories load, not whether."""
    probe = _run_in_fresh_interpreter(
        """
        import json
        from click.testing import CliRunner
        from uipath._cli import cli, runtimes

        # There is no project here, so the run fails; the exit code does not
        # matter, only that invoking reaches ensure_runtime_initialized.
        CliRunner().invoke(cli, ["run", "does-not-exist"])
        print(json.dumps({"runtime_initialized": runtimes._initialized}))
        """
    )

    assert probe["runtime_initialized"] is True
