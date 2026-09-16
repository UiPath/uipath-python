"""Assertions on what the CLI imports at startup.

`uipath --help` once took 5-7s: click resolves every command to render the help
table, and resolving a runtime command used to load the `uipath.runtime.factories`
entry points, so printing a help page imported the whole agent stack of every
installed plugin.

These assertions count modules rather than measure seconds. Wall-clock time for a
process that opens ~1200 module files is dominated by the runner's filesystem and
anti-virus -- measured swings of 2.7s to 13s for the same build on one machine --
and the budget needed to catch the original regression sits inside that noise. The
set of imported modules is exactly what regressed, and it is deterministic.
"""

import json
import subprocess
import sys
import textwrap

RUNTIME_STACK = (
    "langgraph",
    "langchain_core",
    "openai",
    "uipath_langchain",
    "llama_index",
    "uipath_llamaindex",
)


def _probe(body: str) -> dict:
    """Run a probe in a fresh interpreter and return the JSON it prints."""
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"startup probe failed ({completed.returncode}): {completed.stderr}"
    )
    return json.loads(completed.stdout)


def assert_cli_import_is_lean(max_modules: int) -> None:
    """Importing the CLI must stay cheap enough for `uipath --version`.

    Args:
        max_modules: Upper bound on modules in sys.modules after
            `from uipath._cli import cli`. Was 582 before the import chain
            through `uipath/_utils/__init__.py` was broken, and is 212 after.
    """
    result = _probe(
        """
        import json, sys
        from uipath._cli import cli
        print(json.dumps({"modules": len(sys.modules)}))
        """
    )
    modules = result["modules"]

    print(f"'import uipath._cli' loads {modules} modules (budget {max_modules})")
    assert modules <= max_modules, (
        f"importing uipath._cli loads {modules} modules, over the budget of "
        f"{max_modules}. Something expensive was added to the top-level imports "
        f"of uipath/_cli/__init__.py or a package __init__ it reaches through."
    )


def assert_help_does_not_load_runtime_stack() -> None:
    """Rendering `--help` must not import any installed agent runtime.

    Only meaningful where a package registers a `uipath.runtime.factories` entry
    point, so call it from a testcase that installs one.
    """
    result = _probe(
        f"""
        import json, sys
        from click.testing import CliRunner
        from uipath._cli import cli

        outcome = CliRunner().invoke(cli, ["--help"])
        print(json.dumps({{
            "exit_code": outcome.exit_code,
            # Checked here: the table sits past any excerpt worth sending back.
            "has_table": "Commands" in outcome.output,
            "excerpt": outcome.output[:200],
            "loaded": sorted(set({RUNTIME_STACK!r}) & sys.modules.keys()),
        }}))
        """
    )

    assert result["exit_code"] == 0, f"'uipath --help' failed: {result['excerpt']}"
    assert result["has_table"], (
        f"'uipath --help' printed no command table: {result['excerpt']}"
    )
    assert not result["loaded"], (
        f"'uipath --help' imported the agent runtime stack: {result['loaded']}. "
        f"Printing help must not load runtime factories; see "
        f"requires_runtime in uipath/_cli/runtimes.py."
    )

    print("'uipath --help' loaded no agent runtime stack")
