import json
import logging
from typing import Any, Dict

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint, RequestSpec, infer_bindings
from ..models import Connection, ConnectionToken, EventArguments
from ..models.connections import ConnectionTokenType
from ..tracing._traced import traced
from ._base_service import BaseService

logger: logging.Logger = logging.getLogger("uipath")


class ConnectionsService(BaseService):
    """Service for managing UiPath external service connections.

    This service provides methods to retrieve direct connection information retrieval
    and secure token management.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(
        name="connections_retrieve",
        run_type="uipath",
        hide_output=True,
    )
    def retrieve(self, key: str) -> Connection:
        """Retrieve connection details by its key.

        This method fetches the configuration and metadata for a connection,
        which can be used to establish communication with an external service.

        Args:
            key (str): The unique identifier of the connection to retrieve.

        Returns:
            Connection: The connection details, including configuration parameters
                and authentication information.
        """
        spec = self._retrieve_spec(key)
        response = self.request(spec.method, url=spec.endpoint)
        return Connection.model_validate(response.json())

    @traced(
        name="connections_retrieve",
        run_type="uipath",
        hide_output=True,
    )
    async def retrieve_async(self, key: str) -> Connection:
        """Asynchronously retrieve connection details by its key.

        This method fetches the configuration and metadata for a connection,
        which can be used to establish communication with an external service.

        Args:
            key (str): The unique identifier of the connection to retrieve.

        Returns:
            Connection: The connection details, including configuration parameters
                and authentication information.
        """
        spec = self._retrieve_spec(key)
        response = await self.request_async(spec.method, url=spec.endpoint)
        return Connection.model_validate(response.json())

    @traced(
        name="connections_retrieve_token",
        run_type="uipath",
        hide_output=True,
    )
    def retrieve_token(
        self, key: str, token_type: ConnectionTokenType = ConnectionTokenType.DIRECT
    ) -> ConnectionToken:
        """Retrieve an authentication token for a connection.

        This method obtains a fresh authentication token that can be used to
        communicate with the external service. This is particularly useful for
        services that use token-based authentication.

        Args:
            key (str): The unique identifier of the connection.
            token_type (ConnectionTokenType): The token type to use.

        Returns:
            ConnectionToken: The authentication token details, including the token
                value and any associated metadata.
        """
        spec = self._retrieve_token_spec(key, token_type)
        response = self.request(spec.method, url=spec.endpoint, params=spec.params)
        return ConnectionToken.model_validate(response.json())

    @traced(
        name="connections_retrieve_token",
        run_type="uipath",
        hide_output=True,
    )
    async def retrieve_token_async(
        self, key: str, token_type: ConnectionTokenType = ConnectionTokenType.DIRECT
    ) -> ConnectionToken:
        """Asynchronously retrieve an authentication token for a connection.

        This method obtains a fresh authentication token that can be used to
        communicate with the external service. This is particularly useful for
        services that use token-based authentication.

        Args:
            key (str): The unique identifier of the connection.
            token_type (ConnectionTokenType): The token type to use.

        Returns:
            ConnectionToken: The authentication token details, including the token
                value and any associated metadata.
        """
        spec = self._retrieve_token_spec(key, token_type)
        response = await self.request_async(
            spec.method, url=spec.endpoint, params=spec.params
        )
        return ConnectionToken.model_validate(response.json())

    @traced(
        name="connections_retrieve_event_payload",
        run_type="uipath",
    )
    @infer_bindings(resource_type="ignored", ignore=True)
    def retrieve_event_payload(self, event_args: EventArguments) -> Dict[str, Any]:
        """Retrieve event payload from UiPath Integration Service.

        Args:
            event_args (EventArguments): The event arguments. Should be passed along from the job's input.

        Returns:
            Dict[str, Any]: The event payload data
        """
        if not event_args.additional_event_data:
            raise ValueError("additional_event_data is required")

        # Parse additional event data to get event id
        event_data = json.loads(event_args.additional_event_data)

        event_id = None
        if "processedEventId" in event_data:
            event_id = event_data["processedEventId"]
        elif "rawEventId" in event_data:
            event_id = event_data["rawEventId"]
        else:
            raise ValueError("Event Id not found in additional event data")

        # Build request URL using connection token's API base URI
        spec = self._retrieve_event_payload_spec("v1", event_id)

        response = self.request(spec.method, url=spec.endpoint)

        return response.json()

    @traced(
        name="connections_retrieve_event_payload",
        run_type="uipath",
    )
    @infer_bindings(resource_type="ignored", ignore=True)
    async def retrieve_event_payload_async(
        self, event_args: EventArguments
    ) -> Dict[str, Any]:
        """Retrieve event payload from UiPath Integration Service.

        Args:
            event_args (EventArguments): The event arguments. Should be passed along from the job's input.

        Returns:
            Dict[str, Any]: The event payload data
        """
        if not event_args.additional_event_data:
            raise ValueError("additional_event_data is required")

        # Parse additional event data to get event id
        event_data = json.loads(event_args.additional_event_data)

        event_id = None
        if "processedEventId" in event_data:
            event_id = event_data["processedEventId"]
        elif "rawEventId" in event_data:
            event_id = event_data["rawEventId"]
        else:
            raise ValueError("Event Id not found in additional event data")

        # Build request URL using connection token's API base URI
        spec = self._retrieve_event_payload_spec("v1", event_id)

        response = await self.request_async(spec.method, url=spec.endpoint)

        return response.json()

    def _retrieve_event_payload_spec(self, version: str, event_id: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/elements_/{version}/events/{event_id}"),
        )

    def _retrieve_spec(self, key: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}"),
        )

    def _retrieve_token_spec(
        self, key: str, token_type: ConnectionTokenType = ConnectionTokenType.DIRECT
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}/token"),
            params={"tokenType": token_type.value},
        )
