import asyncio
import base64
import importlib.metadata
import json
import random
import time
from typing import Any, Callable, List, Literal, Optional, cast
from urllib.parse import quote

import httpx
from tenacity import retry_if_exception, stop_after_attempt
from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ..common._resource_identifier import resolve_retrieve_identifier
from ..common.retry import (
    MAX_RETRY_ATTEMPTS,
    RETRYABLE_STATUS_CODES,
    extract_retry_after_from_chain,
)
from ..errors import EnrichedException
from ._folder_service import FolderService
from .mcp import McpServer
from .mcp_tasks import (
    MCP_TASK_RESULT_TYPE,
    MCP_TASKS_EXTENSION_ID,
    MCP_TASKS_PROTOCOL_VERSION,
    MCP_UIPATH_TASKS_CAPABILITY,
    MCP_UIPATH_TASKS_EXTENSION_ID,
    McpTask,
    McpTaskCancelledError,
    McpTaskFailedError,
    McpTaskInputRequiredError,
    McpTaskStatus,
    McpToolCallError,
    McpToolCallOutcome,
    task_ref,
)


def _sdk_version() -> str:
    """This package's version, for the MCP ``clientInfo`` block."""
    try:
        return importlib.metadata.version("uipath-platform")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


_HEADER_BASE64_PREFIX = "=?base64?"
_HEADER_BASE64_SUFFIX = "?="


def _encode_header_value(value: str) -> str:
    """Encode one value for an MCP HTTP header, per SEP-2243.

    The encoding is conditional, not unconditional: a value that is plain
    printable ASCII travels verbatim, because these headers exist so a gateway
    can route on them *without* decoding anything or reading the body. Only a
    value HTTP cannot carry -- non-ASCII, a control character, significant
    leading or trailing whitespace -- is Base64'd, inside the
    ``=?base64?...?=`` sentinel that tells the receiver which of the two it got.
    A value that already looks like the sentinel is encoded too, so the two
    cases stay distinguishable.

    Sending bare Base64 is therefore not a safe shortcut: the receiver finds no
    sentinel, takes the blob to *be* the value, and the server's header/body
    cross-check fails on every call.
    """
    needs_base64 = (
        value[:1] in (" ", "\t")
        or value[-1:] in (" ", "\t")
        or (
            value.startswith(_HEADER_BASE64_PREFIX)
            and value.endswith(_HEADER_BASE64_SUFFIX)
        )
        or any(character < "\x20" or character > "\x7e" for character in value)
    )
    if not needs_base64:
        return value

    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"{_HEADER_BASE64_PREFIX}{encoded}{_HEADER_BASE64_SUFFIX}"


_DEFAULT_POLL_INTERVAL_MS = 5000

#: Floor under the server's poll interval. A server that asks to be polled
#: every millisecond gets a hot loop otherwise.
_MIN_POLL_INTERVAL_SECONDS = 0.1

#: Ceiling on one ``tasks/get`` request, independent of how much budget is
#: left. Bounding a poll by the whole remaining budget makes a stalled
#: connection cost the entire wait: an hour-long timeout would sit on one
#: black-holed socket for an hour and then report the task as unfinished,
#: while the same stall with no timeout at all is noticed in 30 seconds and
#: re-polled. The poll loop is the retry, so each attempt only needs to be
#: long enough for a healthy server to answer.
_MAX_POLL_REQUEST_SECONDS = 30.0

#: Backoff between consecutive failed polls, so a throttled or briefly broken
#: server is not hammered at the poll interval.
_POLL_BACKOFF_INITIAL_SECONDS = 1.0
_MAX_POLL_BACKOFF_SECONDS = 30.0

#: JSON-RPC internal error. On a poll it says the server could not answer
#: *this* question, not that the task is gone, so the loop asks again.
_JSONRPC_INTERNAL_ERROR = -32603

# Consecutive failed polls tolerated by a wait with *no* deadline. Polls
# bypass the platform retry policy (see ``_get_task_within``), so this is what
# stops an unreachable server from being polled forever. A wait that was given
# a timeout is bounded by that timeout instead and keeps absorbing transient
# failures until it expires -- a caller who asked to wait an hour meant to ride
# out a blip, not to be handed the first one.
_MAX_POLL_FAILURES = MAX_RETRY_ATTEMPTS

