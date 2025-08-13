import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.connections_service import ConnectionsService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models import Connection, ConnectionToken, EventArguments


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
            url=f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?tokenType=direct",
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
            == f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?tokenType=direct"
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
            url=f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?tokenType=direct",
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
            == f"{base_url}{org}{tenant}/connections_/api/v1/Connections/{connection_key}/token?tokenType=direct"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve_token_async/{version}"
        )

    def test_retrieve_event_payload(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        event_id = "test-event-id"
        additional_event_data = '{"processedEventId": "test-event-id"}'

        event_args = EventArguments(additional_event_data=additional_event_data)

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}",
            status_code=200,
            json={
                "eventId": event_id,
                "eventType": "test-event",
                "data": {"key": "value"},
                "timestamp": "2025-08-12T10:00:00Z",
            },
        )

        payload = service.retrieve_event_payload(event_args=event_args)

        assert payload["eventId"] == event_id
        assert payload["eventType"] == "test-event"
        assert payload["data"]["key"] == "value"
        assert payload["timestamp"] == "2025-08-12T10:00:00Z"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve_event_payload/{version}"
        )

    def test_retrieve_event_payload_with_raw_event_id(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        event_id = "test-raw-event-id"
        additional_event_data = '{"rawEventId": "test-raw-event-id"}'

        event_args = EventArguments(additional_event_data=additional_event_data)

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}",
            status_code=200,
            json={
                "eventId": event_id,
                "eventType": "test-raw-event",
                "data": {"rawKey": "rawValue"},
            },
        )

        payload = service.retrieve_event_payload(event_args=event_args)

        assert payload["eventId"] == event_id
        assert payload["eventType"] == "test-raw-event"
        assert payload["data"]["rawKey"] == "rawValue"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}"
        )

    def test_retrieve_event_payload_missing_additional_event_data(
        self,
        service: ConnectionsService,
    ) -> None:
        event_args = EventArguments(additional_event_data=None)

        with pytest.raises(ValueError, match="additional_event_data is required"):
            service.retrieve_event_payload(event_args=event_args)

    def test_retrieve_event_payload_missing_event_id(
        self,
        service: ConnectionsService,
    ) -> None:
        additional_event_data = '{"someOtherField": "value"}'
        event_args = EventArguments(additional_event_data=additional_event_data)

        with pytest.raises(
            ValueError, match="Event Id not found in additional event data"
        ):
            service.retrieve_event_payload(event_args=event_args)

    @pytest.mark.anyio
    async def test_retrieve_event_payload_async(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        event_id = "test-event-id-async"
        additional_event_data = '{"processedEventId": "test-event-id-async"}'

        event_args = EventArguments(additional_event_data=additional_event_data)

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}",
            status_code=200,
            json={
                "eventId": event_id,
                "eventType": "test-async-event",
                "data": {"asyncKey": "asyncValue"},
                "timestamp": "2025-08-12T11:00:00Z",
            },
        )

        payload = await service.retrieve_event_payload_async(event_args=event_args)

        assert payload["eventId"] == event_id
        assert payload["eventType"] == "test-async-event"
        assert payload["data"]["asyncKey"] == "asyncValue"
        assert payload["timestamp"] == "2025-08-12T11:00:00Z"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ConnectionsService.retrieve_event_payload_async/{version}"
        )

    @pytest.mark.anyio
    async def test_retrieve_event_payload_async_with_raw_event_id(
        self,
        httpx_mock: HTTPXMock,
        service: ConnectionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        event_id = "test-raw-event-id-async"
        additional_event_data = '{"rawEventId": "test-raw-event-id-async"}'

        event_args = EventArguments(additional_event_data=additional_event_data)

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}",
            status_code=200,
            json={
                "eventId": event_id,
                "eventType": "test-async-raw-event",
                "data": {"asyncRawKey": "asyncRawValue"},
            },
        )

        payload = await service.retrieve_event_payload_async(event_args=event_args)

        assert payload["eventId"] == event_id
        assert payload["eventType"] == "test-async-raw-event"
        assert payload["data"]["asyncRawKey"] == "asyncRawValue"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/elements_/v1/events/{event_id}"
        )

    @pytest.mark.anyio
    async def test_retrieve_event_payload_async_missing_additional_event_data(
        self,
        service: ConnectionsService,
    ) -> None:
        event_args = EventArguments(additional_event_data=None)

        with pytest.raises(ValueError, match="additional_event_data is required"):
            await service.retrieve_event_payload_async(event_args=event_args)

    @pytest.mark.anyio
    async def test_retrieve_event_payload_async_missing_event_id(
        self,
        service: ConnectionsService,
    ) -> None:
        additional_event_data = '{"someOtherField": "value"}'
        event_args = EventArguments(additional_event_data=additional_event_data)

        with pytest.raises(
            ValueError, match="Event Id not found in additional event data"
        ):
            await service.retrieve_event_payload_async(event_args=event_args)
