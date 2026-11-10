import asyncio
import base64
import json
import time
from typing import Any, List, Optional
from urllib.parse import quote

import httpx
from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ..common._resource_identifier import resolve_retrieve_identifier
from ._folder_service import FolderService
from .mcp import McpServer
from .mcp_tasks import (
    MCP_TASK_RESULT_TYPE,
    MCP_TASKS_EXTENSION_ID,
    MCP_TASKS_PROTOCOL_VERSION,
    McpTask,
    McpTaskCancelledError,
    McpTaskFailedError,
    McpTaskStatus,
    McpToolCallError,
    McpToolCallOutcome,
)

_DEFAULT_POLL_INTERVAL_MS = 5000


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

        while True:
            terminal = self._terminal_result(snapshot)
            if terminal is not None:
                return terminal

            time.sleep(self._poll_delay_seconds(snapshot, deadline, timeout))
            snapshot = self.get_task(snapshot)

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

        while True:
            terminal = self._terminal_result(snapshot)
            if terminal is not None:
                return terminal

            await asyncio.sleep(self._poll_delay_seconds(snapshot, deadline, timeout))
            snapshot = await self.get_task_async(snapshot)

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
        return None

    @staticmethod
    def _poll_delay_seconds(
        snapshot: McpTask, deadline: Optional[float], timeout: Optional[float]
    ) -> float:
        delay = (snapshot.poll_interval_ms or _DEFAULT_POLL_INTERVAL_MS) / 1000.0
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"MCP task {snapshot.task_id} did not finish within {timeout} seconds."
                )
            delay = min(delay, remaining)
        return delay

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
                    "version": "1.0.0",
                },
                "io.modelcontextprotocol/clientCapabilities": {
                    "extensions": {MCP_TASKS_EXTENSION_ID: {}},
                },
            },
        }
        body = {
            "jsonrpc": "2.0",
            "id": self._mcp_request_id,
            "method": method,
            "params": params,
        }
        # The current protocol mirrors the method (and, for tools/call, the
        # Base64 routing name) into headers so gateways can route without
        # reading the body.
        headers = {
            "MCP-Protocol-Version": MCP_TASKS_PROTOCOL_VERSION,
            "Mcp-Method": method,
            "Accept": "application/json, text/event-stream",
        }
        if routing_name is not None:
            headers["Mcp-Name"] = base64.b64encode(routing_name.encode("utf-8")).decode(
                "ascii"
            )
        return body, headers

    def _send_mcp(
        self,
        server_url: str,
        method: str,
        params: dict[str, Any],
        routing_name: Optional[str] = None,
    ) -> dict[str, Any]:
        body, headers = self._mcp_rpc_envelope(method, params, routing_name)
        response = self.request("POST", server_url, json=body, headers=headers)
        return self._parse_mcp_envelope(response, method)

    async def _send_mcp_async(
        self,
        server_url: str,
        method: str,
        params: dict[str, Any],
        routing_name: Optional[str] = None,
    ) -> dict[str, Any]:
        body, headers = self._mcp_rpc_envelope(method, params, routing_name)
        response = await self.request_async(
            "POST", server_url, json=body, headers=headers
        )
        return self._parse_mcp_envelope(response, method)

    @staticmethod
    def _parse_mcp_envelope(response: httpx.Response, method: str) -> dict[str, Any]:
        """The JSON-RPC envelope, whether framed as plain JSON or one SSE event."""
        text = response.text
        if "text/event-stream" in response.headers.get("content-type", ""):
            data_lines: list[str] = []
            for line in text.replace("\r\n", "\n").split("\n"):
                if not line and data_lines:
                    break
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if not data_lines:
                raise McpToolCallError(
                    0, f"The MCP SSE response to '{method}' had no data event."
                )
            text = "\n".join(data_lines)

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
