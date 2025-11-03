import json
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from pydantic import TypeAdapter
from typing_extensions import deprecated

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder, resource_override
from .._utils.constants import (
    CONFLUENCE_DATA_SOURCE,
    DROPBOX_DATA_SOURCE,
    GOOGLE_DRIVE_DATA_SOURCE,
    LLMV4,
    ONEDRIVE_DATA_SOURCE,
    ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE,
)
from ..models import IngestionInProgressException
from ..models.context_grounding import ContextGroundingQueryResponse
from ..models.context_grounding_index import ContextGroundingIndex
from ..tracing import traced
from ._base_service import BaseService
from .buckets_service import BucketsService
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
        buckets_service: BucketsService,
    ) -> None:
        self._folders_service = folders_service
        self._buckets_service = buckets_service
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="add_to_index", run_type="uipath")
    @resource_override(resource_type="index")
    def add_to_index(
        self,
        name: str,
        blob_file_path: str,
        content_type: Optional[str] = None,
        content: Optional[Union[str, bytes]] = None,
        source_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        ingest_data: bool = True,
    ) -> None:
        """Add content to the index.

        Args:
            name (str): The name of the index to add content to.
            content_type (Optional[str]): The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream".
            blob_file_path (str): The path where the blob will be stored in the storage bucket.
            content (Optional[Union[str, bytes]]): The content to be added, either as a string or bytes.
            source_path (Optional[str]): The source path of the content if it is being uploaded from a file.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.
            ingest_data (bool): Whether to ingest data in the index after content is uploaded. Defaults to True.

        Raises:
            ValueError: If neither content nor source_path is provided, or if both are provided.
        """
        if not (content or source_path):
            raise ValueError("Content or source_path is required")
        if content and source_path:
            raise ValueError("Content and source_path are mutually exclusive")

        index = self.retrieve(name=name, folder_key=folder_key, folder_path=folder_path)
        bucket_name, bucket_folder_path = self._extract_bucket_info(index)
        if source_path:
            self._buckets_service.upload(
                name=bucket_name,
                blob_file_path=blob_file_path,
                source_path=source_path,
                folder_path=bucket_folder_path,
                content_type=content_type,
            )
        else:
            self._buckets_service.upload(
                name=bucket_name,
                content=content,
                blob_file_path=blob_file_path,
                folder_path=bucket_folder_path,
                content_type=content_type,
            )

        if ingest_data:
            self.ingest_data(index, folder_key=folder_key, folder_path=folder_path)

    @traced(name="add_to_index", run_type="uipath")
    @resource_override(resource_type="index")
    async def add_to_index_async(
        self,
        name: str,
        blob_file_path: str,
        content_type: Optional[str] = None,
        content: Optional[Union[str, bytes]] = None,
        source_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        ingest_data: bool = True,
    ) -> None:
        """Asynchronously add content to the index.

        Args:
            name (str): The name of the index to add content to.
            content_type (Optional[str]): The MIME type of the file. For file inputs this is computed dynamically. Default is "application/octet-stream".
            blob_file_path (str): The path where the blob will be stored in the storage bucket.
            content (Optional[Union[str, bytes]]): The content to be added, either as a string or bytes.
            source_path (Optional[str]): The source path of the content if it is being uploaded from a file.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.
            ingest_data (bool): Whether to ingest data in the index after content is uploaded. Defaults to True.

        Raises:
            ValueError: If neither content nor source_path is provided, or if both are provided.
        """
        if not (content or source_path):
            raise ValueError("Content or source_path is required")
        if content and source_path:
            raise ValueError("Content and source_path are mutually exclusive")

        index = await self.retrieve_async(
            name=name, folder_key=folder_key, folder_path=folder_path
        )
        bucket_name, bucket_folder_path = self._extract_bucket_info(index)
        if source_path:
            await self._buckets_service.upload_async(
                name=bucket_name,
                blob_file_path=blob_file_path,
                source_path=source_path,
                folder_path=bucket_folder_path,
                content_type=content_type,
            )
        else:
            await self._buckets_service.upload_async(
                name=bucket_name,
                content=content,
                blob_file_path=blob_file_path,
                folder_path=bucket_folder_path,
                content_type=content_type,
            )

        if ingest_data:
            await self.ingest_data_async(
                index, folder_key=folder_key, folder_path=folder_path
            )

    @traced(name="contextgrounding_retrieve", run_type="uipath")
    @resource_override(resource_type="index")
    def retrieve(
        self,
        name: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        """Retrieve context grounding index information by its name.

        Args:
            name (str): The name of the context index to retrieve.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.

        Returns:
            ContextGroundingIndex: The index information, including its configuration and metadata if found.

        Raises:
            Exception: If no index with the given name is found.
        """
        spec = self._retrieve_spec(
            name,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()
        try:
            return next(
                ContextGroundingIndex.model_validate(item)
                for item in response["value"]
                if item["name"] == name
            )
        except StopIteration as e:
            raise Exception("ContextGroundingIndex not found") from e

    @traced(name="contextgrounding_retrieve", run_type="uipath")
    @resource_override(resource_type="index")
    async def retrieve_async(
        self,
        name: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        """Asynchronously retrieve context grounding index information by its name.

        Args:
            name (str): The name of the context index to retrieve.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.

        Returns:
            ContextGroundingIndex: The index information, including its configuration and metadata if found.

        Raises:
            Exception: If no index with the given name is found.
        """
        spec = self._retrieve_spec(
            name,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = (
            await self.request_async(
                spec.method,
                spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()
        try:
            return next(
                ContextGroundingIndex.model_validate(item)
                for item in response["value"]
                if item["name"] == name
            )
        except StopIteration as e:
            raise Exception("ContextGroundingIndex not found") from e

    @traced(name="contextgrounding_retrieve_by_id", run_type="uipath")
    @deprecated("Use retrieve instead")
    def retrieve_by_id(
        self,
        id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Any:
        """Retrieve context grounding index information by its ID.

        This method provides direct access to a context index using its unique
        identifier, which can be more efficient than searching by name.

        Args:
            id (str): The unique identifier of the context index.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.

        Returns:
            Any: The index information, including its configuration and metadata.
        """
        spec = self._retrieve_by_id_spec(
            id,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        return self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
        ).json()

    @traced(name="contextgrounding_retrieve_by_id", run_type="uipath")
    @deprecated("Use retrieve_async instead")
    async def retrieve_by_id_async(
        self,
        id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Any:
        """Retrieve asynchronously context grounding index information by its ID.

        This method provides direct access to a context index using its unique
        identifier, which can be more efficient than searching by name.

        Args:
            id (str): The unique identifier of the context index.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.

        Returns:
            Any: The index information, including its configuration and metadata.
        """
        spec = self._retrieve_by_id_spec(
            id,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
        )

        return response.json()

    @traced(name="contextgrounding_create_index", run_type="uipath")
    @resource_override(resource_type="index")
    def create_index(
        self,
        name: str,
        source: Dict[str, Any],
        description: Optional[str] = None,
        cron_expression: Optional[str] = None,
        time_zone_id: Optional[str] = None,
        advanced_ingestion: Optional[bool] = True,
        preprocessing_request: Optional[str] = LLMV4,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        """Create a new context grounding index.

        Args:
            name (str): The name of the index to create.
            source (dict): Source configuration dictionary:
                - For buckets: type="bucket", bucket_name, folder_path, directory_path="/" (optional), file_type (optional)
                - For Google Drive: type="google", connection_name, connection_id, leaf_folder_id, directory_path, folder_path, file_type (optional)
                - For Dropbox: type="dropbox", connection_name, connection_id, directory_path, folder_path, file_type (optional)
                - For OneDrive: type="onedrive", connection_name, connection_id, leaf_folder_id, directory_path, folder_path, file_type (optional)
                - For Confluence: type="confluence", connection_name, connection_id, space_id, directory_path, folder_path, file_type (optional)
            description (Optional[str]): Description of the index.
            cron_expression (Optional[str]): Cron expression for scheduled indexing (e.g., "0 0 18 ? * 2" for Tuesdays at 6 PM).
            time_zone_id (Optional[str]): Valid Windows Timezone ID for the cron expression (e.g., "UTC", "Pacific Standard Time", "GTB Standard Time").
            advanced_ingestion (Optional[bool]): Enable advanced ingestion with preprocessing. Defaults to True.
            preprocessing_request (Optional[str]): The OData type for preprocessing request. Defaults to LLMV4.
            folder_key (Optional[str]): The key of the folder where the index will be created.
            folder_path (Optional[str]): The path of the folder where the index will be created.

        Returns:
            ContextGroundingIndex: The created index information.
        """
        spec = self._create_spec(
            name=name,
            description=description,
            source=source,
            cron_expression=cron_expression,
            time_zone_id=time_zone_id,
            advanced_ingestion=advanced_ingestion
            if advanced_ingestion is not None
            else True,
            preprocessing_request=preprocessing_request or LLMV4,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        return ContextGroundingIndex.model_validate(response.json())

    @traced(name="contextgrounding_create_index", run_type="uipath")
    @resource_override(resource_type="index")
    async def create_index_async(
        self,
        name: str,
        source: Dict[str, Any],
        description: Optional[str] = None,
        cron_expression: Optional[str] = None,
        time_zone_id: Optional[str] = None,
        advanced_ingestion: Optional[bool] = True,
        preprocessing_request: Optional[str] = LLMV4,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        """Create a new context grounding index.

        Args:
            name (str): The name of the index to create.
            source (dict): Source configuration dictionary:
                - For buckets: type="bucket", bucket_name, folder_path, directory_path="/" (optional), file_type (optional)
                - For Google Drive: type="google_drive", connection_name, connection_id, leaf_folder_id, directory_path, folder_path, file_type (optional)
                - For Dropbox: type="dropbox", connection_name, connection_id, directory_path, folder_path, file_type (optional)
                - For OneDrive: type="onedrive", connection_name, connection_id, leaf_folder_id, directory_path, folder_path, file_type (optional)
                - For Confluence: type="confluence", connection_name, connection_id, space_id, directory_path, folder_path, file_type (optional)
            description (Optional[str]): Description of the index.
            cron_expression (Optional[str]): Cron expression for scheduled indexing (e.g., "0 0 18 ? * 2" for Tuesdays at 6 PM).
            time_zone_id (Optional[str]): Valid Windows Timezone ID for the cron expression (e.g., "UTC", "Pacific Standard Time", "GTB Standard Time").
            advanced_ingestion (Optional[bool]): Enable advanced ingestion with preprocessing. Defaults to True.
            preprocessing_request (Optional[str]): The OData type for preprocessing request. Defaults to LLMV4.
            folder_key (Optional[str]): The key of the folder where the index will be created.
            folder_path (Optional[str]): The path of the folder where the index will be created.

        Returns:
            ContextGroundingIndex: The created index information.
        """
        spec = self._create_spec(
            name=name,
            description=description,
            source=source,
            cron_expression=cron_expression,
            time_zone_id=time_zone_id,
            advanced_ingestion=advanced_ingestion
            if advanced_ingestion is not None
            else True,
            preprocessing_request=preprocessing_request or LLMV4,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            content=spec.content,
            headers=spec.headers,
        )

        return ContextGroundingIndex.model_validate(response.json())

    @traced(name="contextgrounding_search", run_type="uipath")
    @resource_override(resource_type="index")
    def search(
        self,
        name: str,
        query: str,
        number_of_results: int = 10,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
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
        index = self.retrieve(name, folder_key=folder_key, folder_path=folder_path)
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=name)

        spec = self._search_spec(
            name,
            query,
            number_of_results,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return TypeAdapter(List[ContextGroundingQueryResponse]).validate_python(
            response.json()
        )

    @traced(name="contextgrounding_search", run_type="uipath")
    @resource_override(resource_type="index")
    async def search_async(
        self,
        name: str,
        query: str,
        number_of_results: int = 10,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
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
        index = self.retrieve(
            name,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=name)
        spec = self._search_spec(
            name,
            query,
            number_of_results,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return TypeAdapter(List[ContextGroundingQueryResponse]).validate_python(
            response.json()
        )

    @traced(name="contextgrounding_ingest_data", run_type="uipath")
    def ingest_data(
        self,
        index: ContextGroundingIndex,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Ingest data into the context grounding index.

        Args:
            index (ContextGroundingIndex): The context grounding index to perform data ingestion.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.
        """
        if not index.id:
            return
        spec = self._ingest_spec(
            index.id,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        try:
            self.request(
                spec.method,
                spec.endpoint,
                headers=spec.headers,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                raise e
            raise IngestionInProgressException(
                index_name=index.name, search_operation=False
            ) from e

    @traced(name="contextgrounding_ingest_data", run_type="uipath")
    async def ingest_data_async(
        self,
        index: ContextGroundingIndex,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Asynchronously ingest data into the context grounding index.

        Args:
            index (ContextGroundingIndex): The context grounding index to perform data ingestion.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.
        """
        if not index.id:
            return
        spec = self._ingest_spec(
            index.id,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        try:
            await self.request_async(
                spec.method,
                spec.endpoint,
                headers=spec.headers,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                raise e
            raise IngestionInProgressException(
                index_name=index.name, search_operation=False
            ) from e

    @traced(name="contextgrounding_delete_index", run_type="uipath")
    def delete_index(
        self,
        index: ContextGroundingIndex,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Delete a context grounding index.

        This method removes the specified context grounding index from Orchestrator.

        Args:
            index (ContextGroundingIndex): The context grounding index to delete.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.
        """
        if not index.id:
            return
        spec = self._delete_by_id_spec(
            index.id,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    @traced(name="contextgrounding_delete_index", run_type="uipath")
    async def delete_index_async(
        self,
        index: ContextGroundingIndex,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> None:
        """Asynchronously delete a context grounding index.

        This method removes the specified context grounding index from Orchestrator.

        Args:
            index (ContextGroundingIndex): The context grounding index to delete.
            folder_key (Optional[str]): The key of the folder where the index resides.
            folder_path (Optional[str]): The path of the folder where the index resides.
        """
        if not index.id:
            return
        spec = self._delete_by_id_spec(
            index.id,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )

    def _ingest_spec(
        self,
        key: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{key}/ingest"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _retrieve_spec(
        self,
        name: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/ecs_/v2/indexes"),
            params={
                "$filter": f"Name eq '{name}'",
                "$expand": "dataSource",
            },
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _create_spec(
        self,
        name: str,
        description: Optional[str],
        source: Dict[str, Any],
        advanced_ingestion: bool,
        preprocessing_request: str,
        cron_expression: Optional[str] = None,
        time_zone_id: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        """Create request spec for index creation.

        Args:
            name: Index name
            description: Index description
            source: Source configuration dictionary
            cron_expression: Optional cron expression for scheduled indexing
            time_zone_id: Optional timezone for cron expression
            advanced_ingestion: Whether to enable advanced ingestion with preprocessing
            preprocessing_request: OData type for preprocessing request
            folder_key: Optional folder key
            folder_path: Optional folder path

        Returns:
            RequestSpec for the create index request
        """
        source_type = source.get("type", "").lower()

        folder_key = self._resolve_folder_key(folder_key, folder_path)
        file_type = source.get("file_type")
        file_name_glob = f"**/*.{file_type}" if file_type else "**/*"

        data_source = self._build_data_source(source_type, source, file_name_glob)

        if cron_expression:
            data_source["indexer"] = {
                "cronExpression": cron_expression,
                "timeZoneId": time_zone_id or "UTC",
            }

        payload = {
            "name": name,
            "description": description or "",
            "dataSource": data_source,
        }

        if advanced_ingestion and preprocessing_request:
            payload["preProcessing"] = {
                "@odata.type": preprocessing_request,
            }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/v2/indexes/create"),
            content=json.dumps(payload),
            headers={
                **header_folder(folder_key, None),
                "Content-Type": "application/json",
            },
        )

    def _build_data_source(
        self, source_type: str, source: Dict[str, Any], file_name_glob: str
    ) -> Dict[str, Any]:
        """Build data source configuration based on type."""
        if source_type == "bucket":
            return self._build_bucket_data_source(source, file_name_glob)
        elif source_type in ["google_drive"]:
            return self._build_google_drive_data_source(source, file_name_glob)
        elif source_type == "dropbox":
            return self._build_dropbox_data_source(source, file_name_glob)
        elif source_type == "onedrive":
            return self._build_onedrive_data_source(source, file_name_glob)
        elif source_type == "confluence":
            return self._build_confluence_data_source(source, file_name_glob)
        else:
            raise ValueError(
                f"Unsupported data source type: {source_type}. "
                f"Supported types: bucket, google_drive, dropbox, onedrive, confluence"
            )

    def _build_bucket_data_source(
        self, source: Dict[str, Any], file_name_glob: str
    ) -> Dict[str, Any]:
        """Build data source configuration for storage bucket."""
        required_fields = ["bucket_name", "folder_path"]
        for field in required_fields:
            if not source.get(field):
                raise ValueError(f"{field} is required for bucket data source")

        return {
            "@odata.type": ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE,
            "folder": source["folder_path"],
            "bucketName": source["bucket_name"],
            "fileNameGlob": file_name_glob,
            "directoryPath": source.get("directory_path", "/"),
        }

    def _build_google_drive_data_source(
        self, source: Dict[str, Any], file_name_glob: str
    ) -> Dict[str, Any]:
        """Build data source configuration for Google Drive."""
        required_fields = [
            "connection_id",
            "connection_name",
            "leaf_folder_id",
            "directory_path",
            "folder_path",
        ]
        for field in required_fields:
            if not source.get(field):
                raise ValueError(f"{field} is required for Google Drive data source")

        return {
            "@odata.type": GOOGLE_DRIVE_DATA_SOURCE,
            "folder": source["folder_path"],
            "connectionId": source["connection_id"],
            "connectionName": source["connection_name"],
            "leafFolderId": source["leaf_folder_id"],
            "directoryPath": source["directory_path"],
            "fileNameGlob": file_name_glob,
        }

    def _build_dropbox_data_source(
        self, source: Dict[str, Any], file_name_glob: str
    ) -> Dict[str, Any]:
        """Build data source configuration for Dropbox."""
        required_fields = [
            "connection_id",
            "connection_name",
            "directory_path",
            "folder_path",
        ]
        for field in required_fields:
            if not source.get(field):
                raise ValueError(f"{field} is required for Dropbox data source")

        return {
            "@odata.type": DROPBOX_DATA_SOURCE,
            "folder": source["folder_path"],
            "connectionId": source["connection_id"],
            "connectionName": source["connection_name"],
            "directoryPath": source["directory_path"],
            "fileNameGlob": file_name_glob,
        }

    def _build_onedrive_data_source(
        self, source: Dict[str, Any], file_name_glob: str
    ) -> Dict[str, Any]:
        """Build data source configuration for OneDrive."""
        required_fields = [
            "connection_id",
            "connection_name",
            "leaf_folder_id",
            "directory_path",
            "folder_path",
        ]
        for field in required_fields:
            if not source.get(field):
                raise ValueError(f"{field} is required for OneDrive data source")

        return {
            "@odata.type": ONEDRIVE_DATA_SOURCE,
            "folder": source["folder_path"],
            "connectionId": source["connection_id"],
            "connectionName": source["connection_name"],
            "leafFolderId": source["leaf_folder_id"],
            "directoryPath": source["directory_path"],
            "fileNameGlob": file_name_glob,
        }

    def _build_confluence_data_source(
        self, source: Dict[str, Any], file_name_glob: str
    ) -> Dict[str, Any]:
        """Build data source configuration for Confluence."""
        required_fields = [
            "connection_id",
            "connection_name",
            "directory_path",
            "folder_path",
            "space_id",
        ]
        for field in required_fields:
            if not source.get(field):
                raise ValueError(f"{field} is required for Confluence data source")

        return {
            "@odata.type": CONFLUENCE_DATA_SOURCE,
            "folder": source["folder_path"],
            "connectionId": source["connection_id"],
            "connectionName": source["connection_name"],
            "directoryPath": source["directory_path"],
            "fileNameGlob": file_name_glob,
            "spaceId": source["space_id"],
        }

    def _retrieve_by_id_spec(
        self,
        id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{id}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _delete_by_id_spec(
        self,
        id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{id}"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _search_spec(
        self,
        name: str,
        query: str,
        number_of_results: int = 10,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/v1/search"),
            json={
                "query": {"query": query, "numberOfResults": number_of_results},
                "schema": {"name": name},
            },
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _resolve_folder_key(self, folder_key, folder_path):
        if folder_key is None and folder_path is not None:
            folder_key = self._folders_service.retrieve_key(folder_path=folder_path)

        if folder_key is None and folder_path is None:
            folder_key = self._folder_key or (
                self._folders_service.retrieve_key(folder_path=self._folder_path)
                if self._folder_path
                else None
            )

        if folder_key is None:
            raise ValueError("ContextGrounding: Failed to resolve folder key")

        return folder_key

    def _extract_bucket_info(self, index: ContextGroundingIndex) -> Tuple[str, str]:
        try:
            return index.data_source.bucketName, index.data_source.folder  # type: ignore
        except AttributeError as e:
            raise Exception(
                "ContextGrounding: Cannot extract bucket data from index"
            ) from e
