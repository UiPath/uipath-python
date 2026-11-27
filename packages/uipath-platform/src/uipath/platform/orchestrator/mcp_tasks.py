"""Models for the MCP Tasks extension on UiPath MCP servers.

The Tasks extension (``io.modelcontextprotocol/tasks``) lets a long-running
``tools/call`` — typically a UiPath process invocation — return a durable task
handle instead of holding the request open; the caller then polls ``tasks/get``
until the task is terminal. UiPath MCP servers serve the extension on the
2026-07-28 per-request-metadata protocol revision, which is stateless: no
initialize handshake, no session, every request self-contained.
"""

import uuid
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


def task_ref(task_id: str) -> str:
    """A task id shortened for a message or a log line.

    An MCP task id is a self-contained handle, not a short key: a UiPath server
    mints one of 368 characters, and the first 27 of those are identical across
    tasks (a header on the encrypted blob). Taking a prefix therefore
    distinguishes nothing -- every task reads the same -- so this takes both
    ends. Short ids, which is what tests use, are left alone.

    Whoever can reach the server can read or cancel a task with its id, and a
    message or a log line travels further than the call that produced it; on
    the agent path this text is also read by a model, where a few hundred
    characters of opaque handle is noise it may well repeat. The full id stays
    in the one log line written when the task is first seen, which is what an
    operator needs to find a task that outlived its wait.
    """
    if len(task_id) <= 32:
        return task_id
    return f"{task_id[:12]}...{task_id[-8:]}"


MCP_TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"

# The UiPath flavour of the same protocol. A server that honours it answers
# exactly as it does for the standard extension, and additionally says which
# Orchestrator job is behind the task -- see ``McpTaskJob``.
MCP_UIPATH_TASKS_EXTENSION_ID = "com.uipath/tasks"
MCP_UIPATH_TASK_META_KEY = "com.uipath/task"

#: The version of the ``com.uipath/task`` annotation this client reads.
MCP_UIPATH_TASK_ANNOTATION_VERSION = 1
#: The resume-trigger kind this client can suspend on. The server may name
#: other kinds later; a task annotated with one of those is polled.
MCP_UIPATH_TASK_JOB_TRIGGER = "Job"
#: The resume-trigger kind for a task the server does not run itself (a Remote
#: MCP server's own task): the caller suspends on an API trigger, which the
#: server fires once the task has ended. Declared only by a caller that asks
#: for it (``call_tool(resume_trigger_types=...)``, ``watch_task``).
MCP_UIPATH_TASK_API_TRIGGER = "Api"
#: This client's ``com.uipath/tasks`` declaration: the trigger kinds it handles.
MCP_UIPATH_TASKS_CAPABILITY: dict[str, Any] = {
    "resumeTriggerTypes": [MCP_UIPATH_TASK_JOB_TRIGGER]
}
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


class McpTaskApiTrigger(BaseModel):
    """That a task can be suspended on through a watch (``McpTask.api_trigger``).

    A task a Remote MCP server runs has no Orchestrator job behind it. The
    server (AgentHub) annotates it with an ``Api`` resume trigger instead: a
    caller that is itself a job can ask for a watch (``McpService.watch_task``)
    and suspend on an API trigger the server fires when the task has ended.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    suspend_after_ms: Optional[int] = Field(default=None, alias="suspendAfterMs")

    @field_validator("suspend_after_ms", mode="before")
    @classmethod
    def _is_a_duration(cls, value: Any) -> Optional[int]:
        return _whole_milliseconds(value)


class McpTaskWatch(BaseModel):
    """A watch the server started on a task (``McpTask.watch``).

    Attributes:
        watch_id: Names the watch. The caller suspends on an API trigger whose
            request is ``{"com.uipath/task": {"watchId": watch_id}}``; the
            server delivers only to a trigger that carries it.
        expires_in_ms: How long the watch runs. The caller should also suspend
            on a timer for this long, so it wakes whether or not it is woken.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    watch_id: str = Field(alias="id")
    expires_in_ms: int = Field(alias="expiresInMs")

    @field_validator("watch_id")
    @classmethod
    def _is_a_guid(cls, value: str) -> str:
        return str(uuid.UUID(value))

    @field_validator("expires_in_ms", mode="before")
    @classmethod
    def _is_a_positive_duration(cls, value: Any) -> int:
        milliseconds = _whole_milliseconds(value)
        if milliseconds is None or milliseconds <= 0:
            raise ValueError("expiresInMs must be a positive number of milliseconds")
        return milliseconds


