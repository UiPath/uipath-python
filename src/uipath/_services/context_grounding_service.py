import json
from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._models import IngestionInProgressException
from .._models.context_grounding import ContextGroundingQueryResponse
from .._models.context_grounding_index import ContextGroundingIndex
from .._utils import Endpoint, RequestSpec
from .._utils.constants import (
    HEADER_FOLDER_KEY,
    ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE,
)
from ._base_service import BaseService
from .folder_service import FolderService


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

    def __init__(
        self,
        config: Config,
        execution_context: ExecutionContext,
        folders_service: FolderService,
    ) -> None:
        self._folders_service = folders_service
        super().__init__(config=config, execution_context=execution_context)

    def retrieve(self, name: str) -> Optional[ContextGroundingIndex]:
        """Retrieve context grounding index information by its name.

        This method fetches details about a specific context index, which can be
        used to understand what type of contextual information is available for
        automation processes.

        Args:
            name (str): The name of the context index to retrieve.

        Returns:
            Optional[ContextGroundingIndex]: The index information, including its configuration and metadata if found, otherwise None.
        """
        spec = self._retrieve_spec(name)

        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
        ).json()
        return next(
            (
                ContextGroundingIndex.model_validate(item)
                for item in response["value"]
                if item["name"] == name
            ),
            None,
        )

    async def retrieve_async(self, name: str) -> Optional[ContextGroundingIndex]:
        """Retrieve asynchronously context grounding index information by its name.

        This method fetches details about a specific context index, which can be
        used to understand what type of contextual information is available for
        automation processes.

        Args:
            name (str): The name of the context index to retrieve.

        Returns:
            Optional[ContextGroundingIndex]: The index information, including its configuration and metadata if found, otherwise None.

        """
        spec = self._retrieve_spec(name)

        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                params=spec.params,
            )
        ).json()
        return next(
            (
                ContextGroundingIndex.model_validate(item)
                for item in response["value"]
                if item["name"] == name
            ),
            None,
        )

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
        index = self.retrieve(name)
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=name)

        spec = self._search_spec(name, query, number_of_results)

        response = self.request(
            spec.method,
            spec.endpoint,
            content=spec.content,
        )

        return TypeAdapter(List[ContextGroundingQueryResponse]).validate_python(
            response.json()
        )

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
        index = self.retrieve(name)
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=name)
        spec = self._search_spec(name, query, number_of_results)

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            content=spec.content,
        )

        return TypeAdapter(List[ContextGroundingQueryResponse]).validate_python(
            response.json()
        )

    def get_or_create_index(
        self,
        name: str,
        *,
        description: Optional[str] = None,
        storage_bucket_name: str,
        file_name_glob: Optional[str] = None,
        storage_bucket_folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        spec = self._create_spec(
            name,
            description,
            storage_bucket_name,
            file_name_glob,
            storage_bucket_folder_path,
        )
        index = self.retrieve(name=name)
        if index:
            return index

        response = self.request(
            spec.method,
            spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        ).json()
        return ContextGroundingIndex.model_validate(response)

    async def get_or_create_index_async(
        self,
        name: str,
        *,
        description: Optional[str] = None,
        storage_bucket_name: str,
        file_name_glob: Optional[str] = None,
        storage_bucket_folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        index = await self.retrieve_async(name=name)
        if index:
            return index

        spec = self._create_spec(
            name,
            description,
            storage_bucket_name,
            file_name_glob,
            storage_bucket_folder_path,
        )
        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                content=spec.content,
                headers=spec.headers,
            )
        ).json()
        return ContextGroundingIndex.model_validate(response)

    def ingest_data(self, index: ContextGroundingIndex) -> None:
        if not index.id:
            return
        spec = self._ingest_spec(index.id)
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    async def ingest_data_async(self, index: ContextGroundingIndex) -> None:
        if not index.id:
            return
        spec = self._ingest_spec(index.id)
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    def delete_index(self, index: ContextGroundingIndex) -> None:
        if not index.id:
            return
        spec = self._delete_by_id_spec(index.id)
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    async def delete_index_async(self, index: ContextGroundingIndex) -> None:
        if not index.id:
            return
        spec = self._delete_by_id_spec(index.id)
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        self._folder_key = self._folder_key or (
            self._folders_service.retrieve_key_by_folder_path(self._folder_path)
            if self._folder_path
            else None
        )

        if self._folder_key is None:
            raise ValueError(f"Folder key is not set ({HEADER_FOLDER_KEY})")

        return self.folder_headers

    def _ingest_spec(self, key: str) -> RequestSpec:
        return RequestSpec(
            method="POST", endpoint=Endpoint(f"/ecs_/v2/indexes/{key}/ingest")
        )

    def _retrieve_spec(self, name: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/ecs_/v2/indexes"),
            params={"$filter": f"Name eq '{name}'"},
        )

    def _create_spec(
        self,
        name: str,
        description: Optional[str],
        storage_bucket_name: Optional[str],
        file_name_glob: Optional[str],
        storage_bucket_folder_path: Optional[str],
    ) -> RequestSpec:
        storage_bucket_folder_path = (
            storage_bucket_folder_path
            if storage_bucket_folder_path
            else self._folder_path
        )
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/v2/indexes/create"),
            content=json.dumps(
                {
                    "name": name,
                    "description": description,
                    "dataSource": {
                        "@odata.type": ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE,
                        "folder": storage_bucket_folder_path,
                        "bucketName": storage_bucket_name,
                        "fileNameGlob": file_name_glob
                        if file_name_glob is not None
                        else "*",
                        "directoryPath": "/",
                    },
                }
            ),
        )

    def _retrieve_by_id_spec(self, id: str) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{id}"),
        )

    def _delete_by_id_spec(self, id: str) -> RequestSpec:
        return RequestSpec(
            method="DELETE",
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
