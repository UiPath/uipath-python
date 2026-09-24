"""Lets the server cancel the job that runs on its worker thread.

run/debug/eval drive their own event loop inside the ``asyncio.to_thread`` worker. That
loop is the only place a cancellation can land, so the command publishes it here and
the server reaches it through ``loop.call_soon_threadsafe``.

Kept import-light: ``_cli/__init__.py`` defers heavy imports.
"""

import asyncio
import contextvars
import threading
from typing import Any

CURRENT_JOB_CONTROL: contextvars.ContextVar["JobControl | None"] = (
    contextvars.ContextVar("uipath_current_job_control", default=None)
)


class JobControl:
    """Handle on one job's event loop, shared by the server loop and the job thread."""

    def __init__(self) -> None:
        """Create an unbound control; the job binds its loop once it has one."""
        self.cancel_requested = False
        self._delivered = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: "asyncio.Task[Any] | None" = None
        self._sync = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop, task: "asyncio.Task[Any]") -> None:
        """Publish the job's loop and root task (job thread)."""
        with self._sync:
            self._loop, self._task = loop, task
            pending = self.cancel_requested
        if pending:
            self.cancel()

    def unbind(self) -> None:
        """Withdraw the loop once the root task is done (job thread)."""
        with self._sync:
            self._loop = self._task = None

    def cancel(self) -> None:
        """Cancel the job's root task, at most once.

        A second delivery would land inside the runtime's cleanup ``finally`` blocks,
        the ones that write ``output.json``, and abort them. Before the job has a loop,
        the request is recorded and applied by ``bind``.
        """
        with self._sync:
            self.cancel_requested = True
            if self._delivered or self._loop is None or self._task is None:
                return
            loop, task = self._loop, self._task
            self._delivered = True
        try:
            loop.call_soon_threadsafe(task.cancel)
        except RuntimeError:
            with self._sync:
                self._delivered = False

    def cancel_all(self) -> None:
        """Cancel every task on the job's loop, giving up on a clean cleanup."""
        with self._sync:
            self.cancel_requested = True
            loop = self._loop
        if loop is None:
            return

        def _sweep() -> None:
            for task in asyncio.all_tasks(loop):
                task.cancel()

        try:
            loop.call_soon_threadsafe(_sweep)
        except RuntimeError:
            pass


def run_job_loop(coro: Any) -> Any:
    """``asyncio.run`` that publishes its loop and root task to the job's control.

    With no control in scope (``uipath run`` from a terminal) this is ``asyncio.run``.
    The loop is withdrawn before the runner closes, so a sweep can never cancel the
    runner's own wait on the job's executor threads.
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
