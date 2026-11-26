import base64
import json
import time
from typing import Any, Optional

import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common.retry import extract_retry_after_from_chain
from uipath.platform.orchestrator import McpService, _mcp_service
from uipath.platform.orchestrator._folder_service import FolderService
from uipath.platform.orchestrator.mcp_tasks import (
    McpTask,
    McpTaskCancelledError,
    McpTaskFailedError,
    McpTaskInputRequiredError,
    McpTaskStatus,
    McpToolCallError,
    McpToolCallOutcome,
    task_ref,
)

MCP_URL = "https://test.com/mcp/folder-key/test-mcp-server"


@pytest.fixture(autouse=True)
def quick_poll_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the inter-failure backoff so the retry paths run in milliseconds."""
    monkeypatch.setattr(_mcp_service, "_POLL_BACKOFF_INITIAL_SECONDS", 0.001)
    monkeypatch.setattr(_mcp_service, "_MIN_POLL_INTERVAL_SECONDS", 0.001)


@pytest.fixture
def folders_service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FolderService:
    monkeypatch.setenv("UIPATH_FOLDER_KEY", "test-folder-key")
    return FolderService(config=config, execution_context=execution_context)


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    folders_service: FolderService,
    monkeypatch: pytest.MonkeyPatch,
) -> McpService:
    monkeypatch.setenv("UIPATH_FOLDER_KEY", "test-folder-key")
    return McpService(
        config=config,
        execution_context=execution_context,
        folders_service=folders_service,
    )


def mock_retrieve(httpx_mock: HTTPXMock, base_url: str, org: str, tenant: str) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/agenthub_/api/servers/test-mcp-server",
        status_code=200,
        json={
            "id": "server-id-1",
            "name": "Test MCP Server",
            "slug": "test-mcp-server",
            "type": 0,
            "folderKey": "test-folder-key",
            "mcpUrl": MCP_URL,
        },
    )


def decode_header_value(header_value: str) -> Optional[str]:
    """Decode an MCP header value the way a server does (SEP-2243).

    Mirrors ``McpHeaderEncoder.DecodeValue`` in the MCP SDKs, which is what a
    server cross-checks the header against the body with: strip the sentinel
    and Base64-decode when both markers are present, and otherwise take the
    value as it stands. ``None`` is a decode failure, which a server rejects.
    """
    if header_value.startswith("=?base64?") and header_value.endswith("?="):
        try:
            return base64.b64decode(
                header_value[len("=?base64?") : -len("?=")], validate=True
            ).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return header_value


def rpc_result(result: dict[str, Any], request_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def task_result(
    status: str,
    *,
    result: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
    result_type: str = "complete",
    poll_interval_ms: int = 1,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "resultType": result_type,
        "taskId": "task-1",
        "status": status,
        "createdAt": "2026-11-10T10:00:00Z",
        "lastUpdatedAt": "2026-11-10T10:00:01Z",
        "ttlMs": None,
        "pollIntervalMs": poll_interval_ms,
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    return payload


def known_task() -> McpTask:
    return McpTask(
        task_id="task-1",
        status=McpTaskStatus.WORKING,
        server_url=MCP_URL,
    )


def polling_task() -> McpTask:
    """A known task whose poll interval keeps a timeout test quick."""
    return McpTask(
        task_id="task-1",
        status=McpTaskStatus.WORKING,
        server_url=MCP_URL,
        poll_interval_ms=1,
    )


class TestMcpTasks:
    def test_call_tool_declares_extension_and_wire_headers(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(task_result("working", result_type="task")),
        )

        outcome = service.call_tool("test-mcp-server", "long-process", {"a": 1})

        assert outcome.is_task
        assert outcome.task is not None
        assert outcome.task.task_id == "task-1"
        assert outcome.task.status == McpTaskStatus.WORKING
        assert outcome.task.server_url == MCP_URL

        call_request = httpx_mock.get_requests()[1]
        assert call_request.method == "POST"
        assert call_request.headers["MCP-Protocol-Version"] == "2026-07-28"
        assert call_request.headers["Mcp-Method"] == "tools/call"
        # A plain tool name travels as itself -- the header is there to be read
        # by a gateway that decodes nothing.
        assert call_request.headers["Mcp-Name"] == "long-process"

        body = json.loads(call_request.content)
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "long-process"
        assert body["params"]["arguments"] == {"a": 1}
        meta = body["params"]["_meta"]
        assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
        capabilities = meta["io.modelcontextprotocol/clientCapabilities"]
        assert "io.modelcontextprotocol/tasks" in capabilities["extensions"]

    @pytest.mark.parametrize(
        "tool_name",
        [
            "long-process",
            "café ☕",
            "=?base64?bm90LWJhc2U2NA==?=",
            "tool\twith\tcontrol",
        ],
        ids=["plain", "non-ascii", "sentinel-collision", "control-characters"],
    )
    def test_call_tool_name_header_round_trips_to_the_body(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
        tool_name: str,
    ) -> None:
        """The server accepts the call only if the header decodes to the body's name.

        Whatever the name, decoding the header the way a server does has to give
        back exactly what the body carries; a bare Base64 blob decodes to itself
        and fails that check.
        """
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(task_result("working", result_type="task")),
        )

        service.call_tool("test-mcp-server", tool_name)

        call_request = httpx_mock.get_requests()[1]
        name_header = call_request.headers["Mcp-Name"]
        assert all("\x20" <= character <= "\x7e" for character in name_header), (
            "the header value must be printable ASCII"
        )
        assert (
            decode_header_value(name_header)
            == json.loads(call_request.content)["params"]["name"]
        )

    def test_call_tool_passes_through_synchronous_result(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                {"content": [{"type": "text", "text": "quick"}], "isError": False}
            ),
        )

        outcome = service.call_tool("test-mcp-server", "quick-process")

        assert not outcome.is_task
        assert outcome.result is not None
        assert outcome.result["content"][0]["text"] == "quick"

    def test_call_tool_and_wait_polls_until_completed(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(task_result("working", result_type="task")),
        )
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result(task_result("working"))
        )
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={
                        "isError": False,
                        "content": [{"type": "text", "text": "finally"}],
                        "structuredContent": {"output": "finally"},
                    },
                )
            ),
        )

        result = service.call_tool_and_wait(
            "test-mcp-server", "long-process", timeout=10
        )

        assert result["content"][0]["text"] == "finally"

        methods = [
            json.loads(request.content)["method"]
            for request in httpx_mock.get_requests()[1:]
        ]
        assert methods == ["tools/call", "tasks/get", "tasks/get"]

        get_request = httpx_mock.get_requests()[2]
        assert json.loads(get_request.content)["params"]["taskId"] == "task-1"
        assert "Mcp-Name" not in get_request.headers

    def test_wait_for_task_raises_on_failed(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result("failed", error={"code": -32603, "message": "job faulted"})
            ),
        )

        with pytest.raises(McpTaskFailedError) as failure:
            service.wait_for_task(known_task(), timeout=10)

        assert failure.value.task.error == {"code": -32603, "message": "job faulted"}

    def test_cancel_task_sends_tasks_cancel(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result({"resultType": "complete"})
        )

        service.cancel_task(known_task())

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["method"] == "tasks/cancel"
        assert body["params"]["taskId"] == "task-1"

    def test_json_rpc_error_raises_tool_call_error(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "Unknown task id."},
            },
        )

        with pytest.raises(McpToolCallError) as error:
            service.get_task(known_task())

        assert error.value.code == -32602
        assert error.value.message == "Unknown task id."

    def test_sse_framed_response_is_parsed(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        envelope = rpc_result(task_result("working"))
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            headers={"content-type": "text/event-stream"},
            text=f"event: message\ndata: {json.dumps(envelope)}\n\n",
        )

        snapshot = service.get_task(known_task())

        assert snapshot.task_id == "task-1"
        assert snapshot.status == McpTaskStatus.WORKING
        assert snapshot.server_url == MCP_URL

    def test_task_without_server_url_is_rejected(self, service: McpService) -> None:
        orphan = McpTask(task_id="task-9", status=McpTaskStatus.WORKING)

        with pytest.raises(McpToolCallError, match="no server URL"):
            service.get_task(orphan)

    @pytest.mark.anyio
    async def test_call_tool_and_wait_async_polls_until_completed(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(task_result("working", result_type="task")),
        )
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={
                        "isError": False,
                        "content": [{"type": "text", "text": "async done"}],
                    },
                )
            ),
        )

        result = await service.call_tool_and_wait_async(
            "test-mcp-server", "long-process", timeout=10
        )

        assert result["content"][0]["text"] == "async done"


class TestMcpTasksReviewFindings:
    """Regression cover for the review findings on PR #2015."""

    def test_sse_response_after_a_notification_is_still_read(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """A leading notification must not be mistaken for the answer."""
        mock_retrieve(httpx_mock, base_url, org, tenant)
        notification = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "notifications/message",
                "params": {"level": "info", "data": "job started"},
            }
        )
        answer = json.dumps(rpc_result(task_result("working", result_type="task")))
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            headers={"content-type": "text/event-stream"},
            text=(
                "event: message\ndata: "
                + notification
                + "\n\nevent: message\ndata: "
                + answer
                + "\n\n"
            ),
        )

        outcome = service.call_tool("test-mcp-server", "long-process", {})

        assert outcome.is_task
        assert outcome.task is not None
        assert outcome.task.task_id == "task-1"

    def test_sse_body_carrying_only_notifications_is_reported(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Notifications alone are not an answer, and the error says so."""
        mock_retrieve(httpx_mock, base_url, org, tenant)
        notification = json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/message", "params": {}}
        )
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            headers={"content-type": "text/event-stream"},
            text="data: " + notification + "\n\n",
        )

        with pytest.raises(McpToolCallError, match="carried no JSON-RPC response"):
            service.call_tool("test-mcp-server", "long-process", {})

    def test_a_poll_is_bounded_by_the_remaining_budget(self) -> None:
        """The request bound shrinks with the deadline, so a slow poll cannot outlive it."""
        budget = McpService._poll_budget_seconds(
            known_task(), time.monotonic() + 7.5, 30.0
        )

        # approx, not <=: (now + 7.5) - now is not exactly 7.5 in binary
        # floating point, and on a clock with a large magnitude the error
        # lands above the bound rather than below it.
        assert budget == pytest.approx(7.5, abs=0.5)

    def test_one_poll_is_capped_even_when_the_deadline_is_far_away(self) -> None:
        """Otherwise a long wait rides on one socket for its whole duration."""
        budget = McpService._poll_budget_seconds(
            known_task(), time.monotonic() + 3600, 3600.0
        )

        assert budget == pytest.approx(30.0, abs=0.5)

    def test_an_expired_budget_raises_before_the_poll_goes_out(self) -> None:
        """Checked after the sleep: an exhausted budget must not start another request."""
        with pytest.raises(TimeoutError, match="task-1"):
            McpService._poll_budget_seconds(known_task(), time.monotonic() - 0.01, 30.0)

    def test_no_timeout_means_no_request_bound(self) -> None:
        assert McpService._poll_budget_seconds(known_task(), None, None) is None


class TestMcpTaskAsyncSurface:
    """The async twins, the terminal paths, and the two refusals."""

    @pytest.mark.anyio
    async def test_get_task_async_reads_one_snapshot(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result(task_result("working"))
        )

        snapshot = await service.get_task_async(known_task())

        assert snapshot.status == McpTaskStatus.WORKING
        assert json.loads(httpx_mock.get_requests()[0].content)["method"] == "tasks/get"

    @pytest.mark.anyio
    async def test_cancel_task_async_sends_tasks_cancel(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result({"resultType": "complete"})
        )

        await service.cancel_task_async(known_task())

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["method"] == "tasks/cancel"
        assert body["params"]["taskId"] == "task-1"

    def test_call_tool_and_wait_passes_a_synchronous_result_through(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """No task, no poll: the one-call convenience must not cost a round trip."""
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                {"content": [{"type": "text", "text": "quick"}], "isError": False}
            ),
        )

        result = service.call_tool_and_wait(
            "test-mcp-server", "quick-process", timeout=10
        )

        assert result["content"][0]["text"] == "quick"
        methods = [
            json.loads(request.content)["method"]
            for request in httpx_mock.get_requests()[1:]
        ]
        assert methods == ["tools/call"]

    @pytest.mark.anyio
    async def test_call_tool_and_wait_async_passes_a_synchronous_result_through(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                {"content": [{"type": "text", "text": "quick"}], "isError": False}
            ),
        )

        result = await service.call_tool_and_wait_async(
            "test-mcp-server", "quick-process", timeout=10
        )

        assert result["content"][0]["text"] == "quick"

    def test_wait_for_task_raises_on_cancelled(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result(task_result("cancelled"))
        )

        with pytest.raises(McpTaskCancelledError) as cancelled:
            service.wait_for_task(known_task(), timeout=10)

        assert cancelled.value.task.task_id == "task-1"

    def test_only_the_three_final_statuses_are_terminal(self) -> None:
        terminal = [status for status in McpTaskStatus if status.is_terminal]

        assert terminal == [
            McpTaskStatus.COMPLETED,
            McpTaskStatus.FAILED,
            McpTaskStatus.CANCELLED,
        ]

    def test_a_server_without_an_mcp_url_is_reported(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/agenthub_/api/servers/test-mcp-server",
            status_code=200,
            json={
                "id": "server-id-1",
                "name": "Test MCP Server",
                "slug": "test-mcp-server",
                "type": 0,
                "folderKey": "test-folder-key",
            },
        )

        with pytest.raises(McpToolCallError, match="exposes no MCP URL"):
            service.call_tool("test-mcp-server", "long-process")

    @pytest.mark.anyio
    async def test_a_server_without_an_mcp_url_is_reported_async(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/agenthub_/api/servers/test-mcp-server",
            status_code=200,
            json={
                "id": "server-id-1",
                "name": "Test MCP Server",
                "slug": "test-mcp-server",
                "type": 0,
                "folderKey": "test-folder-key",
            },
        )

        with pytest.raises(McpToolCallError, match="exposes no MCP URL"):
            await service.call_tool_async("test-mcp-server", "long-process")

    def test_an_exhausted_deadline_is_what_becomes_a_task_timeout(
        self, service: McpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A poll that runs past the deadline ends the wait, as a timeout."""

        def exhausted(task: McpTask, budget: Optional[float]) -> McpTask:
            time.sleep(0.06)
            raise httpx.ReadTimeout("the server never answered")

        monkeypatch.setattr(service, "_get_task_within", exhausted)

        with pytest.raises(TimeoutError, match="task-1"):
            service.wait_for_task(polling_task(), timeout=0.05)

    @pytest.mark.anyio
    async def test_an_exhausted_deadline_is_what_becomes_a_task_timeout_async(
        self, service: McpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def exhausted(task: McpTask, budget: Optional[float]) -> McpTask:
            time.sleep(0.06)
            raise httpx.ReadTimeout("the server never answered")

        monkeypatch.setattr(service, "_get_task_within_async", exhausted)

        with pytest.raises(TimeoutError, match="task-1"):
            await service.wait_for_task_async(polling_task(), timeout=0.05)

    def test_a_timed_out_poll_with_budget_left_is_polled_again(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """A stalled connection is not the task's verdict, and not the deadline's.

        Treating any read timeout as the deadline made a long wait *less*
        resilient than one with no timeout at all: one black-holed socket
        ended an hour-long wait, while the same stall with ``timeout=None``
        was re-polled.
        """
        httpx_mock.add_exception(httpx.ReadTimeout("no answer"), url=MCP_URL)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={
                        "content": [{"type": "text", "text": "late"}],
                        "isError": False,
                    },
                )
            ),
        )

        result = service.wait_for_task(polling_task(), timeout=30)

        assert result["content"][0]["text"] == "late"
        assert len(httpx_mock.get_requests()) == 2

    def test_a_timed_out_poll_is_sent_once_per_tick_not_five_times(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """The platform retry policy would outlive the deadline it is bounded by.

        Five ticks, five requests: the loop is the retry. With the policy on,
        each tick would have re-sent up to ``MAX_RETRY_ATTEMPTS`` times behind
        backoff of its own.
        """
        for _ in range(5):
            httpx_mock.add_exception(httpx.ReadTimeout("no answer"), url=MCP_URL)

        with pytest.raises(httpx.ReadTimeout):
            service.wait_for_task(polling_task())

        assert len(httpx_mock.get_requests()) == 5

    def test_a_transient_poll_failure_is_retried_by_the_loop(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """A blip must not end a long wait: the next tick re-polls the same task."""
        httpx_mock.add_exception(httpx.ConnectError("connection reset"), url=MCP_URL)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={
                        "content": [{"type": "text", "text": "late"}],
                        "isError": False,
                    },
                )
            ),
        )

        result = service.wait_for_task(polling_task(), timeout=10)

        assert result["content"][0]["text"] == "late"
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.anyio
    async def test_a_transient_poll_failure_is_retried_by_the_loop_async(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("connection reset"), url=MCP_URL)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={
                        "content": [{"type": "text", "text": "late"}],
                        "isError": False,
                    },
                )
            ),
        )

        result = await service.wait_for_task_async(polling_task(), timeout=10)

        assert result["content"][0]["text"] == "late"

    def test_a_server_that_is_simply_gone_stops_at_the_failure_cap(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """Without a timeout there is no deadline, so the cap is the only bound."""
        for _ in range(5):
            httpx_mock.add_exception(httpx.ConnectError("gone"), url=MCP_URL)

        with pytest.raises(httpx.ConnectError):
            service.wait_for_task(polling_task())

        assert len(httpx_mock.get_requests()) == 5

    def test_a_non_transient_poll_failure_is_raised_at_once(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """Only transient failures are the loop's to absorb."""
        httpx_mock.add_response(url=MCP_URL, status_code=403, json={"message": "nope"})

        with pytest.raises(Exception, match="403"):
            service.wait_for_task(polling_task(), timeout=10)

        assert len(httpx_mock.get_requests()) == 1

    def test_a_plain_500_on_a_poll_is_absorbed(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """500 is outside the platform's retryable set, but a poll is a read.

        The task is still running; the server just failed to describe it.
        """
        httpx_mock.add_response(url=MCP_URL, status_code=500, json={"message": "boom"})
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={"content": [{"type": "text", "text": "ok"}]},
                )
            ),
        )

        result = service.wait_for_task(polling_task(), timeout=30)

        assert result["content"][0]["text"] == "ok"

    def test_a_json_rpc_internal_error_on_a_poll_is_absorbed(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """The same failure arriving inside a 200, which the loop never caught."""
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32603, "message": "internal error"},
            },
        )
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={"content": [{"type": "text", "text": "ok"}]},
                )
            ),
        )

        result = service.wait_for_task(polling_task(), timeout=30)

        assert result["content"][0]["text"] == "ok"

    def test_an_unknown_task_on_a_poll_is_raised_at_once(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """Not every JSON-RPC error is a blip: this one is an answer."""
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "unknown task"},
            },
        )

        with pytest.raises(McpToolCallError, match="unknown task"):
            service.wait_for_task(polling_task(), timeout=30)

        assert len(httpx_mock.get_requests()) == 1

    def test_a_transient_failure_rides_until_the_deadline_not_the_cap(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """A caller who asked to wait meant to ride out more than four blips."""
        for _ in range(6):
            httpx_mock.add_response(
                url=MCP_URL, status_code=503, json={"message": "unavailable"}
            )
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={"content": [{"type": "text", "text": "eventually"}]},
                )
            ),
        )

        result = service.wait_for_task(polling_task(), timeout=30)

        assert result["content"][0]["text"] == "eventually"
        assert len(httpx_mock.get_requests()) == 7

    def test_a_retry_after_sets_the_floor_for_the_next_poll(self) -> None:
        """A throttled server asked for room; the poll interval does not override it."""
        failure = httpx.HTTPStatusError(
            "throttled",
            request=httpx.Request("POST", MCP_URL),
            response=httpx.Response(429, headers={"retry-after": "4"}),
        )

        delay = McpService._poll_delay_seconds(
            polling_task(), None, None, failures=1, retry_after=4.0
        )

        assert delay == pytest.approx(4.0)
        assert extract_retry_after_from_chain(failure) == 4.0

    def test_a_zero_poll_interval_does_not_spin(self) -> None:
        """A server asking to be polled instantly gets the floor instead."""
        eager = McpTask(
            task_id="task-1",
            status=McpTaskStatus.WORKING,
            server_url=MCP_URL,
            poll_interval_ms=0,
        )

        assert McpService._poll_delay_seconds(eager, None, None) >= 0.001

    def test_a_deadline_already_past_stops_before_sleeping(self) -> None:
        with pytest.raises(TimeoutError, match="task-1"):
            McpService._poll_delay_seconds(known_task(), time.monotonic() - 1, 30.0)


