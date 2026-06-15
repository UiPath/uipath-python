"""Framework-neutral value objects for MCP-backed UiPath jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

__all__ = ["JobStart", "UiPathJobHandle"]


@dataclass(frozen=True)
class UiPathJobHandle:
    """Handle to a UiPath job started behind an MCP ``tools/call``.

    The server returns this in the START response ``_meta`` (under
    ``uipath.com/job``). It is used to drive the job to completion (suspend +
    resume, or poll) and to FETCH its result with a follow-up ``tools/call``.

    Attributes:
        job_key: The Orchestrator job key (GUID) — also the resume-trigger
            ``item_key`` when the host suspends on the job.
        folder_key: The key of the folder the job runs in.
    """

    job_key: str
    folder_key: str


@dataclass(frozen=True)
class JobStart:
    """Outcome of the START ``tools/call``.

    Either the server handed back a job handle (the tool is job-backed and the
    server started a job) or it returned a normal tool result (a non-job tool, or
    no opt-in / an older server).

    Attributes:
        handle: The job handle when the call started a job, else ``None``.
        result: The normalized tool result when ``handle`` is ``None``, else
            ``None``.
    """

    handle: Optional[UiPathJobHandle]
    result: Any = None