def _whole_milliseconds(value: Any) -> Optional[int]:
    """A whole, non-negative number of milliseconds, else ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    if value < 0:
        return None
    return int(value)


class McpTaskJob(BaseModel):
    """The Orchestrator job behind a task, from its ``com.uipath/task`` annotation.

    A UiPath MCP server adds the annotation for a caller that declared
    ``com.uipath/tasks``. It is what lets a caller that is itself an
    Orchestrator job stop holding compute while the task runs: instead of
    polling, it suspends on a Job-type resume trigger for ``job_key`` and reads
    the task with ``tasks/get`` once Orchestrator resumes it.

    Attributes:
        job_key: The job to suspend on.
        folder_key: The folder that job runs in.
        suspend_after_ms: How long the server suggests polling the task before
            suspending, in milliseconds from when the call was sent. ``None``
            when the server sent none, or one this client cannot use; the
            caller then falls back to its own default. Like ``poll_interval_ms``
            it is a suggestion, and a caller's own setting takes precedence.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    job_key: str
    folder_key: Optional[str] = None
    suspend_after_ms: Optional[int] = None

    @field_validator("suspend_after_ms", mode="before")
    @classmethod
    def _is_a_duration(cls, value: Any) -> Optional[int]:
        """Keep a whole, non-negative number of milliseconds; drop anything else.

        It is only a hint, so a value that cannot be used does not cost the
        caller the job it could still suspend on.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        # An int is whole and finite whatever its size; asking ``math`` about
        # a very large one would overflow instead of answering.
        if isinstance(value, float) and not value.is_integer():
            return None
        if value < 0:
            return None
        return int(value)

    @field_validator("job_key", "folder_key")
    @classmethod
    def _is_a_key(cls, value: Optional[str]) -> Optional[str]:
        """Accept only a GUID.

        These values go into a resume trigger and an Orchestrator request, so a
        server answer that is not a key is refused here rather than passed on.
        """
        if value is None:
            return None
        return str(uuid.UUID(value))


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

    # A status the spec adds later must not break a poll in flight: an
    # unrecognized one stays a plain string, which no terminal check matches,
    # so the loop keeps polling instead of raising a ValidationError out of
    # somebody's hour-long wait. Known values are always the enum.
    status: Union[McpTaskStatus, str]

    status_message: Optional[str] = None
    created_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    ttl_ms: Optional[int] = None
    poll_interval_ms: Optional[int] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None

    # Client-side only: the MCP endpoint this task was minted by, so follow-up
    # tasks/get, cancel, and wait calls know where to go. Never serialized, and
    # never read off the wire either -- see _ignore_a_server_supplied_url.
    server_url: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _ignore_a_server_supplied_url(cls, data: Any) -> Any:
        """Drop ``serverUrl`` when it arrives as input data.

        This field is the client's own bookkeeping: the endpoint *we* sent the
        call to. Every follow-up carries the caller's bearer token, so a task
        payload that named its own endpoint would be a way to have this client
        post that token wherever the payload said. The server has no business
        setting it, and the camel-case spelling is the only one a payload can
        arrive in -- the Python name stays available to this client, which is
        how ``_task_from_result`` fills it in.
        """
        if isinstance(data, dict) and "serverUrl" in data:
            return {key: value for key, value in data.items() if key != "serverUrl"}
        return data

    @property
    def job(self) -> Optional[McpTaskJob]:
        """The Orchestrator job behind this task, when the server named one.

        ``None`` for a server that does not serve ``com.uipath/tasks`` (a
        tenant without it, a non-UiPath server), for a terminal task, and for
        an annotation this client cannot read -- in every such case the task is
        still pollable, there is just no job to suspend on.

        An annotation is read only at the version this client knows, and only
        when the trigger it names is a Job one. Anything else is a kind of
        resume this client does not implement, so the task is polled rather
        than suspended on by a guess.
        """
        if isinstance(self.status, McpTaskStatus) and self.status.is_terminal:
            # Whatever the server sent with it: a task that is over has no
            # running job, and a caller must not suspend on one that has ended.
            return None
        meta = (self.model_extra or {}).get("_meta")
        annotation = (
            meta.get(MCP_UIPATH_TASK_META_KEY) if isinstance(meta, dict) else None
        )
        if not isinstance(annotation, dict):
            return None
        version = annotation.get("version")
        if type(version) is not int or version != MCP_UIPATH_TASK_ANNOTATION_VERSION:
            return None
        trigger = annotation.get("resumeTrigger")
        if (
            not isinstance(trigger, dict)
            or trigger.get("triggerType") != MCP_UIPATH_TASK_JOB_TRIGGER
        ):
            return None
        try:
            return McpTaskJob.model_validate(annotation)
        except ValueError:
            return None

    def _annotation(self, trigger_type: str) -> Optional[dict[str, Any]]:
        """The ``com.uipath/task`` annotation of a working task, at this version."""
        if isinstance(self.status, McpTaskStatus) and self.status.is_terminal:
            return None
        meta = (self.model_extra or {}).get("_meta")
        annotation = (
            meta.get(MCP_UIPATH_TASK_META_KEY) if isinstance(meta, dict) else None
        )
        if not isinstance(annotation, dict):
            return None
        version = annotation.get("version")
        if type(version) is not int or version != MCP_UIPATH_TASK_ANNOTATION_VERSION:
            return None
        trigger = annotation.get("resumeTrigger")
        if not isinstance(trigger, dict) or trigger.get("triggerType") != trigger_type:
            return None
        return annotation

    @property
    def api_trigger(self) -> Optional[McpTaskApiTrigger]:
        """That this task can be suspended on through a watch, when it can.

        ``None`` for a task the server names a job for (``job``), for one with
        no annotation, for a terminal one, and for an annotation this client
        cannot read. The task is still pollable in every such case.
        """
        annotation = self._annotation(MCP_UIPATH_TASK_API_TRIGGER)
        if annotation is None:
            return None
        return McpTaskApiTrigger.model_validate(annotation)

    @property
    def watch(self) -> Optional[McpTaskWatch]:
        """The watch the server started on this task, from a ``watch_task`` reply.

        ``None`` when the reply names no watch, or one that cannot be used (an
        id that is not a GUID, a lifetime that is not a positive number): the
        caller keeps polling rather than suspend on a watch it cannot name or
        time.
        """
        annotation = self._annotation(MCP_UIPATH_TASK_API_TRIGGER)
        watch = annotation.get("watch") if annotation is not None else None
        if not isinstance(watch, dict):
            return None
        try:
            return McpTaskWatch.model_validate(watch)
        except ValueError:
            return None

    @field_validator("status", mode="before")
    @classmethod
    def _known_status_stays_typed(cls, value: Any) -> Any:
        """Map a known status onto the enum, leave an unknown one a string.

        Pydantic's union resolution would hand back a plain ``str`` for a value
        that is also a valid enum member, which would quietly break
        ``status.is_terminal`` for callers.
        """
        if isinstance(value, str) and not isinstance(value, McpTaskStatus):
            try:
                return McpTaskStatus(value)
            except ValueError:
                return value
        return value


class McpToolCallOutcome(BaseModel):
    """Either shape a task-capable ``tools/call`` can answer.

    ``result`` holds the plain CallToolResult object when the server answered
    synchronously; ``task`` holds the durable handle when it did not. Exactly
    one is set.
    """

    model_config = ConfigDict(extra="forbid")

    result: Optional[dict[str, Any]] = None
    task: Optional[McpTask] = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "McpToolCallOutcome":
        """Enforce the either/or the docstring promises."""
        if (self.result is None) == (self.task is None):
            raise ValueError(
                "An MCP tool call answers with either a result or a task, not both "
                "and not neither."
            )
        return self

    @property
    def is_task(self) -> bool:
        """Whether the server answered with a task handle instead of a result."""
        return self.task is not None


class McpToolCallError(Exception):
    """A JSON-RPC error answered an MCP request.

    ``status_code`` is the HTTP status the error arrived with, when it arrived
    on a non-2xx response. A server is free to answer a JSON-RPC error with a
    matching HTTP status, so the status is kept alongside the code: it is what
    says whether re-sending could help.
    """

    def __init__(
        self,
        code: int,
        message: str,
        data: Any = None,
        status_code: Optional[int] = None,
    ) -> None:
        """Initialize with the JSON-RPC error code, message, and optional data."""
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data
        self.status_code = status_code


class McpTaskFailedError(Exception):
    """The task reached ``failed``; carries the server's JSON-RPC error object."""

    def __init__(self, task: McpTask) -> None:
        """Initialize with the terminal task snapshot."""
        super().__init__(f"MCP task {task_ref(task.task_id)} failed: {task.error}")
        self.task = task


class McpTaskInputRequiredError(Exception):
    """The task is parked on ``input_required``, which a waiter cannot answer.

    Not a terminal status per the spec -- the task can still proceed once the
    input arrives -- but terminal for ``wait_for_task``, which has no way to
    supply it and would otherwise poll until the caller's timeout, or forever
    when there is none.
    """

    def __init__(self, task: McpTask) -> None:
        """Initialize with the parked task snapshot."""
        super().__init__(
            f"MCP task {task_ref(task.task_id)} requires additional input, "
            "which this client cannot provide."
        )
        self.task = task


class McpTaskCancelledError(Exception):
    """The task reached ``cancelled`` before producing a result."""

    def __init__(self, task: McpTask) -> None:
        """Initialize with the terminal task snapshot."""
        super().__init__(f"MCP task {task_ref(task.task_id)} was cancelled.")
        self.task = task