class TestTaskReference:
    """What a task id looks like once it reaches a message or a log line."""

    # Two real ids from a UiPath server: 368 characters, sharing their first 27.
    REAL_A = "AfDP2j-98rUt7wxBowad5FIlYGx" + "A" * 333 + "4VD53jN7yzE8"
    REAL_B = "AfDP2j-98rUt7wxBowad5FIlYGx" + "B" * 333 + "8eMkW1DIPfrp"

    def test_two_different_tasks_do_not_read_the_same(self) -> None:
        """The whole point: a prefix of these ids is a constant, not a name."""
        assert task_ref(self.REAL_A) != task_ref(self.REAL_B)

    def test_a_long_id_is_shortened(self) -> None:
        shortened = task_ref(self.REAL_A)

        assert len(shortened) < 40
        assert self.REAL_A not in shortened
        # Both ends, so it can still be matched by eye against a full id.
        assert shortened.startswith(self.REAL_A[:12])
        assert shortened.endswith(self.REAL_A[-8:])

    def test_a_short_id_is_left_alone(self) -> None:
        assert task_ref("task-1") == "task-1"

    def test_the_wire_carries_the_whole_id(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """Shortening is for text only: a request addresses the task by its id.

        A truncated id on the wire would be a different task -- or no task at
        all -- so this pins the one thing the shortening must never touch.
        """
        long_task = McpTask(
            task_id=self.REAL_A, status=McpTaskStatus.WORKING, server_url=MCP_URL
        )
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result(task_result("working"))
        )
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result({"resultType": "complete"})
        )

        service.get_task(long_task)
        service.cancel_task(long_task)

        sent = [json.loads(request.content) for request in httpx_mock.get_requests()]
        assert [body["method"] for body in sent] == ["tasks/get", "tasks/cancel"]
        for body in sent:
            assert body["params"]["taskId"] == self.REAL_A

    def test_the_wait_timeout_names_the_task_without_quoting_it(self) -> None:
        task = McpTask(task_id=self.REAL_A, status=McpTaskStatus.WORKING)

        message = str(McpService._task_timeout(task, 30.0))

        assert self.REAL_A not in message
        assert self.REAL_A[:12] in message


