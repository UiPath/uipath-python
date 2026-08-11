"""Transport-agnostic job core shared by the HTTP and uipath-ipc channels."""

import asyncio
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

            result_value = await asyncio.to_thread(
                cmd.main, args, standalone_mode=False
            )
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
        finally:
            # Restore to server baseline.
            try:
                os.chdir(original_cwd)
            except OSError:
                pass
            os.environ.clear()
            os.environ.update(_state.baseline_env)
