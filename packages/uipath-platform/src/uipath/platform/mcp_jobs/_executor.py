"""Framework-neutral execution of MCP-backed UiPath jobs.

The START ``tools/call`` and the FETCH re-call are MCP-shaped concerns owned by the
caller (they touch the ``mcp`` SDK). This module models only HOW to await the started
job — by suspending the host (a framework-specific adapter) or by polling (the neutral
:class:`BlockingJobExecutor` default).
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional, Protocol, runtime_checkable

from ..orchestrator.job import Job, JobState
from ._handle import JobStart, UiPathJobHandle

__all__ = [
    "BlockingJobExecutor",
    "FetchFn",
    "McpJobExecutor",
    "StartFn",
]

StartFn = Callable[[], Awaitable[JobStart]]
"""Issues the START ``tools/call`` once and returns its :class:`JobStart` outcome."""

FetchFn = Callable[[UiPathJobHandle], Awaitable[Any]]
"""Re-calls the tool with the FETCH ``_meta`` for a handle; returns the job result."""

_TERMINAL_STATES = frozenset({JobState.SUCCESSFUL.value, JobState.FAULTED.value})


@runtime_checkable
class McpJobExecutor(Protocol):
    """Awaits a job-backed MCP tool call and returns its final output.

    An implementation owns the START → await → FETCH lifecycle for one tool call:
    it invokes ``start`` (exactly once, inside its durable boundary when it
    suspends), waits for the job to finish (by suspending the host or by polling),
    then returns ``await fetch(handle)``. Implementations differ only in *how* they
    wait, never in the wire contract.
    """

    async def run(self, *, start: StartFn, fetch: FetchFn, tool_name: str) -> Any:
        """Run one job-backed tool call to completion.

        Args:
            start: Issues the START ``tools/call`` once; returns a :class:`JobStart`.
            fetch: Re-calls the tool with the FETCH ``_meta`` for a handle.
            tool_name: The MCP tool name (for diagnostics/tracing).

        Returns:
            The tool's final output — the FETCH result for a job-backed call, or the
            normal tool result when the call did not start a job.
        """
        ...


@runtime_checkable
class JobStatusReader(Protocol):
    """Minimal jobs-service shape consumed by :class:`BlockingJobExecutor`."""

    async def retrieve_async(
        self, job_key: str, *, folder_key: Optional[str] = None
    ) -> Job:
        """Retrieve the job identified by ``job_key`` in folder ``folder_key``."""
        ...


class BlockingJobExecutor:
    """Neutral default executor: poll the job to a terminal state, then FETCH.

    This executor does **not** suspend the host. It is correct in any environment
    (a CLI, an eval harness, a framework without durable interrupts): the child job
    stays running while we poll, but the tool always returns the right result. Hosts
    that *can* suspend should inject a framework-specific executor instead (for
    example a LangGraph one that interrupts on the job and resumes when it finishes).
    """

    def __init__(
        self,
        jobs: Optional[JobStatusReader] = None,
        *,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> None:
        """Initialize the executor.

        Args:
            jobs: A jobs service exposing
                ``retrieve_async(job_key, *, folder_key)``. Defaults to
                ``UiPath().jobs`` (constructed lazily) when ``None``.
            poll_interval: Seconds to wait between status polls.
            timeout: Optional overall timeout in seconds; ``None`` waits
                indefinitely.
        """
        self._jobs = jobs
        self._poll_interval = poll_interval
        self._timeout = timeout

    def _jobs_service(self) -> JobStatusReader:
        if self._jobs is None:
            from .._uipath import UiPath

            self._jobs = UiPath().jobs
        return self._jobs

    async def run(self, *, start: StartFn, fetch: FetchFn, tool_name: str) -> Any:
        """Start the job, poll until terminal, then FETCH its result.

        Args:
            start: Issues the START ``tools/call`` once.
            fetch: Re-calls the tool with the FETCH ``_meta`` for a handle.
            tool_name: The MCP tool name (for diagnostics/tracing).

        Returns:
            The FETCH result for a job-backed call, or the normal tool result when
            the call did not start a job.
        """
        outcome = await start()
        if outcome.handle is None:
            return outcome.result
        await self._wait_until_terminal(outcome.handle)
        return await fetch(outcome.handle)

    async def _wait_until_terminal(self, handle: UiPathJobHandle) -> None:
        jobs = self._jobs_service()
        loop = asyncio.get_event_loop()
        deadline = None if self._timeout is None else loop.time() + self._timeout
        while True:
            job = await jobs.retrieve_async(
                handle.job_key, folder_key=handle.folder_key
            )
            if (job.state or "").lower() in _TERMINAL_STATES:
                return
            if deadline is not None and loop.time() >= deadline:
                raise TimeoutError(
                    f"Job {handle.job_key} did not reach a terminal state "
                    f"within {self._timeout}s"
                )
            await asyncio.sleep(self._poll_interval)
