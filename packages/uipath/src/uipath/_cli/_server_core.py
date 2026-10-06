"""Transport-agnostic job core shared by the HTTP and uipath-ipc channels."""

import asyncio
import contextvars
import functools
import logging
import os
import shlex
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from ._execution_control import CURRENT_EXECUTION_CONTROL, ExecutionControl
from .cli_debug import debug
from .cli_eval import eval
from .cli_run import run

COMMANDS = {
    "run": run,
    "debug": debug,
    "eval": eval,
}


# Distinct from any click exit code, so a stop on request is not read as a failure.
EXIT_CODE_STOPPED = 143

STOP_GRACE_SECONDS = 30.0
STOP_ESCALATION_SECONDS = 10.0
FORCE_STOP_GRACE_SECONDS = 5.0
FORCE_STOP_ESCALATION_SECONDS = 5.0


@dataclass
class _Execution:
    job_key: str
    resume_version: int | None
    control: ExecutionControl = field(default_factory=ExecutionControl)
    started: bool = False
    stop_requested: asyncio.Event = field(default_factory=asyncio.Event)
    finished: asyncio.Event = field(default_factory=asyncio.Event)


class _ServerState:
    """Mutable server state, initialized lazily at server startup."""

    def __init__(self) -> None:
        self.lock: asyncio.Lock | None = None
        self.baseline_env: dict[str, str] | None = None
        # Queued and running executions; the lock lets at most one of them run.
        self.executions: list[_Execution] = []
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

    The env and cwd are restored only after the teardown has finished, cancelled or not.

    Args:
        provider: Zero-argument callable returning a fresh async context manager per job, or
            ``None`` to clear the registration.
    """
    _state.job_scope_provider = provider


@asynccontextmanager
async def _job_scope() -> AsyncIterator[None]:
    """Enter the registered per-job scope, or do nothing when none is registered.

    Fail-open in both directions: a provider that raises on entry yields an un-scoped job, and
    one that raises on exit cannot mask the job's own outcome. A cancelled execution still
    runs the teardown to completion before the cancellation moves on.
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
            teardown = asyncio.ensure_future(scope.__aexit__(None, None, None))
            try:
                await _await_despite_cancellation(teardown)
            finally:
                if not teardown.cancelled() and teardown.exception() is not None:
                    logger.warning(
                        "job scope provider failed to exit",
                        exc_info=teardown.exception(),
                    )


async def _await_despite_cancellation(
    future: "asyncio.Future[Any]", on_cancel: Callable[[], None] | None = None
) -> None:
    """Wait for ``future`` to finish, even if this task is cancelled meanwhile.

    A cancellation that arrives while waiting runs ``on_cancel`` and is re-raised once
    ``future`` has finished, so nothing the caller does next runs ahead of it.
    """
    try:
        await asyncio.wait([future])
    except asyncio.CancelledError:
        if on_cancel is not None:
            on_cancel()
        await _await_despite_cancellation(future, on_cancel)
        raise


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


def _stopped_outcome() -> dict[str, Any]:
    return {
        "ExitCode": EXIT_CODE_STOPPED,
        "Error": "Stopped on request",
        "Result": None,
        "Unexpected": False,
        "Stopped": True,
    }


def _find_execution(job_key: str, resume_version: int | None) -> _Execution | None:
    for execution in _state.executions:
        if execution.job_key != job_key:
            continue
        if (
            resume_version is not None
            and execution.resume_version is not None
            and execution.resume_version != resume_version
        ):
            continue
        return execution
    return None


async def _wait_finished(execution: _Execution, timeout: float) -> bool:
    try:
        async with asyncio.timeout(timeout):
            await execution.finished.wait()
        return True
    except TimeoutError:
        return False


async def stop_execution(
    job_key: str, resume_version: int | None = None, force: bool = False
) -> bool:
    """Stop a queued or running execution and report whether it is no longer running.

    A running execution is stopped cooperatively: its event loop's root task is
    cancelled, so the runtime unwinds and still writes its result. If it has not
    finished within the grace period every task on its loop is cancelled, and if it
    still has not finished the answer is False: it is blocked in a call that cannot be
    interrupted, and only ending the process stops it. ``force`` shortens both waits.

    An execution that is not known, or whose live run has another resume version, is
    not running, so the answer is True.
    """
    execution = _find_execution(job_key, resume_version)
    if execution is None:
        logger.info("StopJob for %s: no such execution is queued or running", job_key)
        return True

    grace, escalation = (
        (FORCE_STOP_GRACE_SECONDS, FORCE_STOP_ESCALATION_SECONDS)
        if force
        else (STOP_GRACE_SECONDS, STOP_ESCALATION_SECONDS)
    )

    execution.control.cancel()
    if not execution.started:
        execution.stop_requested.set()
        return True

    if await _wait_finished(execution, grace):
        return True

    logger.warning(
        "StopJob for %s: still running after %ss; cancelling every task on its loop",
        job_key,
        grace,
    )
    execution.control.cancel_all()
    if await _wait_finished(execution, escalation):
        return True

    logger.error(
        "StopJob for %s: still running; it is blocked in a call that cannot be "
        "interrupted",
        job_key,
    )
    return False


