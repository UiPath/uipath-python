import json
from typing import Any, Dict, List

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models.context_grounding import ContextGroundingQueryResponse
from .._utils import Endpoint
from ._base_service import BaseService


class ContextGroundingService(FolderContext, BaseService):
    """
    Service for managing semantic automation contexts in UiPath.

    Context Grounding is a feature that helps in understanding and managing the
    semantic context in which automation processes operate. It provides capabilities
    for indexing, retrieving, and searching through contextual information that
    can be used to enhance AI-enabled automation.

    This service requires a valid folder key to be set in the environment, as
    context grounding operations are always performed within a specific folder
    context.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        """
        Initialize the context grounding service.

        Args:
            config (Config): Configuration object containing API settings.
            execution_context (ExecutionContext): Context object containing execution-specific
                information.
        """
        super().__init__(config=config, execution_context=execution_context)

    def retrieve_by_name(self, index_name: str) -> Any:
        """
        Retrieve context grounding index information by its name.

        This method fetches details about a specific context index, which can be
        used to understand what type of contextual information is available for
        automation processes.

        Args:
            index_name (str): The name of the context index to retrieve.

        Returns:
            Any: The index information, including its configuration and metadata.

        Example:
            ```python
            # Get details about a specific context index
            index = context_grounding_service.retrieve_by_name("customer-support-index")
            print(f"Index status: {index['status']}")
            ```
        """
        endpoint = Endpoint("/ecs_/v2/indexes")

        return self.request(
            "GET",
            endpoint,
            params={"$filter": f"Name eq '{index_name}'"},
        ).json()

    def retrieve_by_id(self, index_id: str) -> Any:
        """
        Retrieve context grounding index information by its ID.

        This method provides direct access to a context index using its unique
        identifier, which can be more efficient than searching by name.

        Args:
            index_id (str): The unique identifier of the context index.

        Returns:
            Any: The index information, including its configuration and metadata.

        Example:
            ```python
            # Get details about a context index using its ID
            index = context_grounding_service.retrieve_by_id("idx-123-abc")
            print(f"Index type: {index['type']}")
            ```
        """
        endpoint = Endpoint(f"/ecs_/v2/indexes/{index_id}")

        return self.request("GET", endpoint).json()

    def search(
        self, index_name: str, query: str, number_of_results: int = 10
    ) -> List[ContextGroundingQueryResponse]:
        """
        Search for contextual information within a specific index.

        This method performs a semantic search against the specified context index,
        helping to find relevant information that can be used in automation processes.
        The search is powered by AI and understands natural language queries.

        Args:
            index_name (str): The name of the context index to search in.
            query (str): The search query in natural language.
            number_of_results (int, optional): Maximum number of results to return.
                Defaults to 10.

        Returns:
            List[ContextGroundingQueryResponse]: A list of search results, each containing
                relevant contextual information and metadata.

        Example:
            ```python
            # Search for customer support information
            results = context_grounding_service.search(
                index_name="customer-support-index",
                query="How to handle refund requests",
                number_of_results=5
            )
            for result in results:
                print(f"Found: {result.content}")
            ```
        """
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
        """
        Get custom headers for context grounding requests.

        This property ensures that a folder key is available for context grounding
        operations, as they must be performed within a specific folder context.

        Returns:
            Dict[str, str]: Headers containing folder context information.

        Raises:
            ValueError: If the folder key is not set in the environment.
        """
        if self.folder_headers["x-uipath-folderkey"] is None:
            raise ValueError("Folder key is not set (UIPATH_FOLDER_KEY)")

        return self.folder_headers
