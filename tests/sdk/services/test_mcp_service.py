from unittest.mock import Mock, patch

import pytest
from pytest_httpx import HTTPXMock

from uipath._utils.constants import HEADER_FOLDER_KEY, HEADER_USER_AGENT
from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.orchestrator import McpService
from uipath.platform.orchestrator._folder_service import FolderService
from uipath.platform.orchestrator.mcp import McpServer


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


class TestMcpService:
    class TestListServers:
        def test_list_with_folder_path(
            self,
            httpx_mock: HTTPXMock,
            service: McpService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            """Test listing MCP servers with a folder_path parameter that gets resolved."""
            mock_servers = [
                {
                    "id": "server-id-1",
                    "name": "Test MCP Server",
                    "slug": "test-mcp-server",
                    "description": "Test description",
                    "version": "1.0.0",
                    "createdAt": "2025-07-24T11:30:52.031427",
                    "updatedAt": "2025-07-24T12:29:53.4765887",
                    "isActive": True,
                    "type": 2,
                    "status": 1,
                    "command": "",
                    "arguments": "",
                    "environmentVariables": "",
                    "processKey": "test-process-key",
                    "folderKey": "test-folder-key",
                    "runtimesCount": 0,
                    "mcpUrl": "https://test.com/mcp/test-mcp-server",
                }
            ]

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
                status_code=200,
                json={
                    "PageItems": [
                        {
                            "Key": "resolved-folder-key",
                            "FullyQualifiedName": "test-folder-path",
                        }
                    ],
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agenthub_/api/servers",
                status_code=200,
                json=mock_servers,
            )

            servers = service.list(folder_path="test-folder-path")

            assert len(servers) == 1
            assert isinstance(servers[0], McpServer)
            assert servers[0].name == "Test MCP Server"

            requests = httpx_mock.get_requests()
            assert len(requests) == 2

            servers_request = requests[1]
            assert servers_request.method == "GET"
            assert (
                servers_request.url == f"{base_url}{org}{tenant}/agenthub_/api/servers"
            )
            assert HEADER_FOLDER_KEY in servers_request.headers
            assert servers_request.headers[HEADER_FOLDER_KEY] == "resolved-folder-key"

        def test_list_without_folder_raises_error(
            self,
            config: UiPathApiConfig,
            execution_context: UiPathExecutionContext,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """Test that listing servers without a folder_path raises ValueError."""
            monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
            monkeypatch.delenv("UIPATH_FOLDER_PATH", raising=False)

            folders_service = FolderService(
                config=config, execution_context=execution_context
            )
            service = McpService(
                config=config,
                execution_context=execution_context,
                folders_service=folders_service,
            )

            with pytest.raises(
                ValueError,
                match="Cannot obtain folder_key without providing folder_path",
            ):
                service.list()

        @pytest.mark.anyio
        async def test_list_async(
            self,
            httpx_mock: HTTPXMock,
            service: McpService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            """Test asynchronously listing MCP servers."""
            mock_servers = [
                {
                    "id": "server-id-1",
                    "name": "Async Test Server",
                    "slug": "async-test-server",
                    "description": "Async test description",
                    "version": "1.0.0",
                    "createdAt": "2025-07-24T11:30:52.031427",
                    "updatedAt": "2025-07-24T12:29:53.4765887",
                    "isActive": True,
                    "type": 2,
                    "status": 1,
                    "command": "",
                    "arguments": "",
                    "environmentVariables": "",
                    "processKey": "test-process-key",
                    "folderKey": "test-folder-key",
                    "runtimesCount": 0,
                    "mcpUrl": "https://test.com/mcp/async-test-server",
                }
            ]

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
                status_code=200,
                json={
                    "PageItems": [
                        {
                            "Key": "test-folder-key",
                            "FullyQualifiedName": "test-folder-path",
                        }
                    ],
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agenthub_/api/servers",
                status_code=200,
                json=mock_servers,
            )

            servers = await service.list_async(folder_path="test-folder-path")

            assert len(servers) == 1
            assert isinstance(servers[0], McpServer)
            assert servers[0].name == "Async Test Server"

            requests = httpx_mock.get_requests()
            assert len(requests) == 2

            servers_request = requests[1]
            assert servers_request.method == "GET"
            assert (
                servers_request.url == f"{base_url}{org}{tenant}/agenthub_/api/servers"
            )
            assert HEADER_FOLDER_KEY in servers_request.headers
            assert servers_request.headers[HEADER_FOLDER_KEY] == "test-folder-key"
            assert HEADER_USER_AGENT in servers_request.headers
            assert (
                servers_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.McpService.list_async/{version}"
            )

    class TestRetrieveServer:
        def test_retrieve_server_with_folder_path(
            self,
            httpx_mock: HTTPXMock,
            service: McpService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            """Test retrieving a specific MCP server by slug with folder_path."""
            mock_server = {
                "id": "server-id-1",
                "name": "Test MCP Server",
                "slug": "test-mcp-server",
                "description": "A test server",
                "version": "1.0.0",
                "createdAt": "2025-07-24T11:30:52.031427",
                "updatedAt": "2025-07-24T12:29:53.4765887",
                "isActive": True,
                "type": 2,
                "status": 1,
                "command": "",
                "arguments": "",
                "environmentVariables": "",
                "processKey": "test-process-key",
                "folderKey": "test-folder-key",
                "runtimesCount": 0,
                "mcpUrl": "https://test.com/mcp/test-mcp-server",
            }

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
                status_code=200,
                json={
                    "PageItems": [
                        {
                            "Key": "test-folder-key",
                            "FullyQualifiedName": "test-folder-path",
                        }
                    ],
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agenthub_/api/servers/test-mcp-server",
                status_code=200,
                json=mock_server,
            )

            server = service.retrieve("test-mcp-server", folder_path="test-folder-path")

            assert isinstance(server, McpServer)
            assert server.name == "Test MCP Server"
            assert server.slug == "test-mcp-server"

            requests = httpx_mock.get_requests()
            assert len(requests) == 2

            retrieve_request = requests[1]
            assert retrieve_request.method == "GET"
            assert (
                retrieve_request.url
                == f"{base_url}{org}{tenant}/agenthub_/api/servers/test-mcp-server"
            )
            assert HEADER_FOLDER_KEY in retrieve_request.headers
            assert retrieve_request.headers[HEADER_FOLDER_KEY] == "test-folder-key"
            assert HEADER_USER_AGENT in retrieve_request.headers
            assert (
                retrieve_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.McpService.retrieve/{version}"
            )

        @pytest.mark.anyio
        async def test_retrieve_server_async(
            self,
            httpx_mock: HTTPXMock,
            service: McpService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            """Test asynchronously retrieving a specific MCP server."""
            mock_server = {
                "id": "server-id-1",
                "name": "Async Test Server",
                "slug": "async-test-server",
                "description": "Async test server",
                "version": "1.0.0",
                "createdAt": "2025-07-24T11:30:52.031427",
                "updatedAt": "2025-07-24T12:29:53.4765887",
                "isActive": True,
                "type": 2,
                "status": 1,
                "command": "",
                "arguments": "",
                "environmentVariables": "",
                "processKey": "test-process-key",
                "folderKey": "test-folder-key",
                "runtimesCount": 0,
                "mcpUrl": "https://test.com/mcp/async-test-server",
            }

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
                status_code=200,
                json={
                    "PageItems": [
                        {
                            "Key": "test-folder-key",
                            "FullyQualifiedName": "test-folder-path",
                        }
                    ],
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agenthub_/api/servers/async-test-server",
                status_code=200,
                json=mock_server,
            )

            server = await service.retrieve_async(
                "async-test-server", folder_path="test-folder-path"
            )

            assert isinstance(server, McpServer)
            assert server.name == "Async Test Server"

            requests = httpx_mock.get_requests()
            assert len(requests) == 2

            retrieve_request = requests[1]
            assert retrieve_request.method == "GET"
            assert (
                retrieve_request.url
                == f"{base_url}{org}{tenant}/agenthub_/api/servers/async-test-server"
            )
            assert HEADER_FOLDER_KEY in retrieve_request.headers
            assert retrieve_request.headers[HEADER_FOLDER_KEY] == "test-folder-key"
            assert HEADER_USER_AGENT in retrieve_request.headers
            assert (
                retrieve_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.McpService.retrieve_async/{version}"
            )

    class TestRequestKwargs:
        """Test that all methods pass the correct kwargs to request/request_async."""

        def test_list_passes_all_kwargs(self, service: McpService) -> None:
            """Test that list passes all kwargs to request."""
            mock_response = Mock()
            mock_response.json.return_value = [
                {
                    "id": "test-id",
                    "name": "Test Server",
                    "slug": "test-server",
                    "description": "Test",
                    "version": "1.0.0",
                    "createdAt": "2025-07-24T11:30:52.031427",
                    "updatedAt": "2025-07-24T12:29:53.4765887",
                    "isActive": True,
                    "type": 2,
                    "status": 1,
                    "processKey": "test-process-key",
                    "folderKey": "test-folder-key",
                    "mcpUrl": "https://test.com/mcp/test",
                }
            ]

            with patch.object(
                service._folders_service,
                "retrieve_folder_key",
                return_value="test-folder-key",
            ):
                with patch.object(
                    service, "request", return_value=mock_response
                ) as mock_request:
                    service.list(folder_path="test-folder-path")

                    mock_request.assert_called_once()
                    call_kwargs = mock_request.call_args

                    assert "url" in call_kwargs.kwargs
                    assert "params" in call_kwargs.kwargs
                    assert "headers" in call_kwargs.kwargs

                    assert call_kwargs.args[0] == "GET"

                    assert HEADER_FOLDER_KEY in call_kwargs.kwargs["headers"]
                    assert (
                        call_kwargs.kwargs["headers"][HEADER_FOLDER_KEY]
                        == "test-folder-key"
                    )

        @pytest.mark.anyio
        async def test_list_async_passes_all_kwargs(self, service: McpService) -> None:
            """Test that list_async passes all kwargs to request_async."""
            mock_response = Mock()
            mock_response.json.return_value = [
                {
                    "id": "test-id",
                    "name": "Test Server",
                    "slug": "test-server",
                    "description": "Test",
                    "version": "1.0.0",
                    "createdAt": "2025-07-24T11:30:52.031427",
                    "updatedAt": "2025-07-24T12:29:53.4765887",
                    "isActive": True,
                    "type": 2,
                    "status": 1,
                    "processKey": "test-process-key",
                    "folderKey": "test-folder-key",
                    "mcpUrl": "https://test.com/mcp/test",
                }
            ]

            with patch.object(
                service._folders_service,
                "retrieve_folder_key",
                return_value="test-folder-key",
            ):
                with patch.object(
                    service, "request_async", return_value=mock_response
                ) as mock_request:
                    await service.list_async(folder_path="test-folder-path")

                    mock_request.assert_called_once()
                    call_kwargs = mock_request.call_args

                    assert "url" in call_kwargs.kwargs
                    assert "params" in call_kwargs.kwargs
                    assert "headers" in call_kwargs.kwargs

                    assert call_kwargs.args[0] == "GET"

                    assert HEADER_FOLDER_KEY in call_kwargs.kwargs["headers"]
                    assert (
                        call_kwargs.kwargs["headers"][HEADER_FOLDER_KEY]
                        == "test-folder-key"
                    )

        def test_retrieve_passes_all_kwargs(self, service: McpService) -> None:
            """Test that retrieve passes all kwargs to request."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "id": "test-id",
                "name": "Test Server",
                "slug": "test-server",
                "description": "Test",
                "version": "1.0.0",
                "createdAt": "2025-07-24T11:30:52.031427",
                "updatedAt": "2025-07-24T12:29:53.4765887",
                "isActive": True,
                "type": 2,
                "status": 1,
                "processKey": "test-process-key",
                "folderKey": "test-folder-key",
                "mcpUrl": "https://test.com/mcp/test",
            }

            with patch.object(
                service._folders_service,
                "retrieve_folder_key",
                return_value="test-folder-key",
            ):
                with patch.object(
                    service, "request", return_value=mock_response
                ) as mock_request:
                    service.retrieve("test-server", folder_path="test-folder-path")

                    mock_request.assert_called_once()
                    call_kwargs = mock_request.call_args

                    assert "url" in call_kwargs.kwargs
                    assert "params" in call_kwargs.kwargs
                    assert "headers" in call_kwargs.kwargs

                    assert call_kwargs.args[0] == "GET"

                    assert HEADER_FOLDER_KEY in call_kwargs.kwargs["headers"]
                    assert (
                        call_kwargs.kwargs["headers"][HEADER_FOLDER_KEY]
                        == "test-folder-key"
                    )

        @pytest.mark.anyio
        async def test_retrieve_async_passes_all_kwargs(
            self, service: McpService
        ) -> None:
            """Test that retrieve_async passes all kwargs to request_async."""
            mock_response = Mock()
            mock_response.json.return_value = {
                "id": "test-id",
                "name": "Test Server",
                "slug": "test-server",
                "description": "Test",
                "version": "1.0.0",
                "createdAt": "2025-07-24T11:30:52.031427",
                "updatedAt": "2025-07-24T12:29:53.4765887",
                "isActive": True,
                "type": 2,
                "status": 1,
                "processKey": "test-process-key",
                "folderKey": "test-folder-key",
                "mcpUrl": "https://test.com/mcp/test",
            }

            with patch.object(
                service._folders_service,
                "retrieve_folder_key",
                return_value="test-folder-key",
            ):
                with patch.object(
                    service, "request_async", return_value=mock_response
                ) as mock_request:
                    await service.retrieve_async(
                        "test-server", folder_path="test-folder-path"
                    )

                    mock_request.assert_called_once()
                    call_kwargs = mock_request.call_args

                    assert "url" in call_kwargs.kwargs
                    assert "params" in call_kwargs.kwargs
                    assert "headers" in call_kwargs.kwargs

                    assert call_kwargs.args[0] == "GET"

                    assert HEADER_FOLDER_KEY in call_kwargs.kwargs["headers"]
                    assert (
                        call_kwargs.kwargs["headers"][HEADER_FOLDER_KEY]
                        == "test-folder-key"
                    )