async def _run_on_worker_thread(
    cmd: Any, args: list[str], execution: _Execution
) -> dict[str, Any]:
    """Run the command on a worker thread and return once that thread has exited.

    Cancelling the awaiting task (a dropped connection, a server shutdown) stops the
    execution instead of abandoning it, and the cancellation is re-raised only once the
    thread is gone, so the lock, env and cwd are never handed on while the execution
    still runs.
    """
    loop = asyncio.get_running_loop()
    token = CURRENT_EXECUTION_CONTROL.set(execution.control)
    try:
        context = contextvars.copy_context()
    finally:
        CURRENT_EXECUTION_CONTROL.reset(token)
    # A plain executor future rather than a task: a task re-raises the execution's
    # SystemExit into the server loop instead of keeping it as its outcome.
    worker = loop.run_in_executor(
        None, functools.partial(context.run, cmd.main, args, standalone_mode=False)
    )
    escalations: list[asyncio.TimerHandle] = []

    def _stop_abandoned_execution() -> None:
        execution.control.cancel()
        if not escalations:
            escalations.append(
                loop.call_later(STOP_GRACE_SECONDS, execution.control.cancel_all)
            )

    try:
        await _await_despite_cancellation(worker, _stop_abandoned_execution)
    finally:
        for handle in escalations:
            handle.cancel()
        execution.finished.set()

    if worker.cancelled() or isinstance(worker.exception(), asyncio.CancelledError):
        if execution.control.cancel_requested:
            return _stopped_outcome()
        return {
            "ExitCode": 1,
            "Error": "The execution cancelled itself",
            "Result": None,
            "Unexpected": True,
        }

    exc = worker.exception()
    if exc is not None:
        raise exc

    result_value = worker.result()
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


async def _run_command_isolated(
    cmd: Any,
    args: list[str],
    env_vars: dict[str, str],
    working_dir: str | None,
    on_run_start: Callable[[], None] | None = None,
    on_run_end: Callable[[], None] | None = None,
    job_key: str | None = None,
    resume_version: int | None = None,
) -> dict[str, Any]:
    """Run one command with per-job env/cwd isolation (the shared job core).

    ``on_run_start`` / ``on_run_end`` run inside the serialization lock, and the lock,
    env and cwd are only given back once the execution's thread has exited. An execution
    with a ``job_key`` can be stopped through `stop_execution`.
    """
    if _state.lock is None or _state.baseline_env is None:
        raise RuntimeError("Server state not initialized")

    execution = _Execution(job_key or "", resume_version)
    if job_key:
        _state.executions.append(execution)
    try:
        return await _run_registered_execution(
            execution, cmd, args, env_vars, working_dir, on_run_start, on_run_end
        )
    finally:
        if job_key:
            _state.executions.remove(execution)


async def _acquire_unless_stopped(execution: _Execution, lock: asyncio.Lock) -> bool:
    """Take the lock; False when the execution is stopped while it waits for it."""
    acquired = asyncio.ensure_future(lock.acquire())
    stopped = asyncio.ensure_future(execution.stop_requested.wait())
    try:
        await asyncio.wait({acquired, stopped}, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        _give_up_lock(acquired, lock)
        raise
    finally:
        stopped.cancel()
    if execution.stop_requested.is_set():
        _give_up_lock(acquired, lock)
        return False
    return True


def _give_up_lock(acquired: "asyncio.Future[Any]", lock: asyncio.Lock) -> None:
    # A pending acquire, once cancelled, never holds the lock; a completed one does.
    if not acquired.cancel() and not acquired.cancelled():
        lock.release()


async def _run_registered_execution(
    execution: _Execution,
    cmd: Any,
    args: list[str],
    env_vars: dict[str, str],
    working_dir: str | None,
    on_run_start: Callable[[], None] | None,
    on_run_end: Callable[[], None] | None,
) -> dict[str, Any]:
    assert _state.lock is not None and _state.baseline_env is not None
    if not await _acquire_unless_stopped(execution, _state.lock):
        return _stopped_outcome()
    execution.started = True

    try:
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
                    return await _run_on_worker_thread(cmd, args, execution)
            finally:
                if on_run_end is not None:
                    on_run_end()
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
    finally:
        _state.lock.release()
