import importlib
import logging
from typing import Any, Dict, Protocol, TypeVar, Union

from .._config import Config
from .._execution_context import ExecutionContext
from .._models import Connection, ConnectionToken
from .._utils import Endpoint, RequestSpec
from .._utils.constants import ENTRYPOINT
from ._base_service import BaseService

T_co = TypeVar("T_co", covariant=True)

logger: logging.Logger = logging.getLogger("uipath")


class PluginNotFoundError(AttributeError):
    """Raised when a plugin is not installed or failed to load."""

    pass


class Connector(Protocol[T_co]):
    def __call__(self, *, client: Any, instance_id: Union[str, int]) -> T_co: ...


class ConnectionsService(BaseService):
    """Service for managing UiPath external service connections.

    This service provides methods to retrieve and manage connections to external
    systems and services that your automation processes interact with. It supports
    both direct connection information retrieval and secure token management.

    The service implements a flexible connector system that allows for type-safe
    instantiation of specific service connectors, making it easier to interact
    with different types of external services.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._plugins: Dict[str, Any] = {}
        self._plugins_loaded = False
        self._load_connectors()

    def __call__(self, connector: Connector[T_co], key: str) -> T_co:
        connection = self.retrieve(key)
        return connector(client=self.client, instance_id=connection.elementInstanceId)

    def __getattr__(self, name: str) -> Any:
        """Get a plugin by name.

        Args:
            name: The name of the plugin to get

        Returns:
            The plugin instance

        Raises:
            PluginNotFoundError: If the plugin is not installed
            ImportError: If the plugin fails to load
        """
        if not self._plugins_loaded:
            self._load_connectors()

        if name in self._plugins:
            return self._plugins[name]

        try:
            plugin: Any = getattr(self.client, name)
            self._plugins[name] = plugin
            return plugin
        except AttributeError as e:
            raise PluginNotFoundError(f"Plugin '{name}' is not installed") from e

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

    def retrieve_token(self, key: str) -> ConnectionToken:
        """Retrieve an authentication token for a connection.

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
        response = self.request(spec.method, url=spec.endpoint, params=spec.params)
        return ConnectionToken.model_validate(response.json())

    async def retrieve_token_async(self, key: str) -> ConnectionToken:
        """Asynchronously retrieve an authentication token for a connection.

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
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}"),
        )

    def _retrieve_token_spec(self, key: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/connections_/api/v1/Connections/{key}/token"),
            params={"type": "direct"},
        )

    def _load_connectors(self) -> None:
        """Load all available connector plugins.

        Raises:
            ImportError: If a plugin fails to load
        """
        try:
            entry_points: Any = importlib.metadata.entry_points()
            if hasattr(entry_points, "select"):
                connectors = list(entry_points.select(group=ENTRYPOINT))
            else:
                connectors = list(entry_points.get(ENTRYPOINT, []))

            for entry_point in connectors:
                try:
                    register_func = entry_point.load()
                    register_func(self)
                except Exception as e:
                    logger.error(
                        f"[ERROR] Failed to load plugin {entry_point.name}: {str(e)}"
                    )

            self._plugins_loaded = True
        except Exception as e:
            self._plugins_loaded = False
            raise ImportError(f"Failed to load plugins: {str(e)}") from e