class TestMcpTaskHandle:
    """What a handle accepts, and what it refuses to take from the wire."""

    def test_an_unknown_status_keeps_the_wait_polling(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """A status the spec adds later must not raise out of somebody's wait."""
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(task_result("suspended", poll_interval_ms=1)),
        )
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(
                task_result(
                    "completed",
                    result={"content": [{"type": "text", "text": "resumed"}]},
                )
            ),
        )

        result = service.wait_for_task(polling_task(), timeout=30)

        assert result["content"][0]["text"] == "resumed"

    def test_a_known_status_is_still_the_enum(self) -> None:
        """Union resolution must not quietly hand back a plain string."""
        task = McpTask.model_validate({"taskId": "task-1", "status": "working"})

        assert task.status is McpTaskStatus.WORKING
        assert isinstance(task.status, McpTaskStatus)

    def test_a_payload_cannot_name_its_own_endpoint(self) -> None:
        """Follow-ups carry the bearer token, so the server does not pick the host."""
        task = McpTask.model_validate(
            {
                "taskId": "task-1",
                "status": "working",
                "serverUrl": "https://evil.example.com/mcp",
            }
        )

        assert task.server_url is None

    def test_the_client_still_records_where_it_sent_the_call(self) -> None:
        task = McpTask(
            task_id="task-1", status=McpTaskStatus.WORKING, server_url=MCP_URL
        )

        assert task.server_url == MCP_URL
        assert "serverUrl" not in task.model_dump(by_alias=True)


