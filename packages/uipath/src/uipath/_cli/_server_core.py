"""Transport-agnostic job core shared by the HTTP and uipath-ipc channels."""

import asyncio
import logging
import os
import shlex
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
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

logger = logging.getLogger(__name__)

# Optional per-job scope, registered by an out-of-process concern that needs to bracket
# every job this server runs. ``None`` — the default — means no scope is installed and
# the job runs exactly as it did before.
_job_scope_provider: Callable[[], AbstractAsyncContextManager[None]] | None = None


def register_job_scope_provider(
    provider: Callable[[], AbstractAsyncContextManager[None]] | None,
) -> None:
    """Register an async context manager entered around every job body.

    The scope is entered inside the per-job lock, *after* this module has applied the job's
    ``env_vars`` and ``working_dir`` and *before* the command runs, and exited before that
    state is restored. A caller therefore sees the same process environment and cwd the job
    itself sees, which is what makes per-job setup/teardown possible from outside this module.

    Args:
        provider: Zero-argument callable returning a fresh async context manager per job, or
            ``None`` to clear the registration.
    """
    global _job_scope_provider
    _job_scope_provider = provider


@asynccontextmanager
async def _job_scope() -> AsyncIterator[None]:
    """Enter the registered per-job scope, or do nothing when none is registered.

    Fail-open in both directions: a provider that raises on entry yields an un-scoped job, and
    one that raises on exit cannot mask the job's own outcome. Teardown is shielded, so a
    cancelled job still runs it to completion.
    """
    provider = _job_scope_provider
    if provider is None:
        yield
        return

    scope: AbstractAsyncContextManager[None] | None = None
    try:
        scope = provider()
        await scope.__aenter__()
    except Exception:
        logger.warning(
            "job scope provider failed to start; job runs unscoped", exc_info=True
        )
        scope = None

    try:
        yield
    finally:
        if scope is not None:
            try:
                # Shielded: a cancel delivered while the job unwinds must not leave the
                # provider half torn down.
                await asyncio.shield(scope.__aexit__(None, None, None))
            except Exception:
                logger.warning("job scope provider failed to exit", exc_info=True)


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

            async with _job_scope():
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
