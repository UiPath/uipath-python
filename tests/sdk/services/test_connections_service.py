import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.connections_service import ConnectionsService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models import Connection, ConnectionToken


@pytest.fixture
def service(
    config: Config, execution_context: ExecutionContext, monkeypatch: pytest.MonkeyPatch
) -> ConnectionsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return ConnectionsService(config=config, execution_context=execution_context)


class TestConnectionsService:
    def test_retrieve(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        connection_key = "test-connection"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}",
            status_code=200,
            json={
                "id": "test-id",
                "name": "Test Connection",
                "state": "active",
                "elementInstanceId": 123,
            },
        )

        connection = service.retrieve(key=connection_key)

        assert isinstance(connection, Connection)
        assert connection.id == "test-id"
        assert connection.name == "Test Connection"
        assert connection.state == "active"
        assert connection.element_instance_id == 123

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve/{version}"
        )

    @pytest.mark.anyio
    async def test_retrieve_async(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        connection_key = "test-connection"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}",
            status_code=200,
            json={
                "id": "test-id",
                "name": "Test Connection",
                "state": "active",
                "elementInstanceId": 123,
            },
        )

        connection = await service.retrieve_async(key=connection_key)

        assert isinstance(connection, Connection)
        assert connection.id == "test-id"
        assert connection.name == "Test Connection"
        assert connection.state == "active"
        assert connection.element_instance_id == 123

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve_async/{version}"
        )

    def test_retrieve_token(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        connection_key = "test-connection"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?type=direct",
            status_code=200,
            json={
                "accessToken": "test-token",
                "tokenType": "Bearer",
                "expiresIn": 3600,
            },
        )

        token = service.retrieve_token(key=connection_key)

        assert isinstance(token, ConnectionToken)
        assert token.access_token == "test-token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?type=direct"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve_token/{version}"
        )

    @pytest.mark.anyio
    async def test_retrieve_token_async(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        connection_key = "test-connection"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?type=direct",
            status_code=200,
            json={
                "accessToken": "test-token",
                "tokenType": "Bearer",
                "expiresIn": 3600,
            },
        )

        token = await service.retrieve_token_async(key=connection_key)

        assert isinstance(token, ConnectionToken)
        assert token.access_token == "test-token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?type=direct"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve_token_async/{version}"
        )