class TestMcpToolCallIsNotResent:
    """A tool call starts work server-side, so it must not be re-sent blindly."""

    @staticmethod
    def _tool_calls(httpx_mock: HTTPXMock) -> int:
        return len([r for r in httpx_mock.get_requests() if str(r.url) == MCP_URL])

    def test_a_read_timeout_does_not_resend_the_tool_call(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """The server has the request: re-sending it can start a second job.

        The platform policy would retry a timeout five times; the 30-second
        client timeout makes that reachable for any tool answering slowly in
        the synchronous shape.
        """
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_exception(httpx.ReadTimeout("still working"), url=MCP_URL)

        with pytest.raises(httpx.ReadTimeout):
            service.call_tool("test-mcp-server", "long-process")

        assert self._tool_calls(httpx_mock) == 1

    def test_a_gateway_504_does_not_resend_the_tool_call(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """A 504 says the gateway gave up, not that the server did nothing."""
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_response(url=MCP_URL, status_code=504, json={"error": "timeout"})

        with pytest.raises(Exception, match="504"):
            service.call_tool("test-mcp-server", "long-process")

        assert self._tool_calls(httpx_mock) == 1

    @pytest.mark.anyio
    async def test_a_read_timeout_does_not_resend_the_tool_call_async(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_exception(httpx.ReadTimeout("still working"), url=MCP_URL)

        with pytest.raises(httpx.ReadTimeout):
            await service.call_tool_async("test-mcp-server", "long-process")

        assert self._tool_calls(httpx_mock) == 1

    def test_a_failed_connect_is_still_retried(
        self,
        httpx_mock: HTTPXMock,
        service: McpService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Nothing was delivered, so re-sending cannot duplicate the work."""
        mock_retrieve(httpx_mock, base_url, org, tenant)
        httpx_mock.add_exception(httpx.ConnectError("no route"), url=MCP_URL)
        httpx_mock.add_response(
            url=MCP_URL,
            status_code=200,
            json=rpc_result(task_result("working", result_type="task")),
        )

        outcome = service.call_tool("test-mcp-server", "long-process")

        assert outcome.is_task
        assert self._tool_calls(httpx_mock) == 2

    def test_a_task_parked_on_input_required_is_not_polled_forever(
        self, httpx_mock: HTTPXMock, service: McpService
    ) -> None:
        """`timeout` defaults to None, so polling on would never end."""
        httpx_mock.add_response(
            url=MCP_URL, status_code=200, json=rpc_result(task_result("input_required"))
        )

        with pytest.raises(McpTaskInputRequiredError) as parked:
            service.wait_for_task(known_task())

        assert parked.value.task.task_id == "task-1"

    def test_an_outcome_must_carry_exactly_one_shape(self) -> None:
        with pytest.raises(ValueError, match="not both and not neither"):
            McpToolCallOutcome(result={"content": []}, task=known_task())

        with pytest.raises(ValueError, match="not both and not neither"):
            McpToolCallOutcome()


class TestMcpEnvelopeParsing:
    """The framing edges, which only a malformed server produces."""

    def test_a_trailing_event_without_a_blank_line_is_still_read(self) -> None:
        """SSE bodies are not required to end with the event separator."""
        events = McpService._sse_data_events('data: {"a": 1}')

        assert events == ['{"a": 1}']

    def test_an_sse_body_with_no_data_event_is_reported(self) -> None:
        with pytest.raises(McpToolCallError, match="had no data event"):
            McpService._sse_response_envelope("event: ping\n\n", "tasks/get")

    def test_an_unparseable_event_is_skipped_for_the_next_one(self) -> None:
        """A heartbeat or comment payload must not mask the response behind it."""
        answer = json.dumps(rpc_result(task_result("working")))

        envelope = McpService._sse_response_envelope(
            f"data: not-json\n\ndata: {answer}\n\n", "tasks/get"
        )

        assert envelope["result"]["taskId"] == "task-1"

    def test_a_body_that_is_not_json_is_reported(self) -> None:
        response = httpx.Response(200, text="<html>login</html>")

        with pytest.raises(McpToolCallError, match="was not JSON"):
            McpService._parse_mcp_envelope(response, "tools/call")

    def test_a_body_that_is_not_an_envelope_is_reported(self) -> None:
        response = httpx.Response(200, json=[1, 2, 3])

        with pytest.raises(McpToolCallError, match="was not an envelope"):
            McpService._parse_mcp_envelope(response, "tools/call")

    def test_an_envelope_without_a_result_object_is_reported(self) -> None:
        response = httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": None})

        with pytest.raises(McpToolCallError, match="carried no result object"):
            McpService._parse_mcp_envelope(response, "tools/call")
