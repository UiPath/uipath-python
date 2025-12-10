from typing import Annotated, Any, Dict, List, Optional, Tuple, Union

import httpx
from pydantic import Field, TypeAdapter
from typing_extensions import deprecated

from ..._utils import Endpoint, RequestSpec, header_folder, resource_override
from ..._utils._ssl_context import get_httpx_client_kwargs
from ..._utils.constants import (
    LLMV4_REQUEST,
    ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE,
)
from ...tracing import traced
from ..common import BaseService, FolderContext, UiPathApiConfig, UiPathExecutionContext
from ..errors import (
    BatchTransformNotCompleteException,
    IngestionInProgressException,
    UnsupportedDataSourceException,
)
from ..orchestrator._buckets_service import BucketsService
from ..orchestrator._folder_service import FolderService
from .context_grounding import (
    BatchTransformCreationResponse,
    BatchTransformOutputColumn,
    BatchTransformReadUriResponse,
    BatchTransformResponse,
    BatchTransformStatus,
    CitationMode,
    ContextGroundingQueryResponse,
    DeepRagCreationResponse,
    DeepRagResponse,
)
from .context_grounding_index import ContextGroundingIndex
from .context_grounding_payloads import (
    BucketDataSource,
    BucketSourceConfig,
    ConfluenceDataSource,
    ConfluenceSourceConfig,
    CreateIndexPayload,
    DropboxDataSource,
    DropboxSourceConfig,
    GoogleDriveDataSource,
    GoogleDriveSourceConfig,
    OneDriveDataSource,
    OneDriveSourceConfig,
    PreProcessing,
    SourceConfig,
)


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
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
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
        source: SourceConfig,
        description: Optional[str] = None,
        advanced_ingestion: Optional[bool] = True,
        preprocessing_request: Optional[str] = LLMV4_REQUEST,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        """Create a new context grounding index.

        Args:
            name (str): The name of the index to create.
            source (SourceConfig): Source configuration using one of:
                - BucketSourceConfig: For storage buckets
                - GoogleDriveSourceConfig: For Google Drive
                - DropboxSourceConfig: For Dropbox
                - OneDriveSourceConfig: For OneDrive
                - ConfluenceSourceConfig: For Confluence

                The source can include an optional indexer field for scheduled indexing:
                    source.indexer = Indexer(cron_expression="0 0 18 ? * 2", time_zone_id="UTC")
            description (Optional[str]): Description of the index.
            advanced_ingestion (Optional[bool]): Enable advanced ingestion with preprocessing. Defaults to True.
            preprocessing_request (Optional[str]): The OData type for preprocessing request. Defaults to LLMV4_REQUEST.
            folder_key (Optional[str]): The key of the folder where the index will be created.
            folder_path (Optional[str]): The path of the folder where the index will be created.

        Returns:
            ContextGroundingIndex: The created index information.
        """
        spec = self._create_spec(
            name=name,
            description=description,
            source=source,
            advanced_ingestion=advanced_ingestion
            if advanced_ingestion is not None
            else True,
            preprocessing_request=preprocessing_request or LLMV4_REQUEST,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return ContextGroundingIndex.model_validate(response.json())

    @traced(name="contextgrounding_create_index", run_type="uipath")
    @resource_override(resource_type="index")
    async def create_index_async(
        self,
        name: str,
        source: SourceConfig,
        description: Optional[str] = None,
        advanced_ingestion: Optional[bool] = True,
        preprocessing_request: Optional[str] = LLMV4_REQUEST,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ContextGroundingIndex:
        """Create a new context grounding index.

        Args:
            name (str): The name of the index to create.
            source (SourceConfig): Source configuration using one of:
                - BucketSourceConfig: For storage buckets
                - GoogleDriveSourceConfig: For Google Drive
                - DropboxSourceConfig: For Dropbox
                - OneDriveSourceConfig: For OneDrive
                - ConfluenceSourceConfig: For Confluence

                The source can include an optional indexer field for scheduled indexing:
                    source.indexer = Indexer(cron_expression="0 0 18 ? * 2", time_zone_id="UTC")
            description (Optional[str]): Description of the index.
            advanced_ingestion (Optional[bool]): Enable advanced ingestion with preprocessing. Defaults to True.
            preprocessing_request (Optional[str]): The OData type for preprocessing request. Defaults to LLMV4_REQUEST.
            folder_key (Optional[str]): The key of the folder where the index will be created.
            folder_path (Optional[str]): The path of the folder where the index will be created.

        Returns:
            ContextGroundingIndex: The created index information.
        """
        spec = self._create_spec(
            name=name,
            description=description,
            source=source,
            advanced_ingestion=advanced_ingestion
            if advanced_ingestion is not None
            else True,
            preprocessing_request=preprocessing_request or LLMV4_REQUEST,
            folder_path=folder_path,
            folder_key=folder_key,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return ContextGroundingIndex.model_validate(response.json())

    @traced(name="contextgrounding_retrieve_deep_rag", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    def retrieve_deep_rag(
        self,
        id: str,
        *,
        index_name: str | None = None,
    ) -> DeepRagResponse:
        """Retrieves a Deep RAG task.

        Args:
            id (str): The id of the Deep RAG task.
            index_name (Optional[str]): Index name hint for resource override.

        Returns:
            DeepRagResponse: The Deep RAG task response.
        """
        spec = self._deep_rag_retrieve_spec(
            id=id,
        )
        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )
        return DeepRagResponse.model_validate(response.json())

    @traced(name="contextgrounding_retrieve_deep_rag_async", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    async def retrieve_deep_rag_async(
        self,
        id: str,
        *,
        index_name: str | None = None,
    ) -> DeepRagResponse:
        """Asynchronously retrieves a Deep RAG task.

        Args:
            id (str): The id of the Deep RAG task.
            index_name (Optional[str]): Index name hint for resource override.

        Returns:
            DeepRagResponse: The Deep RAG task response.
        """
        spec = self._deep_rag_retrieve_spec(
            id=id,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )

        return DeepRagResponse.model_validate(response.json())

    @traced(name="contextgrounding_start_batch_transform", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    def start_batch_transform(
        self,
        name: str,
        index_name: str,
        prompt: Annotated[str, Field(max_length=250000)],
        output_columns: list[BatchTransformOutputColumn],
        storage_bucket_folder_path_prefix: Annotated[
            str | None, Field(max_length=512)
        ] = None,
        enable_web_search_grounding: bool = False,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> BatchTransformCreationResponse:
        """Starts a Batch Transform, task on the targeted index.

        Batch Transform tasks are processing and transforming csv files from the index.

        Args:
            name (str): The name of the Deep RAG task.
            index_name (str): The name of the context index to search in.
            prompt (str): Describe the task: what to research, what to synthesize.
            output_columns (list[BatchTransformOutputColumn]):  The output columns to add into the csv.
            storage_bucket_folder_path_prefix (str): The prefix pattern for filtering files in the storage bucket. Use "*" to include all files. Defaults to "*".
            enable_web_search_grounding (Optional[bool]): Whether to enable web search. Defaults to False.
            folder_key (str, optional): The folder key where the index resides. Defaults to None.
            folder_path (str, optional): The folder path where the index resides. Defaults to None.

        Returns:
            BatchTransformCreationResponse: The batch transform task creation response.
        """
        index = self.retrieve(
            index_name, folder_key=folder_key, folder_path=folder_path
        )
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=index_name)

        spec = self._batch_transform_creation_spec(
            index_id=index.id,
            name=name,
            storage_bucket_folder_path_prefix=storage_bucket_folder_path_prefix,
            prompt=prompt,
            output_columns=output_columns,
            enable_web_search_grounding=enable_web_search_grounding,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            params=spec.params,
            headers=spec.headers,
        )
        return BatchTransformCreationResponse.model_validate(response.json())

    @traced(name="contextgrounding_start_batch_transform_async", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    async def start_batch_transform_async(
        self,
        name: str,
        index_name: str,
        prompt: Annotated[str, Field(max_length=250000)],
        output_columns: list[BatchTransformOutputColumn],
        storage_bucket_folder_path_prefix: Annotated[
            str | None, Field(max_length=512)
        ] = None,
        enable_web_search_grounding: bool = False,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> BatchTransformCreationResponse:
        """Asynchronously starts a Batch Transform, task on the targeted index.

        Batch Transform tasks are processing and transforming csv files from the index.

        Args:
            name (str): The name of the Deep RAG task.
            index_name (str): The name of the context index to search in.
            prompt (str): Describe the task: what to research, what to synthesize.
            output_columns (list[BatchTransformOutputColumn]):  The output columns to add into the csv.
            storage_bucket_folder_path_prefix (str): The prefix pattern for filtering files in the storage bucket. Use "*" to include all files. Defaults to "*".
            enable_web_search_grounding (Optional[bool]): Whether to enable web search. Defaults to False.
            folder_key (str, optional): The folder key where the index resides. Defaults to None.
            folder_path (str, optional): The folder path where the index resides. Defaults to None.

        Returns:
            BatchTransformCreationResponse: The batch transform task creation response.
        """
        index = await self.retrieve_async(
            index_name, folder_key=folder_key, folder_path=folder_path
        )
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=index_name)

        spec = self._batch_transform_creation_spec(
            index_id=index.id,
            name=name,
            storage_bucket_folder_path_prefix=storage_bucket_folder_path_prefix,
            prompt=prompt,
            output_columns=output_columns,
            enable_web_search_grounding=enable_web_search_grounding,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            json=spec.json,
            params=spec.params,
            headers=spec.headers,
        )
        return BatchTransformCreationResponse.model_validate(response.json())

    @traced(name="contextgrounding_retrieve_batch_transform", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    def retrieve_batch_transform(
        self,
        id: str,
        *,
        index_name: str | None = None,
    ) -> BatchTransformResponse:
        """Retrieves a Batch Transform task status.

        Args:
            id (str): The id of the Batch Transform task.
            index_name (Optional[str]): Index name hint for resource override.

        Returns:
            BatchTransformResponse: The Batch Transform task response.
        """
        spec = self._batch_transform_retrieve_spec(id=id)
        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        return BatchTransformResponse.model_validate(response.json())

    @traced(name="contextgrounding_retrieve_batch_transform_async", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    async def retrieve_batch_transform_async(
        self,
        id: str,
        *,
        index_name: str | None = None,
    ) -> BatchTransformResponse:
        """Asynchronously retrieves a Batch Transform task status.

        Args:
            id (str): The id of the Batch Transform task.
            index_name (Optional[str]): Index name hint for resource override.

        Returns:
            BatchTransformResponse: The Batch Transform task response.
        """
        spec = self._batch_transform_retrieve_spec(id=id)
        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        return BatchTransformResponse.model_validate(response.json())

    @traced(name="contextgrounding_download_batch_transform_result", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    def download_batch_transform_result(
        self,
        id: str,
        destination_path: str,
        *,
        validate_status: bool = True,
        index_name: str | None = None,
    ) -> None:
        """Downloads the Batch Transform result file to the specified path.

        Args:
            id (str): The id of the Batch Transform task.
            destination_path (str): The local file path where the result file will be saved.
            validate_status (bool): Whether to validate the batch transform status before downloading. Defaults to True.
            index_name (Optional[str]): Index name hint for resource override.

        Raises:
            BatchTransformNotCompleteException: If validate_status is True and the batch transform is not complete.
        """
        if validate_status:
            batch_transform = self.retrieve_batch_transform(
                id=id, index_name=index_name
            )
            if batch_transform.last_batch_rag_status != BatchTransformStatus.SUCCESSFUL:
                raise BatchTransformNotCompleteException(
                    batch_transform_id=id,
                    status=batch_transform.last_batch_rag_status,
                )

        spec = self._batch_transform_get_read_uri_spec(id=id)
        response = self.request(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )
        uri_response = BatchTransformReadUriResponse.model_validate(response.json())

        with open(destination_path, "wb") as file:
            with httpx.Client(**get_httpx_client_kwargs()) as client:
                file_content = client.get(uri_response.uri).content
            file.write(file_content)

    @traced(
        name="contextgrounding_download_batch_transform_result_async", run_type="uipath"
    )
    @resource_override(resource_type="index", resource_identifier="index_name")
    async def download_batch_transform_result_async(
        self,
        id: str,
        destination_path: str,
        *,
        validate_status: bool = True,
        index_name: str | None = None,
    ) -> None:
        """Asynchronously downloads the Batch Transform result file to the specified path.

        Args:
            id (str): The id of the Batch Transform task.
            destination_path (str): The local file path where the result file will be saved.
            validate_status (bool): Whether to validate the batch transform status before downloading. Defaults to True.
            index_name (Optional[str]): Index name hint for resource override.

        Raises:
            BatchTransformNotCompleteException: If validate_status is True and the batch transform is not complete.
        """
        if validate_status:
            batch_transform = await self.retrieve_batch_transform_async(
                id=id, index_name=index_name
            )
            if batch_transform.last_batch_rag_status != BatchTransformStatus.SUCCESSFUL:
                raise BatchTransformNotCompleteException(
                    batch_transform_id=id,
                    status=batch_transform.last_batch_rag_status,
                )

        spec = self._batch_transform_get_read_uri_spec(id=id)
        response = await self.request_async(
            spec.method,
            spec.endpoint,
            headers=spec.headers,
        )
        uri_response = BatchTransformReadUriResponse.model_validate(response.json())

        async with httpx.AsyncClient(**get_httpx_client_kwargs()) as client:
            download_response = await client.get(uri_response.uri)
            file_content = download_response.content

        with open(destination_path, "wb") as file:
            file.write(file_content)

    @traced(name="contextgrounding_start_deep_rag", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    def start_deep_rag(
        self,
        name: str,
        index_name: Annotated[str, Field(max_length=512)],
        prompt: Annotated[str, Field(max_length=250000)],
        glob_pattern: Annotated[str, Field(max_length=512, default="*")] = "**",
        citation_mode: CitationMode = CitationMode.SKIP,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> DeepRagCreationResponse:
        """Starts a Deep RAG task on the targeted index.

        Args:
            name (str): The name of the Deep RAG task.
            index_name (str): The name of the context index to search in.
            prompt (str): Describe the task: what to research across documents, what to synthesize and how to cite sources.
            glob_pattern (str): The glob pattern to search in the index. Defaults to "**".
            citation_mode (CitationMode): The citation mode to use. Defaults to SKIP.
            folder_key (str, optional): The folder key where the index resides. Defaults to None.
            folder_path (str, optional): The folder path where the index resides. Defaults to None.

        Returns:
            DeepRagCreationResponse: The Deep RAG task creation response.
        """
        index = self.retrieve(
            index_name, folder_key=folder_key, folder_path=folder_path
        )
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=index_name)

        spec = self._deep_rag_creation_spec(
            index_id=index.id,
            name=name,
            glob_pattern=glob_pattern,
            prompt=prompt,
            citation_mode=citation_mode,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            spec.endpoint,
            json=spec.json,
            params=spec.params,
            headers=spec.headers,
        )

        return DeepRagCreationResponse.model_validate(response.json())

    @traced(name="contextgrounding_start_deep_rag_async", run_type="uipath")
    @resource_override(resource_type="index", resource_identifier="index_name")
    async def start_deep_rag_async(
        self,
        name: str,
        index_name: Annotated[str, Field(max_length=512)],
        prompt: Annotated[str, Field(max_length=250000)],
        glob_pattern: Annotated[str, Field(max_length=512, default="*")] = "**",
        citation_mode: CitationMode = CitationMode.SKIP,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> DeepRagCreationResponse:
        """Asynchronously starts a Deep RAG task on the targeted index.

        Args:
            name (str): The name of the Deep RAG task.
            index_name (str): The name of the context index to search in.
            name (str): The name of the Deep RAG task.
            prompt (str): Describe the task: what to research across documents, what to synthesize and how to cite sources.
            glob_pattern (str): The glob pattern to search in the index. Defaults to "**".
            citation_mode (CitationMode): The citation mode to use. Defaults to SKIP.
            folder_key (str, optional): The folder key where the index resides. Defaults to None.
            folder_path (str, optional): The folder path where the index resides. Defaults to None.

        Returns:
            DeepRagCreationResponse: The Deep RAG task creation response.
        """
        index = await self.retrieve_async(
            index_name, folder_key=folder_key, folder_path=folder_path
        )
        if index and index.in_progress_ingestion():
            raise IngestionInProgressException(index_name=index_name)

        spec = self._deep_rag_creation_spec(
            index_id=index.id,
            name=name,
            glob_pattern=glob_pattern,
            prompt=prompt,
            citation_mode=citation_mode,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )

        return DeepRagCreationResponse.model_validate(response.json())

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
        source: SourceConfig,
        advanced_ingestion: bool,
        preprocessing_request: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        """Create request spec for index creation.

        Args:
            name: Index name
            description: Index description
            source: Source configuration (typed model) with optional indexer
            advanced_ingestion: Whether to enable advanced ingestion with preprocessing
            preprocessing_request: OData type for preprocessing request
            folder_key: Optional folder key
            folder_path: Optional folder path

        Returns:
            RequestSpec for the create index request
        """
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        data_source_dict = self._build_data_source(source)

        # Add indexer from source config if present
        if source.indexer:
            data_source_dict["indexer"] = source.indexer.model_dump(by_alias=True)

        payload = CreateIndexPayload(
            name=name,
            description=description or "",
            data_source=data_source_dict,
            pre_processing=(
                PreProcessing(**{"@odata.type": preprocessing_request})
                if advanced_ingestion and preprocessing_request
                else None
            ),
        )

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/v2/indexes/create"),
            json=payload.model_dump(by_alias=True, exclude_none=True),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _build_data_source(self, source: SourceConfig) -> Dict[str, Any]:
        """Build data source configuration from typed source config.

        Args:
            source: Typed source configuration model

        Returns:
            Dictionary with data source configuration for API
        """
        file_name_glob = f"**/*.{source.file_type}" if source.file_type else "**/*"

        data_source: Union[
            BucketDataSource,
            GoogleDriveDataSource,
            DropboxDataSource,
            OneDriveDataSource,
            ConfluenceDataSource,
        ]

        if isinstance(source, BucketSourceConfig):
            data_source = BucketDataSource(
                folder=source.folder_path,
                bucketName=source.bucket_name,
                fileNameGlob=file_name_glob,
                directoryPath=source.directory_path,
            )
        elif isinstance(source, GoogleDriveSourceConfig):
            data_source = GoogleDriveDataSource(
                folder=source.folder_path,
                connectionId=source.connection_id,
                connectionName=source.connection_name,
                leafFolderId=source.leaf_folder_id,
                directoryPath=source.directory_path,
                fileNameGlob=file_name_glob,
            )
        elif isinstance(source, DropboxSourceConfig):
            data_source = DropboxDataSource(
                folder=source.folder_path,
                connectionId=source.connection_id,
                connectionName=source.connection_name,
                directoryPath=source.directory_path,
                fileNameGlob=file_name_glob,
            )
        elif isinstance(source, OneDriveSourceConfig):
            data_source = OneDriveDataSource(
                folder=source.folder_path,
                connectionId=source.connection_id,
                connectionName=source.connection_name,
                leafFolderId=source.leaf_folder_id,
                directoryPath=source.directory_path,
                fileNameGlob=file_name_glob,
            )
        elif isinstance(source, ConfluenceSourceConfig):
            data_source = ConfluenceDataSource(
                folder=source.folder_path,
                connectionId=source.connection_id,
                connectionName=source.connection_name,
                directoryPath=source.directory_path,
                fileNameGlob=file_name_glob,
                spaceId=source.space_id,
            )
        else:
            raise ValueError(
                f"Unsupported source configuration type: {type(source).__name__}"
            )

        return data_source.model_dump(by_alias=True, exclude_none=True)

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

    def _deep_rag_creation_spec(
        self,
        index_id: str,
        name: str,
        glob_pattern: str,
        prompt: str,
        citation_mode: CitationMode,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{index_id}/createDeepRag"),
            json={
                "name": name,
                "prompt": prompt,
                "globPattern": glob_pattern,
                "citationMode": citation_mode.value,
            },
            params={
                "$select": "id,lastDeepRagStatus,createdDate",
            },
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _batch_transform_creation_spec(
        self,
        index_id: str,
        name: str,
        enable_web_search_grounding: bool,
        output_columns: list[BatchTransformOutputColumn],
        storage_bucket_folder_path_prefix: str | None,
        prompt: str,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/v2/indexes/{index_id}/createBatchRag"),
            json={
                "name": name,
                "prompt": prompt,
                "targetFileGlobPattern": f"{storage_bucket_folder_path_prefix}/*"
                if storage_bucket_folder_path_prefix
                else "**",
                "useWebSearchGrounding": enable_web_search_grounding,
                "outputColumns": [
                    column.model_dump(by_alias=True) for column in output_columns
                ],
            },
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _deep_rag_retrieve_spec(
        self,
        id: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/deeprag/{id}"),
            params={
                "$expand": "content",
                "$select": "content,name,createdDate,lastDeepRagStatus",
            },
        )

    def _batch_transform_retrieve_spec(
        self,
        id: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/batchRag/{id}"),
        )

    def _batch_transform_get_read_uri_spec(
        self,
        id: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/batchRag/{id}/GetReadUri"),
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
        """Extract bucket information from the index, validating it's a storage bucket data source.

        Args:
            index: The context grounding index

        Returns:
            Tuple of (bucket_name, folder_path)

        Raises:
            UnsupportedDataSourceException: If the data source is not an Orchestrator Storage Bucket
        """
        if not index.data_source:
            raise UnsupportedDataSourceException("add_to_index")

        # Check if the data source has the @odata.type field indicating it's a storage bucket
        data_source_dict = (
            index.data_source.model_dump(by_alias=True)
            if hasattr(index.data_source, "model_dump")
            else index.data_source.__dict__
        )
        odata_type = data_source_dict.get("@odata.type") or data_source_dict.get(
            "odata.type"
        )

        if odata_type and odata_type != ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE:
            raise UnsupportedDataSourceException("add_to_index", odata_type)

        # Try to extract bucket information
        bucket_name = getattr(index.data_source, "bucketName", None)
        folder = getattr(index.data_source, "folder", None)

        if not bucket_name or not folder:
            raise UnsupportedDataSourceException("add_to_index")

        return bucket_name, folder
