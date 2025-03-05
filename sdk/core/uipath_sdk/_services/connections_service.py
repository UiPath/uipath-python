from typing import Any, Protocol, TypeVar, Union

from uipath_sdk._utils._endpoint import Endpoint

from .._config import Config
from .._execution_context import ExecutionContext
from .._models.connections import ConnectionPing
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

    def __call__(
        self, connector: Connector[T_co], instance_id: Union[str, int]
    ) -> T_co:
        return connector(client=self.client, instance_id=instance_id)

    def token(self, instance_id: int) -> ConnectionPing:
        response = self.request(
            "GET",
            Endpoint(f"/elements_/v3/element/instances/{instance_id}/ping"),
            params={"forcePing": True, "disableOnFailure": True},
        )

        return ConnectionPing.model_validate(response.json())
