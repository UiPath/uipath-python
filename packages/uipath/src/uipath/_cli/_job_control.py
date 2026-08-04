"""The seam that lets the server cancel the job running on its worker thread.

Every server command drives its own event loop with ``asyncio.run`` inside the
``asyncio.to_thread`` worker. That loop is the only place a cancellation can actually
land, so the command publishes it here and the server reaches back through
``loop.call_soon_threadsafe``.

Deliberately import-light so ``_cli/__init__.py``'s lazy-import discipline is untouched.
"""

import asyncio
import contextvars
import threading
from typing import Any

CURRENT_JOB_CONTROL: contextvars.ContextVar["JobControl | None"] = (
    contextvars.ContextVar("uipath_current_job_control", default=None)
)


class JobControl:
    """Handle on one job's event loop, shared between the server loop and the worker."""

    def __init__(self, job_key: str) -> None:
        self.job_key = job_key
        self.cancel_requested = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: "asyncio.Task[Any] | None" = None
        # Bound from the job thread, read from the server loop.
        self._sync = threading.Lock()

    # ---- job thread ---------------------------------------------------------

    def bind(self, loop: asyncio.AbstractEventLoop, task: "asyncio.Task[Any]") -> None:
        with self._sync:
            self._loop, self._task = loop, task
            pending = self.cancel_requested
        if pending:
            # A stop that raced the loop's creation: apply it now rather than losing it.
            self.cancel()

    def unbind(self) -> None:
        with self._sync:
            self._loop = self._task = None

    # ---- server loop --------------------------------------------------------

    @property
    def bound(self) -> bool:
        with self._sync:
            return self._task is not None

    def cancel(self) -> bool:
        """Deliver CancelledError to the job's ROOT task only.

        Call this at most once. A second cancel lands inside the runtime's cleanup
        ``finally`` blocks — the ones that write ``output.json`` and tear the log
        interceptor down — and aborts them, which would destroy the very fallback the
        caller relies on. Escalate with ``cancel_all`` instead.
        """
        with self._sync:
            self.cancel_requested = True
            loop, task = self._loop, self._task
        if loop is None or task is None:
            # Not bound yet; bind() will apply it.
            return False
        try:
            loop.call_soon_threadsafe(task.cancel)
        except RuntimeError:
            # Loop already closed — the job is finishing anyway.
            return False
        return True

    def cancel_all(self) -> bool:
        """Escalation: cancel every task on the job's loop.

        This includes whatever the cleanup is awaiting, so it gives up on a clean
        ``output.json``. Only worth doing once a polite cancel has already failed.
        """
        with self._sync:
            loop = self._loop
        if loop is None:
            return False

        def _sweep() -> None:
            for task in asyncio.all_tasks(loop):
                task.cancel()

        try:
            loop.call_soon_threadsafe(_sweep)
        except RuntimeError:
            return False
        return True


def run_job_loop(coro: Any) -> Any:
    """``asyncio.run`` that publishes its loop and root task to the JobControl in scope.

    Outside the server — ``uipath run`` on a terminal — there is no handle in scope and
    this is ``asyncio.run`` verbatim.
    """
    control = CURRENT_JOB_CONTROL.get()
    if control is None:
        return asyncio.run(coro)

    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        task = loop.create_task(coro, context=contextvars.copy_context())
        control.bind(loop, task)
        try:
            return loop.run_until_complete(task)
        finally:
            control.unbind()
