import base64
import json
from typing import Any, Optional

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.orchestrator import McpService
from uipath.platform.orchestrator._folder_service import FolderService
from uipath.platform.orchestrator.mcp_tasks import (
    McpTask,
    McpTaskFailedError,
    McpTaskStatus,
    McpToolCallError,
)

MCP_URL = "https://test.com/mcp/folder-key/test-mcp-server"


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
        assert call_request.headers["Mcp-Name"] == base64.b64encode(
            b"long-process"
        ).decode("ascii")

        body = json.loads(call_request.content)
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "long-process"
        assert body["params"]["arguments"] == {"a": 1}
        meta = body["params"]["_meta"]
        assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
        capabilities = meta["io.modelcontextprotocol/clientCapabilities"]
        assert "io.modelcontextprotocol/tasks" in capabilities["extensions"]

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
