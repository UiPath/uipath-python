import json
from typing import Any, Dict, List

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models.context_grounding import ContextGroundingQueryResponse
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


class ContextGroundingService(FolderContext, BaseService):
    """Service for managing semantic automation contexts in UiPath.

    Context Grounding is a feature that helps in understanding and managing the
    semantic context in which automation processes operate. It provides capabilities
    for indexing, retrieving, and searching through contextual information that
    can be used to enhance AI-enabled automation.

    This service requires a valid folder key to be set in the environment, as
    context grounding operations are always performed within a specific folder
    context.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(self, name: str) -> Any:
        """Retrieve context grounding index information by its name.

        This method fetches details about a specific context index, which can be
        used to understand what type of contextual information is available for
        automation processes.

        Args:
            name (str): The name of the context index to retrieve.

        Returns:
            Any: The index information, including its configuration and metadata.
        """
        spec = self._retrieve_spec(name)

        return self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
        ).json()

    async def retrieve_async(self, name: str) -> Any:
        """Retrieve asynchronously context grounding index information by its name.

        This method fetches details about a specific context index, which can be
        used to understand what type of contextual information is available for
        automation processes.

        Args:
            name (str): The name of the context index to retrieve.

        Returns:
            Any: The index information, including its configuration and metadata.

        """
        spec = self._retrieve_spec(name)

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
        )

        return response.json()

    def retrieve_by_id(self, id: str) -> Any:
        """Retrieve context grounding index information by its ID.

        This method provides direct access to a context index using its unique
        identifier, which can be more efficient than searching by name.

        Args:
            id (str): The unique identifier of the context index.

        Returns:
            Any: The index information, including its configuration and metadata.
        """
        spec = self._retrieve_by_id_spec(id)

        return self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
        ).json()

    async def retrieve_by_id_async(self, id: str) -> Any:
        """Retrieve asynchronously context grounding index information by its ID.

        This method provides direct access to a context index using its unique
        identifier, which can be more efficient than searching by name.

        Args:
            id (str): The unique identifier of the context index.

        Returns:
            Any: The index information, including its configuration and metadata.

        """
        spec = self._retrieve_by_id_spec(id)

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
        )

        return response.json()

    def search(
        self,
        name: str,
        query: str,
        number_of_results: int = 10,
    ) -> List[ContextGroundingQueryResponse]:
        """Search for contextual information within a specific index.

        This method performs a semantic search against the specified context index,
        helping to find relevant information that can be used in automation processes.
        The search is powered by AI and understands natural language queries.

        Args:
            name (str): The name of the context index to search in.
            query (str): The search query in natural language.
            number_of_results (int, optional): Maximum number of results to return.
                Defaults to 10.

        Returns:
            List[ContextGroundingQueryResponse]: A list of search results, each containing
                relevant contextual information and metadata.
        """
        spec = self._search_spec(name, query, number_of_results)

        return self.request(
            spec.method,
            spec.endpoint,
            content=spec.content,
        ).json()

    async def search_async(
        self,
        name: str,
        query: str,
        number_of_results: int = 10,
    ) -> List[ContextGroundingQueryResponse]:
        """Search asynchronously for contextual information within a specific index.

        This method performs a semantic search against the specified context index,
        helping to find relevant information that can be used in automation processes.
        The search is powered by AI and understands natural language queries.

        Args:
            name (str): The name of the context index to search in.
            query (str): The search query in natural language.
            number_of_results (int, optional): Maximum number of results to return.
                Defaults to 10.

        Returns:
            List[ContextGroundingQueryResponse]: A list of search results, each containing
                relevant contextual information and metadata.
        """
        spec = self._search_spec(name, query, number_of_results)

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            content=spec.content,
        )

        return response.json()

    @property
    def custom_headers(self) -> Dict[str, str]:
        if self.folder_headers["x-uipath-folderkey"] is None:
            raise ValueError("Folder key is not set (UIPATH_FOLDER_KEY)")

        return self.folder_headers

    def _retrieve_spec(self, name: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/ecs_/v2/indexes"),
            params={"$filter": f"Name eq '{name}'"},
        )

    def _retrieve_by_id_spec(self, id: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{id}"),
        )

    def _search_spec(
        self, name: str, query: str, number_of_results: int = 10
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/v1/search"),
            content=json.dumps(
                {
                    "query": {"query": query, "numberOfResults": number_of_results},
                    "schema": {"name": name},
                }
            ),
        )