#: How a failed MCP request may be re-sent.
#:
#: ``platform`` is the service-wide policy: five attempts, retrying read
#: timeouts and 408/429/5xx. That is correct for a request the server can only
#: have read or not read -- and wrong for one that *starts work*. A read
#: timeout means the server received the request; the 30-second client timeout
#: or a gateway 504 says nothing about whether it already created an
#: Orchestrator job. So ``tools/call`` uses ``connect-only``: a failed connect
#: never left the client, and nothing else is re-sent. ``never`` is for a poll,
#: whose retry is the poll loop itself.
ResendPolicy = Literal["platform", "connect-only", "never"]


class McpService(FolderContext, BaseService):
    """Service for managing MCP (Model Context Protocol) servers in UiPath.

    MCP servers provide contextual information and capabilities that can be used
    by AI agents and automation processes.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    @traced(name="mcp_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: str | None = None,
    ) -> List[McpServer]:
        """List all MCP servers.

        Args:
            folder_path (Optional[str]): The path of the folder to list servers from.

        Returns:
            List[McpServer]: A list of MCP servers with their configuration.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            servers = client.mcp.list(folder_path="MyFolder")
            for server in servers:
                print(f"{server.name} - {server.slug}")
            ```
        """
        spec = self._list_spec(
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return [McpServer.model_validate(server) for server in response.json()]

    @traced(name="mcp_list_async", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: str | None = None,
    ) -> List[McpServer]:
        """Asynchronously list all MCP servers.

        Args:
            folder_path (Optional[str]): The path of the folder to list servers from.

        Returns:
            List[McpServer]: A list of MCP servers with their configuration.

        Examples:
            ```python
            import asyncio

            from uipath import UiPath

            sdk = UiPath()

            async def main():
                servers = await sdk.mcp.list_async(folder_path="MyFolder")
                for server in servers:
                    print(f"{server.name} - {server.slug}")

            asyncio.run(main())
            ```
        """
        spec = self._list_spec(
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return [McpServer.model_validate(server) for server in response.json()]

    @resource_override(resource_type="mcpServer", resource_identifier="name")
    @resource_override(resource_type="mcpServer", resource_identifier="slug")
    @traced(name="mcp_retrieve", run_type="uipath")
    def retrieve(
        self,
        slug: str | None = None,
        *,
        name: str | None = None,
        folder_path: str | None = None,
    ) -> McpServer:
        """Retrieve a specific MCP server by its display name or legacy slug.

        Args:
            slug (Optional[str]): The legacy slug identifier of the server.
            name (Optional[str]): The display name of the server.
            folder_path (Optional[str]): The path of the folder where the server is located.

        Returns:
            McpServer: The MCP server configuration.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            server = client.mcp.retrieve(name="My Server", folder_path="MyFolder")
            print(f"Server: {server.name}, URL: {server.mcp_url}")
            ```
        """
        identifier = resolve_retrieve_identifier(name=name, slug=slug)
        spec = self._retrieve_spec(
            name=identifier,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return McpServer.model_validate(response.json())

    @resource_override(resource_type="mcpServer", resource_identifier="name")
    @resource_override(resource_type="mcpServer", resource_identifier="slug")
    @traced(name="mcp_retrieve_async", run_type="uipath")
    async def retrieve_async(
        self,
        slug: str | None = None,
        *,
        name: str | None = None,
        folder_path: str | None = None,
    ) -> McpServer:
        """Asynchronously retrieve an MCP server by its display name or legacy slug.

        Args:
            slug (Optional[str]): The legacy slug identifier of the server.
            name (Optional[str]): The display name of the server.
            folder_path (Optional[str]): The path of the folder where the server is located.

        Returns:
            McpServer: The MCP server configuration.

        Examples:
            ```python
            import asyncio

            from uipath import UiPath

            sdk = UiPath()

            async def main():
                server = await sdk.mcp.retrieve_async(name="My Server", folder_path="MyFolder")
                print(f"Server: {server.name}, URL: {server.mcp_url}")

            asyncio.run(main())
            ```
        """
        identifier = resolve_retrieve_identifier(name=name, slug=slug)
        spec = self._retrieve_spec(
            name=identifier,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return McpServer.model_validate(response.json())

    @property
    def custom_headers(self) -> dict[str, str]:
        return self.folder_headers

    def _resolve_folder_key(self, folder_path: str | None) -> str | None:
        """Resolve folder key from folder_path, falling back to FolderContext."""
        if folder_path is not None:
            return self._folders_service.retrieve_folder_key(folder_path)

        return self._folder_key

    def _list_spec(
        self,
        *,
        folder_path: str | None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_path)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/agenthub_/api/servers"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _retrieve_spec(
        self,
        name: str,
        *,
        folder_path: str | None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_path)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/agenthub_/api/servers/{quote(name, safe='')}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    # ------------------------------------------------------------------
    # MCP Tasks extension (io.modelcontextprotocol/tasks)
    #
    # A long-running tools/call on a UiPath MCP server can return a durable
    # task handle instead of holding the request open; the handle is polled
    # via tasks/get until terminal. These methods speak the stateless
    # 2026-07-28 per-request protocol revision directly — the only revision
    # the extension is served on — so no initialize handshake or session is
    # involved.
    # ------------------------------------------------------------------

    @traced(name="mcp_call_tool", run_type="uipath")
    def call_tool(
        self,
        slug: str,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        *,
        folder_path: str | None = None,
    ) -> McpToolCallOutcome:
        """Call a tool on an MCP server, accepting a task handle for long-running calls.

        Declares the MCP Tasks extension on the request; the server decides
        per call whether to answer synchronously or with a durable task.

        Args:
            slug (str): The MCP server's slug or display name.
            tool_name (str): The MCP tool to invoke.
            arguments (Optional[dict[str, Any]]): The tool arguments.
            folder_path (Optional[str]): The folder the server lives in.

        Returns:
            McpToolCallOutcome: Either the plain CallToolResult (``result``)
                or the durable handle to poll (``task``).

        Raises:
            McpToolCallError: If the server answers with a JSON-RPC error.
        """
        server_url = self._resolve_mcp_url(slug, folder_path=folder_path)
        result = self._send_mcp(
            server_url,
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            routing_name=tool_name,
            resend="connect-only",
        )
        return self._outcome_from_result(result, server_url)

    @traced(name="mcp_call_tool", run_type="uipath")
    async def call_tool_async(
        self,
        slug: str,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        *,
        folder_path: str | None = None,
    ) -> McpToolCallOutcome:
        """Asynchronously call a tool on an MCP server, accepting a task handle.

        Args:
            slug (str): The MCP server's slug or display name.
            tool_name (str): The MCP tool to invoke.
            arguments (Optional[dict[str, Any]]): The tool arguments.
            folder_path (Optional[str]): The folder the server lives in.

        Returns:
            McpToolCallOutcome: Either the plain CallToolResult (``result``)
                or the durable handle to poll (``task``).

        Raises:
            McpToolCallError: If the server answers with a JSON-RPC error.
        """
        server_url = await self._resolve_mcp_url_async(slug, folder_path=folder_path)
        result = await self._send_mcp_async(
            server_url,
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            routing_name=tool_name,
            resend="connect-only",
        )
        return self._outcome_from_result(result, server_url)

    @traced(name="mcp_get_task", run_type="uipath")
    def get_task(self, task: McpTask) -> McpTask:
        """Poll the current state of an MCP task once.

        Args:
            task (McpTask): A handle returned by ``call_tool`` (or an earlier poll).

        Returns:
            McpTask: The fresh task snapshot; ``result`` is set once completed.

        Raises:
            McpToolCallError: If the task id is unknown or expired.
        """
        server_url = self._require_server_url(task)
        result = self._send_mcp(server_url, "tasks/get", {"taskId": task.task_id})
        return self._task_from_result(result, server_url)

    @traced(name="mcp_get_task", run_type="uipath")
    async def get_task_async(self, task: McpTask) -> McpTask:
        """Asynchronously poll the current state of an MCP task once.

        Args:
            task (McpTask): A handle returned by ``call_tool_async`` (or an earlier poll).

        Returns:
            McpTask: The fresh task snapshot; ``result`` is set once completed.

        Raises:
            McpToolCallError: If the task id is unknown or expired.
        """
        server_url = self._require_server_url(task)
        result = await self._send_mcp_async(
            server_url, "tasks/get", {"taskId": task.task_id}
        )
        return self._task_from_result(result, server_url)

    @traced(name="mcp_cancel_task", run_type="uipath")
    def cancel_task(self, task: McpTask) -> None:
        """Signal cancellation of an MCP task.

        Cancellation is cooperative: the server acknowledges the intent and
        the next poll reports the state the underlying job actually reached.

        Args:
            task (McpTask): The task to cancel.
        """
        server_url = self._require_server_url(task)
        self._send_mcp(server_url, "tasks/cancel", {"taskId": task.task_id})

    @traced(name="mcp_cancel_task", run_type="uipath")
    async def cancel_task_async(self, task: McpTask) -> None:
        """Asynchronously signal cancellation of an MCP task.

        Args:
            task (McpTask): The task to cancel.
        """
        server_url = self._require_server_url(task)
        await self._send_mcp_async(server_url, "tasks/cancel", {"taskId": task.task_id})

    @traced(name="mcp_wait_for_task", run_type="uipath")
    def wait_for_task(
        self,
        task: McpTask,
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Poll an MCP task until terminal, honoring the server's poll interval.

        Args:
            task (McpTask): The handle to wait on.
            timeout (Optional[float]): Seconds to wait before raising
                ``TimeoutError``. The task keeps running server-side on
                timeout; call ``cancel_task`` if that is not wanted.

        Returns:
            dict[str, Any]: The completed task's CallToolResult object.

        Raises:
            McpTaskFailedError: If the task reaches ``failed``.
            McpTaskCancelledError: If the task reaches ``cancelled``.
            TimeoutError: If ``timeout`` elapses first.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        snapshot = task
        failures = 0
        retry_after: Optional[float] = None

        while True:
            terminal = self._terminal_result(snapshot)
            if terminal is not None:
                return terminal

            time.sleep(
                self._poll_delay_seconds(
                    snapshot, deadline, timeout, failures, retry_after
                )
            )
            budget = self._poll_budget_seconds(snapshot, deadline, timeout)
            try:
                snapshot = self._get_task_within(snapshot, budget)
            except (
                httpx.TransportError,
                EnrichedException,
                McpToolCallError,
            ) as failure:
                failures = self._poll_failure(
                    snapshot, failure, failures, deadline, timeout
                )
                retry_after = extract_retry_after_from_chain(failure)
            else:
                failures = 0
                retry_after = None

    @traced(name="mcp_wait_for_task", run_type="uipath")
    async def wait_for_task_async(
        self,
        task: McpTask,
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Asynchronously poll an MCP task until terminal.

        Args:
            task (McpTask): The handle to wait on.
            timeout (Optional[float]): Seconds to wait before raising
                ``TimeoutError``. The task keeps running server-side on
                timeout; call ``cancel_task_async`` if that is not wanted.

        Returns:
            dict[str, Any]: The completed task's CallToolResult object.

        Raises:
            McpTaskFailedError: If the task reaches ``failed``.
            McpTaskCancelledError: If the task reaches ``cancelled``.
            TimeoutError: If ``timeout`` elapses first.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        snapshot = task
        failures = 0
        retry_after: Optional[float] = None

        while True:
            terminal = self._terminal_result(snapshot)
            if terminal is not None:
                return terminal

            await asyncio.sleep(
                self._poll_delay_seconds(
                    snapshot, deadline, timeout, failures, retry_after
                )
            )
            budget = self._poll_budget_seconds(snapshot, deadline, timeout)
            try:
                snapshot = await self._get_task_within_async(snapshot, budget)
            except (
                httpx.TransportError,
                EnrichedException,
                McpToolCallError,
            ) as failure:
                failures = self._poll_failure(
                    snapshot, failure, failures, deadline, timeout
                )
                retry_after = extract_retry_after_from_chain(failure)
            else:
                failures = 0
                retry_after = None

    @traced(name="mcp_call_tool_and_wait", run_type="uipath")
    def call_tool_and_wait(
        self,
        slug: str,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        *,
        folder_path: str | None = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Call an MCP tool and always return the final result, task or not.

        Args:
            slug (str): The MCP server's slug or display name.
            tool_name (str): The MCP tool to invoke.
            arguments (Optional[dict[str, Any]]): The tool arguments.
            folder_path (Optional[str]): The folder the server lives in.
            timeout (Optional[float]): Seconds to wait for a task to finish.

        Returns:
            dict[str, Any]: The CallToolResult object.

        Examples:
            ```python
            from uipath import UiPath

            sdk = UiPath()

            result = sdk.mcp.call_tool_and_wait(
                "my-server", "invoke-long-process", {"input": "..."}, timeout=3600
            )
            print(result["content"][0]["text"])
            ```
        """
        outcome = self.call_tool(slug, tool_name, arguments, folder_path=folder_path)
        if outcome.task is None:
            return outcome.result or {}
        return self.wait_for_task(outcome.task, timeout=timeout)

    @traced(name="mcp_call_tool_and_wait", run_type="uipath")
    async def call_tool_and_wait_async(
        self,
        slug: str,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        *,
        folder_path: str | None = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Asynchronously call an MCP tool and always return the final result.

        Args:
            slug (str): The MCP server's slug or display name.
            tool_name (str): The MCP tool to invoke.
            arguments (Optional[dict[str, Any]]): The tool arguments.
            folder_path (Optional[str]): The folder the server lives in.
            timeout (Optional[float]): Seconds to wait for a task to finish.

        Returns:
            dict[str, Any]: The CallToolResult object.
        """
        outcome = await self.call_tool_async(
            slug, tool_name, arguments, folder_path=folder_path
        )
        if outcome.task is None:
            return outcome.result or {}
        return await self.wait_for_task_async(outcome.task, timeout=timeout)

    def _resolve_mcp_url(self, slug: str, *, folder_path: str | None) -> str:
        server = self.retrieve(slug, folder_path=folder_path)
        if not server.mcp_url:
            raise McpToolCallError(0, f"MCP server '{slug}' exposes no MCP URL.")
        return server.mcp_url

    async def _resolve_mcp_url_async(
        self, slug: str, *, folder_path: str | None
    ) -> str:
        server = await self.retrieve_async(slug, folder_path=folder_path)
        if not server.mcp_url:
            raise McpToolCallError(0, f"MCP server '{slug}' exposes no MCP URL.")
        return server.mcp_url

    @staticmethod
    def _require_server_url(task: McpTask) -> str:
        if not task.server_url:
            raise McpToolCallError(
                0,
                "The task carries no server URL; use a handle returned by call_tool.",
            )
        return task.server_url

    def _outcome_from_result(
        self, result: dict[str, Any], server_url: str
    ) -> McpToolCallOutcome:
        if result.get("resultType") == MCP_TASK_RESULT_TYPE:
            return McpToolCallOutcome(task=self._task_from_result(result, server_url))
        return McpToolCallOutcome(result=result)

    @staticmethod
    def _task_from_result(result: dict[str, Any], server_url: str) -> McpTask:
        task = McpTask.model_validate(result)
        task.server_url = server_url
        return task

    def _terminal_result(self, snapshot: McpTask) -> Optional[dict[str, Any]]:
        """The completed result, None while running, raising on failure states."""
        if snapshot.status == McpTaskStatus.COMPLETED:
            return snapshot.result or {}
        if snapshot.status == McpTaskStatus.FAILED:
            raise McpTaskFailedError(snapshot)
        if snapshot.status == McpTaskStatus.CANCELLED:
            raise McpTaskCancelledError(snapshot)
        if snapshot.status == McpTaskStatus.INPUT_REQUIRED:
            # Not terminal per spec, but terminal for a *waiter*: nothing here
            # can answer an elicitation, and `timeout` defaults to None, so
            # polling on would mean polling forever. The handle rides on the
            # error, so a caller that can answer still has it.
            raise McpTaskInputRequiredError(snapshot)
        return None

    @staticmethod
    def _poll_delay_seconds(
        snapshot: McpTask,
        deadline: Optional[float],
        timeout: Optional[float],
        failures: int = 0,
        retry_after: Optional[float] = None,
    ) -> float:
        """How long to wait before the next poll.

        The server's interval is the baseline, floored so a zero or
        one-millisecond interval cannot turn the loop into a spin. After a
        failed poll the wait is whichever is longer: a ``Retry-After`` the
        server asked for, or exponential backoff on the consecutive failure
        count -- so a throttled server is not polled at full rate while it is
        asking for room. The deadline still clamps the result, which is also
        where an exhausted budget is noticed.
        """
        delay = max(
            (snapshot.poll_interval_ms or _DEFAULT_POLL_INTERVAL_MS) / 1000.0,
            _MIN_POLL_INTERVAL_SECONDS,
        )
        if failures:
            delay = max(delay, McpService._poll_backoff_seconds(failures))
        if retry_after is not None:
            delay = max(delay, retry_after)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpService._task_timeout(snapshot, timeout)
            delay = min(delay, remaining)
        return delay

    @staticmethod
    def _task_timeout(snapshot: McpTask, timeout: Optional[float]) -> TimeoutError:
        """The uniform timeout, naming the task so the caller can still poll or cancel it."""
        return TimeoutError(
            f"MCP task {task_ref(snapshot.task_id)} did not finish "
            f"within {timeout} seconds."
        )

    @staticmethod
    def _poll_backoff_seconds(failures: int) -> float:
        """Backoff after *failures* consecutive failed polls.

        Doubling, capped, and jittered proportionally: many agent jobs can be
        waiting on the same server, and a shared outage would otherwise have
        all of them re-poll in lockstep.
        """
        doubling = _POLL_BACKOFF_INITIAL_SECONDS * (2 ** (failures - 1))
        return min(doubling, _MAX_POLL_BACKOFF_SECONDS) * random.uniform(0.5, 1.0)

    @staticmethod
    def _poll_budget_seconds(
        snapshot: McpTask, deadline: Optional[float], timeout: Optional[float]
    ) -> Optional[float]:
        """What is left of the caller's budget, as a bound for one poll request.

        Checked after the inter-poll sleep: a sleep clamped to the deadline
        would otherwise be followed by an unbounded request, letting a slow or
        stalled ``tasks/get`` answer long after the budget expired.

        The bound is what makes ``timeout`` a hard deadline rather than a
        hint, together with polls bypassing the platform retry policy: see
        :meth:`_get_task_within`. It is also capped at
        ``_MAX_POLL_REQUEST_SECONDS`` so that a long deadline does not turn one
        stalled connection into the whole wait.
        """
        if deadline is None:
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise McpService._task_timeout(snapshot, timeout)
        return min(remaining, _MAX_POLL_REQUEST_SECONDS)

    def _poll_failure(
        self,
        snapshot: McpTask,
        failure: Exception,
        failures: int,
        deadline: Optional[float],
        timeout: Optional[float],
    ) -> int:
        """Handle a failed poll: re-raise it, or count it and poll on.

        What ends the wait is the deadline, not the failure: a timeout, a
        gateway error or a 429 says nothing about the task, which is still
        running on the server. So a transient failure is left to the loop,
        which re-sends ``tasks/get`` on its own cadence -- the platform retry
        policy is off for polls precisely so that retrying cannot outlive the
        deadline -- and only an expired budget becomes ``TimeoutError``.

        The consecutive-failure cap applies to a wait with *no* deadline,
        where it is the only thing standing between the loop and a server
        that is simply gone. A wait that was given a timeout keeps absorbing
        until that timeout expires: a caller who asked for an hour meant to
        ride out a blip.

        Returns:
            int: The new consecutive-failure count.

        Raises:
            TimeoutError: When the deadline has passed.
            Exception: The failure itself, when it is not transient, or when
                an open-ended wait reaches the cap.
        """
        if deadline is not None and time.monotonic() >= deadline:
            raise self._task_timeout(snapshot, timeout) from failure

        failures += 1
        if not self._poll_is_transient(failure):
            raise failure
        if deadline is None and failures >= _MAX_POLL_FAILURES:
            raise failure

        self._logger.warning(
            f"Transient failure polling MCP task {task_ref(snapshot.task_id)} "
            f"(consecutive failure {failures}): {failure}"
        )
        return failures

    @staticmethod
    def _poll_is_transient(failure: Exception) -> bool:
        """Whether *failure* leaves the task worth asking about again.

        A poll reads state and starts nothing, so anything that looks like the
        answer went missing is worth re-asking: every transport failure, every
        5xx (not only the subset the platform policy retries -- a plain 500 on
        one poll is no verdict on the task), and a JSON-RPC internal error,
        which is the same thing arriving inside a 200. A 4xx other than 408 or
        429, and any other JSON-RPC code, are answers rather than mishaps: the
        task id is unknown, the method is not there, the caller is not allowed.
        """
        if isinstance(failure, httpx.TransportError):
            return True

        status: Optional[int] = None
        if isinstance(failure, EnrichedException):
            status = failure.status_code
        elif isinstance(failure, McpToolCallError):
            if failure.code == _JSONRPC_INTERNAL_ERROR:
                return True
            status = failure.status_code

        if status is None:
            return False
        return status in RETRYABLE_STATUS_CODES or 500 <= status < 600

    @staticmethod
    def _never_reached_the_server(exception: BaseException) -> bool:
        """Whether *exception* proves the request was never delivered.

        A connect that failed, timed out, or never got a pool slot did not
        put the request on the wire, so re-sending cannot duplicate anything.
        Everything else the platform policy retries -- a read timeout, a 429,
        a gateway 5xx -- is consistent with the server having received the
        request and started work on it.
        """
        return isinstance(
            exception,
            (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout),
        )

    def _sender(self, resend: ResendPolicy) -> Callable[..., httpx.Response]:
        """The ``request`` variant implementing *resend*."""
        if resend == "platform":
            return self.request
        request = cast(Any, type(self).request)
        if resend == "never":
            narrowed = request.retry_with(stop=stop_after_attempt(1))
        else:
            narrowed = request.retry_with(
                retry=retry_if_exception(McpService._never_reached_the_server)
            )
        return lambda *args, **kwargs: cast(
            httpx.Response, narrowed(self, *args, **kwargs)
        )

    def _sender_async(self, resend: ResendPolicy) -> Callable[..., Any]:
        """The ``request_async`` variant implementing *resend*."""
        if resend == "platform":
            return self.request_async
        request = cast(Any, type(self).request_async)
        if resend == "never":
            narrowed = request.retry_with(stop=stop_after_attempt(1))
        else:
            narrowed = request.retry_with(
                retry=retry_if_exception(McpService._never_reached_the_server)
            )
        return lambda *args, **kwargs: narrowed(self, *args, **kwargs)

    def _get_task_within(self, task: McpTask, budget: Optional[float]) -> McpTask:
        """``get_task``, bounded by *budget* seconds and tried exactly once.

        The platform retry policy is deliberately off: it re-sends a timed-out
        request up to ``MAX_RETRY_ATTEMPTS`` times with exponential backoff
        between them, which -- even with every attempt bounded -- lands the
        answer long after the caller's deadline. The poll loop is the retry
        instead; it re-sends on the task's own cadence and re-checks the
        deadline every time.
        """
        server_url = self._require_server_url(task)
        result = self._send_mcp(
            server_url,
            "tasks/get",
            {"taskId": task.task_id},
            request_timeout=budget,
            resend="never",
        )
        return self._task_from_result(result, server_url)

    async def _get_task_within_async(
        self, task: McpTask, budget: Optional[float]
    ) -> McpTask:
        """``get_task_async``, bounded by *budget* and tried exactly once.

        See :meth:`_get_task_within` for why the retry policy is off here.
        """
        server_url = self._require_server_url(task)
        result = await self._send_mcp_async(
            server_url,
            "tasks/get",
            {"taskId": task.task_id},
            request_timeout=budget,
            resend="never",
        )
        return self._task_from_result(result, server_url)

    def _mcp_rpc_envelope(
        self, method: str, params: dict[str, Any], routing_name: Optional[str]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        self._mcp_request_id = getattr(self, "_mcp_request_id", 0) + 1
        params = {
            **params,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": MCP_TASKS_PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientInfo": {
                    "name": "UiPath.Python.Sdk",
                    "version": _sdk_version(),
                },
                "io.modelcontextprotocol/clientCapabilities": {
                    # Both names of the one protocol. The UiPath one asks
                    # the server to also name the job behind a task
                    # (McpTask.job), and says which resume triggers this
                    # client can suspend on; a server without it ignores
                    # the entry.
                    "extensions": {
                        MCP_TASKS_EXTENSION_ID: {},
                        MCP_UIPATH_TASKS_EXTENSION_ID: MCP_UIPATH_TASKS_CAPABILITY,
                    },
                },
            },
        }
        body = {
            "jsonrpc": "2.0",
            "id": self._mcp_request_id,
            "method": method,
            "params": params,
        }
        # The current protocol mirrors the method (and, for the routed
        # methods, the name or uri being addressed) into headers so gateways can
        # route without reading the body.
        headers = {
            "MCP-Protocol-Version": MCP_TASKS_PROTOCOL_VERSION,
            "Mcp-Method": method,
            "Accept": "application/json, text/event-stream",
        }
        if routing_name is not None:
            headers["Mcp-Name"] = _encode_header_value(routing_name)
        return body, headers

    def _send_mcp(
        self,
        server_url: str,
        method: str,
        params: dict[str, Any],
        routing_name: Optional[str] = None,
        request_timeout: Optional[float] = None,
        resend: ResendPolicy = "platform",
    ) -> dict[str, Any]:
        body, headers = self._mcp_rpc_envelope(method, params, routing_name)
        extra: dict[str, Any] = (
            {} if request_timeout is None else {"timeout": request_timeout}
        )
        send = self._sender(resend)
        try:
            response = send("POST", server_url, json=body, headers=headers, **extra)
        except EnrichedException as failure:
            # Bare re-raise when there is no JSON-RPC error to recover: `raise
            # failure from failure` would make the exception its own __cause__,
            # and anything walking that chain (the Retry-After lookup, for one)
            # would never come back.
            recovered = self._jsonrpc_error_in(failure)
            if recovered is None:
                raise
            raise recovered from failure
        return self._parse_mcp_envelope(response, method, body["id"])

    async def _send_mcp_async(
        self,
        server_url: str,
        method: str,
        params: dict[str, Any],
        routing_name: Optional[str] = None,
        request_timeout: Optional[float] = None,
        resend: ResendPolicy = "platform",
    ) -> dict[str, Any]:
        body, headers = self._mcp_rpc_envelope(method, params, routing_name)
        extra: dict[str, Any] = (
            {} if request_timeout is None else {"timeout": request_timeout}
        )
        send = self._sender_async(resend)
        try:
            response = await send(
                "POST", server_url, json=body, headers=headers, **extra
            )
        except EnrichedException as failure:
            recovered = self._jsonrpc_error_in(failure)
            if recovered is None:
                raise
            raise recovered from failure
        return self._parse_mcp_envelope(response, method, body["id"])

    @staticmethod
    def _jsonrpc_error_in(failure: EnrichedException) -> Optional[McpToolCallError]:
        """The JSON-RPC error a non-2xx response carried, if it carried one.

        ``request`` raises on status before the body is ever parsed, so a
        server that answered "no such method" in JSON-RPC and mapped it onto
        404 would otherwise reach the caller as a bare HTTP error with the
        code and message dropped -- while every docstring here promises
        ``McpToolCallError``. The status rides along on the error, because it
        is what says whether asking again could help, and the HTTP failure
        stays the ``__cause__`` so a ``Retry-After`` is still reachable.
        """
        cause: Optional[BaseException] = failure
        while cause is not None and not isinstance(cause, httpx.HTTPStatusError):
            cause = cause.__cause__
        if cause is None:
            return None

        try:
            envelope = json.loads(cause.response.text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(envelope, dict) or not isinstance(
            envelope.get("error"), dict
        ):
            return None

        error = envelope["error"]
        return McpToolCallError(
            code=error.get("code", 0),
            message=error.get("message", "Unknown MCP error"),
            data=error.get("data"),
            status_code=failure.status_code,
        )

    @staticmethod
    def _sse_data_events(text: str) -> List[str]:
        """The payload of every ``data:`` event in an SSE body, in order."""
        events: List[str] = []
        data_lines: List[str] = []
        for line in text.replace("\r\n", "\n").split("\n"):
            if not line:
                if data_lines:
                    events.append("\n".join(data_lines))
                    data_lines = []
                continue
            if line.startswith("data:"):
                # Exactly one optional space after the colon belongs to the
                # framing; the rest of the line is payload.
                payload = line[5:]
                data_lines.append(payload[1:] if payload.startswith(" ") else payload)
        if data_lines:
            events.append("\n".join(data_lines))
        return events

    @staticmethod
    def _sse_response_envelope(
        text: str, method: str, request_id: Optional[Any] = None
    ) -> dict[str, Any]:
        """The JSON-RPC response carried by an SSE body.

        A stream may deliver notifications, and server-initiated requests,
        before the response to our own call, so every event is parsed and the
        answer is picked by id. Reading only the first event would take a
        leading notification for the answer and then report a perfectly good
        result as missing; taking the first event that merely carries
        ``result`` or ``error`` would accept the answer to somebody else's
        request.
        """
        events = McpService._sse_data_events(text)
        if not events:
            raise McpToolCallError(
                0, f"The MCP SSE response to '{method}' had no data event."
            )

        for payload in events:
            try:
                candidate = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(candidate, dict) or not (
                "result" in candidate or "error" in candidate
            ):
                continue
            if request_id is not None and "id" in candidate:
                # Compared as text: JSON-RPC allows a string or a number, and
                # a server is free to echo ours as either.
                if str(candidate["id"]) != str(request_id):
                    continue
            return candidate

        raise McpToolCallError(
            0, f"The MCP SSE response to '{method}' carried no JSON-RPC response."
        )

    @staticmethod
    def _parse_mcp_envelope(
        response: httpx.Response, method: str, request_id: Optional[Any] = None
    ) -> dict[str, Any]:
        """The JSON-RPC envelope, whether framed as plain JSON or SSE."""
        text = response.text
        envelope: Any
        if "text/event-stream" in response.headers.get("content-type", ""):
            envelope = McpService._sse_response_envelope(text, method, request_id)
        else:
            try:
                envelope = json.loads(text)
            except json.JSONDecodeError:
                raise McpToolCallError(
                    0, f"The MCP response to '{method}' was not JSON."
                ) from None

        if not isinstance(envelope, dict):
            raise McpToolCallError(
                0, f"The MCP response to '{method}' was not an envelope."
            )

        if "error" in envelope:
            error = envelope["error"] or {}
            raise McpToolCallError(
                code=error.get("code", 0),
                message=error.get("message", "Unknown MCP error"),
                data=error.get("data"),
            )

        result = envelope.get("result")
        if not isinstance(result, dict):
            raise McpToolCallError(
                0, f"The MCP response to '{method}' carried no result object."
            )

        return result
