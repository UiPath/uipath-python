"""Framework-neutral client core for long-running UiPath jobs over MCP.

This package owns the ``uipath.com/job`` ``_meta`` contract and the executor
abstraction used to suspend/await a UiPath job that an MCP server started behind a
``tools/call``. It never imports the ``mcp`` SDK or any agent framework, so every
integration (uipath-langchain, future SDKs) can reuse it and supply only its own
:class:`McpJobExecutor`.
"""

from ._executor import (
    BlockingJobExecutor,
    FetchFn,
    JobStatusReader,
    McpJobExecutor,
    StartFn,
)
from ._handle import JobStart, UiPathJobHandle
from ._meta import (
    JOB_META_KEY,
    JOB_PROTOCOL_VERSION,
    build_fetch_meta,
    build_start_meta,
    read_job_handle,
    read_job_version,
)

__all__ = [
    "JOB_META_KEY",
    "JOB_PROTOCOL_VERSION",
    "BlockingJobExecutor",
    "FetchFn",
    "JobStart",
    "JobStatusReader",
    "McpJobExecutor",
    "StartFn",
    "UiPathJobHandle",
    "build_fetch_meta",
    "build_start_meta",
    "read_job_handle",
    "read_job_version",
]
