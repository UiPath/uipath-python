"""Models for the MCP Tasks extension on UiPath MCP servers.

The Tasks extension (``io.modelcontextprotocol/tasks``) lets a long-running
``tools/call`` — typically a UiPath process invocation — return a durable task
handle instead of holding the request open; the caller then polls ``tasks/get``
until the task is terminal. UiPath MCP servers serve the extension on the
2026-07-28 per-request-metadata protocol revision, which is stateless: no
initialize handshake, no session, every request self-contained.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MCP_TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"
MCP_TASKS_PROTOCOL_VERSION = "2026-07-28"
MCP_TASK_RESULT_TYPE = "task"


class McpTaskStatus(str, Enum):
    """Task lifecycle states; the last three are terminal."""

    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Whether the status is final and can no longer change."""
        return self in (
            McpTaskStatus.COMPLETED,
            McpTaskStatus.FAILED,
            McpTaskStatus.CANCELLED,
        )


class McpTask(BaseModel):
    """A durable task handle over a long-running MCP tool call.

    Returned by ``tools/call`` when the server decides the call is
    long-running, and by every ``tasks/get`` poll. Once terminal, ``result``
    carries what the original call would have returned synchronously
    (a CallToolResult object), or ``error`` carries the JSON-RPC error.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )

    task_id: str
    status: McpTaskStatus
    status_message: Optional[str] = None
    created_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    ttl_ms: Optional[int] = None
    poll_interval_ms: Optional[int] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None

    # Client-side only: the MCP endpoint this task was minted by, so follow-up
    # tasks/get, cancel, and wait calls know where to go. Never serialized.
    server_url: Optional[str] = Field(default=None, exclude=True)


class McpToolCallOutcome(BaseModel):
    """Either shape a task-capable ``tools/call`` can answer.

    ``result`` holds the plain CallToolResult object when the server answered
    synchronously; ``task`` holds the durable handle when it did not. Exactly
    one is set.
    """

    model_config = ConfigDict(extra="forbid")

    result: Optional[dict[str, Any]] = None
    task: Optional[McpTask] = None

    @property
    def is_task(self) -> bool:
        """Whether the server answered with a task handle instead of a result."""
        return self.task is not None


class McpToolCallError(Exception):
    """A JSON-RPC error answered an MCP request."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        """Initialize with the JSON-RPC error code, message, and optional data."""
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class McpTaskFailedError(Exception):
    """The task reached ``failed``; carries the server's JSON-RPC error object."""

    def __init__(self, task: McpTask) -> None:
        """Initialize with the terminal task snapshot."""
        super().__init__(f"MCP task {task.task_id} failed: {task.error}")
        self.task = task


class McpTaskCancelledError(Exception):
    """The task reached ``cancelled`` before producing a result."""

    def __init__(self, task: McpTask) -> None:
        """Initialize with the terminal task snapshot."""
        super().__init__(f"MCP task {task.task_id} was cancelled.")
        self.task = task
