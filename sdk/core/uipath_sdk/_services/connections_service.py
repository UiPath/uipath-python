from typing import Any, Protocol, TypeVar, Union

from .._config import Config
from .._execution_context import ExecutionContext
from .._models import Connection, ConnectionToken
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService

T_co = TypeVar("T_co", covariant=True)


class Connector(Protocol[T_co]):
    """
    A protocol for connectors.
    This helps with type inference when instantiating the connector.
    Even if we have here a callable, the actual connector should be a class.
    """

    def __call__(self, *, client: Any, instance_id: Union[str, int]) -> T_co: ...


class ConnectionsService(BaseService):
    """
    Service for managing UiPath external service connections.

    This service provides methods to retrieve and manage connections to external
    systems and services that your automation processes interact with. It supports
    both direct connection information retrieval and secure token management.

    The service implements a flexible connector system that allows for type-safe
    instantiation of specific service connectors, making it easier to interact
    with different types of external services.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        """
        Initialize the connections service.

        Args:
            config (Config): Configuration object containing API settings.
            execution_context (ExecutionContext): Context object containing execution-specific
                information.
        """
        super().__init__(config=config, execution_context=execution_context)

    def __call__(self, connector: Connector[T_co], key: str) -> T_co:
        """
        Create a typed connector instance for a specific connection.

        This method provides a convenient way to create strongly-typed connectors
        for specific external services. It automatically retrieves the connection
        information and instantiates the appropriate connector type.

        Args:
            connector (Connector[T_co]): The connector class to instantiate.
            key (str): The unique identifier of the connection to use.

        Returns:
            T_co: An instance of the specified connector type, configured with
                the connection details.

        Example:
            ```python
            # Create a typed connector for a specific service
            service_connector = connections_service(ServiceConnector, "my-connection-key")
            result = service_connector.perform_operation()
            ```
        """
        connection = self.retrieve(key)
        return connector(client=self.client, instance_id=connection.elementInstanceId)

    def retrieve(self, key: str) -> Connection:
        """
        Retrieve connection details by its key.

        This method fetches the configuration and metadata for a connection,
        which can be used to establish communication with an external service.

        Args:
            key (str): The unique identifier of the connection to retrieve.

        Returns:
            Connection: The connection details, including configuration parameters
                and authentication information.

        Example:
            ```python
            # Get details for a specific connection
            connection = connections_service.retrieve("my-connection-key")
            print(f"Connection instance ID: {connection.elementInstanceId}")
            ```
        """
        spec = self._retrieve_spec(key)
        response = self.request(spec.method, url=spec.endpoint)
        return Connection.model_validate(response.json())

    async def retrieve_async(self, key: str) -> Connection:
        """
        Asynchronously retrieve connection details by its key.

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

    def retrieve_token(self, key: str) -> ConnectionToken:
        """
        Retrieve an authentication token for a connection.

        This method obtains a fresh authentication token that can be used to
        communicate with the external service. This is particularly useful for
        services that use token-based authentication.

        Args:
            key (str): The unique identifier of the connection.

        Returns:
            ConnectionToken: The authentication token details, including the token
                value and any associated metadata.

        Example:
            ```python
            # Get an authentication token for a connection
            token = connections_service.retrieve_token("my-connection-key")
            print(f"Token type: {token.token_type}")
            ```
        """
        spec = self._retrieve_token_spec(key)
        response = self.request(spec.method, url=spec.endpoint, params=spec.params)
        return ConnectionToken.model_validate(response.json())

    async def retrieve_token_async(self, key: str) -> ConnectionToken:
        """
        Asynchronously retrieve an authentication token for a connection.

        This method obtains a fresh authentication token that can be used to
        communicate with the external service. This is particularly useful for
        services that use token-based authentication.

        Args:
            key (str): The unique identifier of the connection.

        Returns:
            ConnectionToken: The authentication token details, including the token
                value and any associated metadata.
        """
        spec = self._retrieve_token_spec(key)
        response = await self.request_async(
            spec.method, url=spec.endpoint, params=spec.params
        )
        return ConnectionToken.model_validate(response.json())

    def _retrieve_spec(self, key: str) -> RequestSpec:
        """
        Create a request specification for retrieving connection details.

        Args:
            key (str): The unique identifier of the connection.

        Returns:
            RequestSpec: The request specification for the API call.
        """
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}"),
        )

    def _retrieve_token_spec(self, key: str) -> RequestSpec:
        """
        Create a request specification for retrieving a connection token.

        Args:
            key (str): The unique identifier of the connection.

        Returns:
            RequestSpec: The request specification for the API call.
        """
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}/token"),
            params={"type": "direct"},
        )
