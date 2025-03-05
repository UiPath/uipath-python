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
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def __call__(self, connector: Connector[T_co], key: str) -> T_co:
        connection = self.retrieve(key)
        return connector(client=self.client, instance_id=connection.elementInstanceId)

    def retrieve(self, key: str) -> Connection:
        """
        Retrieves a connection by key.
        """

        spec = self._retrieve_spec(key)
        response = self.request(spec.method, url=spec.endpoint)
        return Connection.model_validate(response.json())

    async def retrieve_async(self, key: str) -> Connection:
        """
        Retrieves a connection by key asynchronously.
        """

        spec = self._retrieve_spec(key)
        response = await self.request_async(spec.method, url=spec.endpoint)
        return Connection.model_validate(response.json())

    def retrieve_token(self, key: str) -> ConnectionToken:
        """
        Retrieves a token for a connection by key.
        """

        spec = self._retrieve_token_spec(key)
        response = self.request(spec.method, url=spec.endpoint, params=spec.params)
        return ConnectionToken.model_validate(response.json())

    async def retrieve_token_async(self, key: str) -> ConnectionToken:
        """
        Retrieves a token for a connection by key asynchronously.
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
