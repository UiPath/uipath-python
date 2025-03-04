from uipath_sdk._utils._endpoint import Endpoint

from .._config import Config
from .._execution_context import ExecutionContext
from .._models.connections import ConnectionPing
from ._base_service import BaseService


class ConnectionsService(BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def token(self, elementInstanceId: int) -> ConnectionPing:
        response = self.request(
            "GET",
            Endpoint(f"/elements_/v3/element/instances/{elementInstanceId}/ping"),
            params={"forcePing": True, "disableOnFailure": True},
        )

        return ConnectionPing.model_validate(response.json())
