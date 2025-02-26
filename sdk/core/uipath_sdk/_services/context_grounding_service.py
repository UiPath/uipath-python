import json
from typing import Any, Dict, List

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models.context_grounding import ContextGroundingQueryResponse
from .._utils import Endpoint
from ._base_service import BaseService


class ContextGroundingService(FolderContext, BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve_by_name(self, index_name: str) -> Any:
        endpoint = Endpoint("/ecs_/v2/indexes")

        return self.request(
            "GET",
            endpoint,
            params={"$filter": f"Name eq '{index_name}'"},
        ).json()

    def retrieve_by_id(self, index_id: str) -> Any:
        endpoint = Endpoint(f"/ecs_/v2/indexes/{index_id}")

        return self.request("GET", endpoint).json()

    def search(
        self, index_name: str, query: str, number_of_results: int = 10
    ) -> List[ContextGroundingQueryResponse]:
        endpoint = Endpoint("/ecs_/v1/search")

        content = json.dumps(
            {
                "query": {"query": query, "numberOfResults": number_of_results},
                "schema": {"name": index_name},
            }
        )
        return self.request("POST", endpoint, content=content).json()

    @property
    def custom_headers(self) -> Dict[str, str]:
        if self.folder_headers["x-uipath-folderkey"] is None:
            raise ValueError("Folder key is not set (UIPATH_FOLDER_KEY)")

        return self.folder_headers
