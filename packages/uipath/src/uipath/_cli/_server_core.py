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
        # Optional per-job scope; ``None`` (the default) leaves jobs unscoped.
        self.job_scope_provider: (
            Callable[[], AbstractAsyncContextManager[None]] | None
        ) = None

    def init(self) -> None:
        """Must be called inside a running event loop at server startup."""
        if self.lock is not None:
            return
        self.lock = asyncio.Lock()
        self.baseline_env = os.environ.copy()


_state = _ServerState()

logger = logging.getLogger(__name__)


def register_job_scope_provider(
    provider: Callable[[], AbstractAsyncContextManager[None]] | None,
) -> None:
    """Register an async context manager entered around every job body.

    The scope is entered inside the per-job lock, *after* this module has applied the job's
    ``env_vars`` and ``working_dir`` and *before* the command runs, and on the normal path is
    exited before that state is restored. A caller therefore sees the same process environment
    and cwd the job itself sees, which is what makes per-job setup/teardown possible from
    outside this module.

    Teardown ordering is best-effort rather than guaranteed. When a job is cancelled the
    teardown is shielded but not awaited, so it runs detached and may observe the restored
    server baseline instead of the job's env and cwd. A provider that needs the job's values
    on the teardown side should capture them on entry rather than read the process state.

    Args:
        provider: Zero-argument callable returning a fresh async context manager per job, or
            ``None`` to clear the registration.
    """
    _state.job_scope_provider = provider


@asynccontextmanager
async def _job_scope() -> AsyncIterator[None]:
    """Enter the registered per-job scope, or do nothing when none is registered.

    Fail-open in both directions: a provider that raises on entry yields an un-scoped job, and
    one that raises on exit cannot mask the job's own outcome. Teardown is shielded, so a
    cancelled job still runs it to completion.
    """
    provider = _state.job_scope_provider
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


def _exit_code_outcome(exit_code: int) -> dict[str, Any]:
    return {
        "ExitCode": exit_code,
        "Error": None if exit_code == 0 else f"Exit code: {exit_code}",
        "Result": None,
        "Unexpected": False,
    }


async def _run_command_isolated(
    cmd: Any,
    args: list[str],
    env_vars: dict[str, str],
    working_dir: str | None,
    on_run_start: Callable[[], None] | None = None,
    on_run_end: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Run one command with per-job env/cwd isolation (the shared job core).

    ``on_run_start`` / ``on_run_end`` run inside the serialization lock. That orders them against
    the next job's start, but claims nothing once this task is cancelled: the job runs on a thread
    that cancellation cannot reach, so it outlives the lock and the globals move under it.
    """
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

            if on_run_start is not None:
                on_run_start()
            try:
                # Scope nested inside the hooks: the sink is installed before the scope is
                # entered and cleared after it exits, so anything the provider logs on the
                # way in or out belongs to this job rather than to the server.
                async with _job_scope():
                    result_value = await asyncio.to_thread(
                        cmd.main, args, standalone_mode=False
                    )
            finally:
                if on_run_end is not None:
                    on_run_end()
            # Under standalone_mode=False click returns ctx.exit(N)'s code instead of raising,
            # and every ConsoleLogger.error path ends in ctx.exit(1). run/debug/eval never
            # return an int of their own, so an int here is always an exit code.
            if isinstance(result_value, int) and not isinstance(result_value, bool):
                return _exit_code_outcome(result_value)
            return {
                "ExitCode": 0,
                "Error": None,
                "Result": result_value,
                "Unexpected": False,
            }
        except SystemExit as e:
            return _exit_code_outcome(e.code if isinstance(e.code, int) else 1)
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
