"""Transport-agnostic job core shared by the HTTP and uipath-ipc channels."""

import asyncio
import json
import os
import shlex
from typing import Any

from .cli_debug import debug
from .cli_eval import eval
from .cli_run import run

COMMANDS = {
    "run": run,
    "debug": debug,
    "eval": eval,
}


class _ServerState:
    """Mutable server state, initialized lazily at server startup."""

    def __init__(self) -> None:
        self.lock: asyncio.Lock | None = None
        self.baseline_env: dict[str, str] | None = None

    def init(self) -> None:
        """Must be called inside a running event loop at server startup."""
        if self.lock is not None:
            return
        self.lock = asyncio.Lock()
        self.baseline_env = os.environ.copy()


_state = _ServerState()


def parse_args(args: str | list[str] | None) -> list[str]:
    """Parse args into a list of strings."""
    if args is None:
        return []
    if isinstance(args, list):
        return args
    if isinstance(args, str):
        return shlex.split(args)
    return []


# The document is carried inline on the result push when it fits. uipath_ipc caps a
# frame at 2 MiB and Orchestrator already spills large outputs to an attachment, so
# anything bigger stays on disk and the caller reads the file as it always has.
MAX_INLINE_DOCUMENT_BYTES = 1024 * 1024

DEFAULT_RUNTIME_DIR = "__uipath"
DEFAULT_RESULT_FILE = "output.json"
DEFAULT_LOGS_FILE = "execution.log"


def _resolve_runtime_file(
    config_path: str, base_dir: str, key: str, default_name: str
) -> str | None:
    """Resolve one ``runtime.*`` file path from a uipath.json.

    Mirrors UiPathRuntimeContext.from_config's ``runtime.dir`` / ``runtime.<key>``
    mapping. ``base_dir`` anchors relative paths so this works without ever changing
    the process's cwd.
    """
    if not os.path.isabs(config_path):
        config_path = os.path.join(base_dir, config_path)

    runtime: dict[str, Any] = {}
    try:
        with open(config_path, encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            runtime = loaded.get("runtime") or {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # Fall through to the runtime's own defaults rather than giving up. Returning
        # None here would stop the log tailer from starting at all — and by then the
        # caller has already been told we forward logs and stopped tailing the file
        # itself, so the job would produce no logs anywhere.
        runtime = {}

    directory = runtime.get("dir") or DEFAULT_RUNTIME_DIR
    name = runtime.get(key) or default_name
    if not isinstance(directory, str) or not isinstance(name, str):
        directory, name = DEFAULT_RUNTIME_DIR, default_name

    if not os.path.isabs(directory):
        directory = os.path.join(base_dir, directory)
    return os.path.abspath(os.path.join(directory, name))


def resolve_result_file_path() -> str | None:
    """Where this job's terminal document lives. Call inside the job's env and cwd."""
    return _resolve_runtime_file(
        os.environ.get("UIPATH_CONFIG_PATH", "uipath.json"),
        os.getcwd(),
        "outputFile",
        DEFAULT_RESULT_FILE,
    )


def resolve_logs_file_path(
    env_vars: dict[str, str] | None, working_dir: str | None
) -> str | None:
    """Where this job will write its log file, derived from the request alone.

    Pure with respect to process state: the log tailer has to know the path *before*
    the job takes the lock and applies its env/cwd.
    """
    env_vars = env_vars or {}
    base_dir = working_dir or os.getcwd()
    config_path = env_vars.get("UIPATH_CONFIG_PATH", "uipath.json")
    return _resolve_runtime_file(config_path, base_dir, "logsFile", DEFAULT_LOGS_FILE)


def _read_result_document() -> tuple[str | None, str]:
    """Return ``(document, conveyance)`` for the terminal result document.

    ``conveyance`` is ``inline`` when the document rides the wire, ``file`` when the
    caller must read it from disk (too large, unreadable, or never written).
    """
    path = resolve_result_file_path()
    if not path or not os.path.exists(path):
        return None, "file"

    try:
        if os.path.getsize(path) > MAX_INLINE_DOCUMENT_BYTES:
            return None, "file"
        with open(path, encoding="utf-8") as f:
            return f.read(), "inline"
    except (OSError, UnicodeDecodeError):
        return None, "file"


async def _invoke_command(cmd: Any, args: list[str]) -> dict[str, Any]:
    """Invoke one click command and classify how it ended."""
    try:
        result_value = await asyncio.to_thread(cmd.main, args, standalone_mode=False)
        # Under standalone_mode=False click RETURNS ctx.exit(N)'s code instead of
        # raising SystemExit, so a bare int is the exit code, not a result — every
        # ConsoleLogger.error path lands here via ctx.exit(1). The run/debug/eval
        # callbacks only ever return a result object or None, so this is unambiguous.
        if isinstance(result_value, int) and not isinstance(result_value, bool):
            return {
                "ExitCode": result_value,
                "Error": None if result_value == 0 else f"Exit code: {result_value}",
                "Result": None,
                "Unexpected": False,
            }
        return {
            "ExitCode": 0,
            "Error": None,
            "Result": result_value,
            "Unexpected": False,
        }
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        return {
            "ExitCode": exit_code,
            "Error": None if exit_code == 0 else f"Exit code: {exit_code}",
            "Result": None,
            "Unexpected": False,
        }
    except Exception as e:  # report any job failure as a result, not a fault
        return {"ExitCode": 1, "Error": str(e), "Result": None, "Unexpected": True}


async def _run_command_isolated(
    cmd: Any,
    args: list[str],
    env_vars: dict[str, str],
    working_dir: str | None,
) -> dict[str, Any]:
    """Run one command with per-job env/cwd isolation (the shared job core)."""
    if _state.lock is None or _state.baseline_env is None:
        raise RuntimeError("Server state not initialized")

    async with _state.lock:
        original_cwd = os.getcwd()
        try:
            # Start from server baseline + request env vars only, so nothing from
            # a previous job leaks through.
            os.environ.clear()
            os.environ.update(_state.baseline_env)
            if isinstance(env_vars, dict):
                os.environ.update(env_vars)

            if working_dir and isinstance(working_dir, str):
                try:
                    os.chdir(working_dir)
                except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
                    # Request-shaped error: the caller gave a bad working dir.
                    # HTTP surfaces this as 400; IPC just returns ExitCode/Error.
                    return {
                        "ExitCode": 1,
                        "Error": f"Cannot change to working directory: {e}",
                        "Result": None,
                        "Unexpected": False,
                        "ClientError": True,
                    }

            outcome = await _invoke_command(cmd, args)
            # Must happen before the finally below restores env/cwd: the document's
            # location comes from this job's UIPATH_CONFIG_PATH and may be relative.
            document, conveyance = _read_result_document()
            outcome["Document"] = document
            outcome["DocumentConveyance"] = conveyance
            return outcome
        finally:
            # Restore to server baseline.
            try:
                os.chdir(original_cwd)
            except OSError:
                pass
            os.environ.clear()
            os.environ.update(_state.baseline_env)
