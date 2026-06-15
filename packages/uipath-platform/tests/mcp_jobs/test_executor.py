from typing import List, Optional

import pytest

from uipath.platform.mcp_jobs import (
    BlockingJobExecutor,
    JobStart,
    UiPathJobHandle,
)
from uipath.platform.orchestrator.job import Job


class _FakeJobs:
    """A jobs service whose ``retrieve_async`` walks a scripted list of states.

    The last state repeats once exhausted, so ``["running", "successful"]`` yields
    ``running`` on the first poll and ``successful`` thereafter.
    """

    def __init__(self, states: List[str]) -> None:
        self._states = list(states)
        self.calls: List[tuple[str, Optional[str]]] = []

    async def retrieve_async(
        self, job_key: str, *, folder_key: Optional[str] = None
    ) -> Job:
        self.calls.append((job_key, folder_key))
        state = self._states.pop(0) if len(self._states) > 1 else self._states[0]
        return Job(id=1, key=job_key, state=state, folder_key=folder_key)


def _start_returning(outcome: JobStart):
    async def start() -> JobStart:
        return outcome

    return start


async def test_non_job_returns_result_without_polling() -> None:
    jobs = _FakeJobs(["running"])
    executor = BlockingJobExecutor(jobs, poll_interval=0)

    async def fetch(handle: UiPathJobHandle) -> str:
        raise AssertionError("fetch must not run for a non-job call")

    out = await executor.run(
        start=_start_returning(JobStart(handle=None, result="normal-result")),
        fetch=fetch,
        tool_name="tool",
    )

    assert out == "normal-result"
    assert jobs.calls == []


async def test_polls_until_terminal_then_fetches() -> None:
    jobs = _FakeJobs(["running", "running", "successful"])
    executor = BlockingJobExecutor(jobs, poll_interval=0)
    handle = UiPathJobHandle(job_key="job-1", folder_key="folder-1")

    async def fetch(h: UiPathJobHandle) -> dict[str, str]:
        return {"fetched": h.job_key, "folder": h.folder_key}

    out = await executor.run(
        start=_start_returning(JobStart(handle=handle)),
        fetch=fetch,
        tool_name="tool",
    )

    assert out == {"fetched": "job-1", "folder": "folder-1"}
    # running, running, successful -> 3 polls
    assert jobs.calls == [("job-1", "folder-1")] * 3


async def test_faulted_is_terminal_and_still_fetches() -> None:
    jobs = _FakeJobs(["faulted"])
    executor = BlockingJobExecutor(jobs, poll_interval=0)
    handle = UiPathJobHandle(job_key="job-2", folder_key="folder-2")

    async def fetch(h: UiPathJobHandle) -> str:
        return "server-formatted-error"

    out = await executor.run(
        start=_start_returning(JobStart(handle=handle)),
        fetch=fetch,
        tool_name="tool",
    )

    assert out == "server-formatted-error"
    assert len(jobs.calls) == 1


async def test_timeout_when_never_terminal() -> None:
    jobs = _FakeJobs(["running"])
    executor = BlockingJobExecutor(jobs, poll_interval=0, timeout=0)
    handle = UiPathJobHandle(job_key="job-3", folder_key="folder-3")

    async def fetch(h: UiPathJobHandle) -> str:
        raise AssertionError("fetch must not run when the job never finishes")

    with pytest.raises(TimeoutError):
        await executor.run(
            start=_start_returning(JobStart(handle=handle)),
            fetch=fetch,
            tool_name="tool",
        )
