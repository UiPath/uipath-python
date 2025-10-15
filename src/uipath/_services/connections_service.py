import json
import logging
from typing import Any, Dict, List, Optional

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint, RequestSpec, header_folder, infer_bindings
from ..models import Connection, ConnectionMetadata, ConnectionToken, EventArguments
from ..models.connections import ConnectionTokenType
from ..tracing._traced import traced
from ._base_service import BaseService
from .folder_service import FolderService

logger: logging.Logger = logging.getLogger("uipath")


class ConnectionsService(BaseService):
    """Service for managing UiPath external service connections.

    This service provides methods to retrieve direct connection information retrieval
    and secure token management.
    """

    def __init__(
        self,
        config: Config,
        execution_context: ExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

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
        name="connections_metadata",
        run_type="uipath",
        hide_output=True,
    )
    def metadata(
        self, element_instance_id: int, tool_path: str, schema_mode: bool = True
    ) -> ConnectionMetadata:
        """Synchronously retrieve connection API metadata.

        This method fetches the metadata for a connection,
        which can be used to establish communication with an external service.

        Args:
            element_instance_id (int): The element instance ID of the connection.
            tool_path (str): The tool path to retrieve metadata for.
            schema_mode (bool): Whether or not to represent the output schema in the response fields.

        Returns:
            ConnectionMetadata: The connection metadata.
        """
        spec = self._metadata_spec(element_instance_id, tool_path, schema_mode)
        response = self.request(spec.method, url=spec.endpoint, headers=spec.headers)
        return ConnectionMetadata.model_validate(response.json())

    @traced(name="connections_list", run_type="uipath")
    def list(
        self,
        *,
        name: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        connector_key: Optional[str] = None,
        skip: Optional[int] = None,
        top: Optional[int] = None,
    ) -> List[Connection]:
        """Lists all connections with optional filtering.

        Args:
            name: Optional connection name to filter (supports partial matching)
            folder_path: Optional folder path for filtering connections
            folder_key: Optional folder key (mutually exclusive with folder_path)
            connector_key: Optional connector key to filter by specific connector type
            skip: Number of records to skip (for pagination)
            top: Maximum number of records to return

        Returns:
            List[Connection]: List of connection instances

        Raises:
            ValueError: If both folder_path and folder_key are provided together, or if
                folder_path is provided but cannot be resolved to a folder_key

        Examples:
            >>> # List all connections
            >>> connections = sdk.connections.list()

            >>> # Find connections by name
            >>> salesforce_conns = sdk.connections.list(name="Salesforce")

            >>> # List all Slack connections in Finance folder
            >>> connections = sdk.connections.list(
            ...     folder_path="Finance",
            ...     connector_key="uipath-slack"
            ... )
        """
        spec = self._list_spec(
            name=name,
            folder_path=folder_path,
            folder_key=folder_key,
            connector_key=connector_key,
            skip=skip,
            top=top,
        )
        response = self.request(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        )

        return self._parse_and_validate_list_response(response)

    @traced(name="connections_list", run_type="uipath")
    async def list_async(
        self,
        *,
        name: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        connector_key: Optional[str] = None,
        skip: Optional[int] = None,
        top: Optional[int] = None,
    ) -> List[Connection]:
        """Asynchronously lists all connections with optional filtering.

        Args:
            name: Optional connection name to filter (supports partial matching)
            folder_path: Optional folder path for filtering connections
            folder_key: Optional folder key (mutually exclusive with folder_path)
            connector_key: Optional connector key to filter by specific connector type
            skip: Number of records to skip (for pagination)
            top: Maximum number of records to return

        Returns:
            List[Connection]: List of connection instances

        Raises:
            ValueError: If both folder_path and folder_key are provided together, or if
                folder_path is provided but cannot be resolved to a folder_key

        Examples:
            >>> # List all connections
            >>> connections = await sdk.connections.list_async()

            >>> # Find connections by name
            >>> salesforce_conns = await sdk.connections.list_async(name="Salesforce")

            >>> # List all Slack connections in Finance folder
            >>> connections = await sdk.connections.list_async(
            ...     folder_path="Finance",
            ...     connector_key="uipath-slack"
            ... )
        """
        spec = self._list_spec(
            name=name,
            folder_path=folder_path,
            folder_key=folder_key,
            connector_key=connector_key,
            skip=skip,
            top=top,
        )
        response = await self.request_async(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        )

        return self._parse_and_validate_list_response(response)

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
        name="connections_metadata",
        run_type="uipath",
        hide_output=True,
    )
    async def metadata_async(
        self, element_instance_id: int, tool_path: str, schema_mode: bool = True
    ) -> ConnectionMetadata:
        """Asynchronously retrieve connection API metadata.

        This method fetches the metadata for a connection,
        which can be used to establish communication with an external service.

        Args:
            element_instance_id (int): The element instance ID of the connection.
            tool_path (str): The tool path to retrieve metadata for.
            schema_mode (bool): Whether or not to represent the output schema in the response fields.

        Returns:
            ConnectionMetadata: The connection metadata.
        """
        spec = self._metadata_spec(element_instance_id, tool_path, schema_mode)
        response = await self.request_async(
            spec.method, url=spec.endpoint, headers=spec.headers
        )
        return ConnectionMetadata.model_validate(response.json())

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

    def _metadata_spec(
        self, element_instance_id: int, tool_path: str, schema_mode: bool
    ) -> RequestSpec:
        metadata_endpoint_url = f"/elements_/v3/element/instances/{element_instance_id}/elements/{tool_path}/metadata"
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(metadata_endpoint_url),
            headers={
                "accept": "application/schema+json"
                if schema_mode
                else "application/json"
            },
        )

    def _retrieve_token_spec(
        self, key: str, token_type: ConnectionTokenType = ConnectionTokenType.DIRECT
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}/token"),
            params={"tokenType": token_type.value},
        )

    def _parse_and_validate_list_response(self, response: Response) -> List[Connection]:
        """Parse and validate the list response from the API.

        Handles both OData response format (with 'value' field) and raw list responses.

        Args:
            response: The HTTP response from the API

        Returns:
            List of validated Connection instances
        """
        data = response.json()

        # Handle both OData responses (dict with 'value') and raw list responses
        if isinstance(data, dict):
            connections_data = data.get("value", [])
        elif isinstance(data, list):
            connections_data = data
        else:
            connections_data = []

        return [Connection.model_validate(conn) for conn in connections_data]

    def _list_spec(
        self,
        name: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        connector_key: Optional[str] = None,
        skip: Optional[int] = None,
        top: Optional[int] = None,
    ) -> RequestSpec:
        """Build the request specification for listing connections.

        Args:
            name: Optional connection name to filter (supports partial matching)
            folder_path: Optional folder path for filtering connections
            folder_key: Optional folder key (mutually exclusive with folder_path)
            connector_key: Optional connector key to filter by specific connector type
            skip: Number of records to skip (for pagination)
            top: Maximum number of records to return

        Returns:
            RequestSpec with endpoint, params, and headers configured

        Raises:
            ValueError: If both folder_path and folder_key are provided together, or if
                folder_path is provided but cannot be resolved to a folder_key
        """
        # Validate mutual exclusivity of folder_path and folder_key
        if folder_path is not None and folder_key is not None:
            raise ValueError(
                "folder_path and folder_key are mutually exclusive and cannot be provided together"
            )

        # Resolve folder_path to folder_key if needed
        resolved_folder_key = folder_key
        if not resolved_folder_key and folder_path:
            resolved_folder_key = self._folders_service.retrieve_key(
                folder_path=folder_path
            )
            if not resolved_folder_key:
                raise ValueError(f"Folder with path '{folder_path}' not found")

        # Build OData filters
        filters = []
        if name:
            # Escape single quotes in name for OData
            escaped_name = name.replace("'", "''")
            filters.append(f"contains(Name, '{escaped_name}')")
        if connector_key:
            filters.append(f"connector/key eq '{connector_key}'")

        params = {}
        if filters:
            params["$filter"] = " and ".join(filters)
        if skip is not None:
            params["$skip"] = str(skip)
        if top is not None:
            params["$top"] = str(top)

        # Always expand connector and folder for complete information
        params["$expand"] = "connector,folder"

        # Use header_folder which handles validation
        headers = header_folder(resolved_folder_key, None)

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/connections_/api/v1/Connections"),
            params=params,
            headers=headers,
        )
