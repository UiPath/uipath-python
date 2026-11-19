import asyncio
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from uipath.core.tracing import traced

from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import header_folder
from ..common._models import Endpoint
from ..errors import OperationNotCompleteException
from ..orchestrator._folder_service import FolderService
from ._documents_service import (  # type: ignore[attr-defined]
    POLLING_INTERVAL,
    POLLING_TIMEOUT,
    _DocumentsServiceBase,
    _exactly_one_must_be_provided,
    _operation_result,
    _url_path,
)
from .documents import (
    FileContent,
    ModelExtractionResponse,
    StartModelExtractionResponse,
)


def _models_url(*segments: Any) -> Endpoint:
    return Endpoint(f"/du_/api/framework/models/{_url_path(segments)}")


def _parse_folder_key(folder_key: Optional[str]) -> str:
    if not folder_key:
        raise ValueError(
            "A folder is required for a model deployed to a folder: pass `folder_key` "
            "or `folder_path`, or run in a job folder (`UIPATH_FOLDER_KEY` or "
            "`UIPATH_FOLDER_PATH`)."
        )
    try:
        # The folder routes accept only a GUID folder key.
        return str(UUID(folder_key))
    except ValueError:
        raise ValueError(f"`folder_key` must be a GUID: {folder_key!r}") from None


class DocumentsServiceV2(_DocumentsServiceBase):
    """Service for managing UiPath DocumentUnderstanding Document Operations on DU Framework API v2.

    It has the same methods as `DocumentsService`, which calls API v1.1. API v2 results differ:

    - field IDs are prefixed with their document type and field group, e.g. `Default.Invoice.Total`
    - IXP results group fields in `FieldGroup` fields instead of `Table` fields, and their fields are typed, e.g. `MonetaryQuantity`
    - validation tasks open in the Compact view

    It can also extract with IXP models deployed to an Orchestrator folder, which API v1.1 can't reach:
    `extract_with_model`, or `start_model_extraction` and `retrieve_model_extraction_result`.

    !!! warning "Preview Feature"
        This function is currently experimental.
        Behavior and parameters are subject to change in future versions.
    """

    _api_version = "2.0"

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        polling_interval: float = POLLING_INTERVAL,
        polling_timeout: float = POLLING_TIMEOUT,
        folders_service: Optional[FolderService] = None,
    ) -> None:
        super().__init__(
            config=config,
            execution_context=execution_context,
            polling_interval=polling_interval,
            polling_timeout=polling_timeout,
        )
        self._folders_service = folders_service

    def _tag_route(self, tag: str) -> Tuple[str, ...]:
        # v2 moved tag-scoped routes under a literal `tags` segment.
        return ("tags", tag)

    def _allow_document_type_change(self) -> Dict[str, Any]:
        # v2 moved this setting into the validation configuration.
        return {"configuration": {"allowChangeOfDocumentType": True}}

    def _folders(self) -> FolderService:
        if self._folders_service is None:
            raise ValueError(
                "Looking up a folder path's key needs a `FolderService`: use "
                "`UiPath().documents_v2`, or pass `folders_service` or `folder_key`."
            )
        return self._folders_service

    def _folder_to_resolve(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Returns the folder key, or else the folder path to look its key up by.

        Explicit arguments come first, then the job folder from the environment.
        """
        if folder_key is not None and folder_path is not None:
            raise ValueError(
                "Only one of `folder_key` or `folder_path` can be provided"
            )
        if folder_key is not None or folder_path is not None:
            return folder_key, folder_path
        if self._folder_key:
            return self._folder_key, None
        return None, self._folder_path or None

    def _model_folder_key(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> str:
        folder_key, folder_path = self._folder_to_resolve(folder_key, folder_path)
        if folder_path:
            folder_key = self._folders().retrieve_folder_key(folder_path)
        return _parse_folder_key(folder_key)

    async def _model_folder_key_async(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> str:
        folder_key, folder_path = self._folder_to_resolve(folder_key, folder_path)
        if folder_path:
            folder_key = await self._folders().retrieve_folder_key_async(folder_path)
        return _parse_folder_key(folder_key)

    def _model_headers(self, folder_key: str) -> Dict[str, str]:
        return {
            **self._get_common_headers(),
            **header_folder(_parse_folder_key(folder_key), None),
        }

    def _wait_for_model_digitization(
        self, model_name: str, folder_key: str, document_id: str
    ) -> None:
        def result_getter() -> Tuple[str, Optional[str], Optional[str]]:
            result = self._request_json(
                "GET",
                url=_models_url(model_name, "digitization", "result", document_id),
                params={"api-version": self._api_version},
                headers=self._model_headers(folder_key),
            )
            return result["status"], result.get("error"), None

        self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

    async def _wait_for_model_digitization_async(
        self, model_name: str, folder_key: str, document_id: str
    ) -> None:
        async def result_getter() -> Tuple[str, Optional[str], Optional[str]]:
            result = await self._request_json_async(
                "GET",
                url=_models_url(model_name, "digitization", "result", document_id),
                params={"api-version": self._api_version},
                headers=self._model_headers(folder_key),
            )
            return result["status"], result.get("error"), None

        await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

    @traced(name="documents_start_model_extraction", run_type="uipath")
    def start_model_extraction(
        self,
        model_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> StartModelExtractionResponse:
        """Start an extraction with an IXP model deployed to a folder, without waiting for the result (non-blocking).

        It digitizes the document, waiting for the digitization to finish, then starts the extraction.

        Args:
            model_name (str): Name of the model deployed to the folder, e.g. `invoices-ixp`. This is the model's URL name, not its display name.
            file (FileContent, optional): The document file to be processed.
            file_path (str, optional): Path to the document file to be processed.
            folder_key (str, optional): Key of the folder the model is deployed to.
            folder_path (str, optional): Path of the folder the model is deployed to. Its key is looked up.

        Note:
            Either `file` or `file_path` must be provided, but not both.
            Pass at most one of `folder_key` and `folder_path`. Without either, the current job's folder is used.

        Returns:
            StartModelExtractionResponse: Contains the operation_id, document_id, model_name, and folder_key.

        Examples:
            ```python
            start_response = uipath.documents_v2.start_model_extraction(
                model_name="invoices-ixp",
                file_path="path/to/document.pdf",
                folder_path="Shared/Invoices",
            )
            # Later, read the result:
            extraction_response = uipath.documents_v2.retrieve_model_extraction_result(start_response)
            ```
        """
        _exactly_one_must_be_provided(file=file, file_path=file_path)
        _url_path((model_name,))
        folder_key = self._model_folder_key(folder_key, folder_path)
        headers = self._model_headers(folder_key)

        with open(Path(file_path), "rb") if file_path else nullcontext(file) as handle:
            document_id = self._request_json(
                "POST",
                url=_models_url(model_name, "digitization", "start"),
                params={"api-version": self._api_version},
                headers=headers,
                files={"File": handle},
            )["documentId"]

        self._wait_for_model_digitization(model_name, folder_key, document_id)

        operation_id = self._request_json(
            "POST",
            url=_models_url(model_name, "extraction", "start"),
            params={"api-version": self._api_version},
            headers=headers,
            json={"documentId": document_id},
        )["operationId"]

        return StartModelExtractionResponse(
            operation_id=operation_id,
            document_id=document_id,
            model_name=model_name,
            folder_key=folder_key,
        )

    @traced(name="documents_start_model_extraction_async", run_type="uipath")
    async def start_model_extraction_async(
        self,
        model_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> StartModelExtractionResponse:
        """Asynchronous version of the [`start_model_extraction`][uipath.platform.documents._documents_service_v2.DocumentsServiceV2.start_model_extraction] method."""
        _exactly_one_must_be_provided(file=file, file_path=file_path)
        _url_path((model_name,))
        folder_key = await self._model_folder_key_async(folder_key, folder_path)
        headers = self._model_headers(folder_key)

        with open(Path(file_path), "rb") if file_path else nullcontext(file) as handle:
            document_id = (
                await self._request_json_async(
                    "POST",
                    url=_models_url(model_name, "digitization", "start"),
                    params={"api-version": self._api_version},
                    headers=headers,
                    files={"File": handle},
                )
            )["documentId"]

        await self._wait_for_model_digitization_async(
            model_name, folder_key, document_id
        )

        operation_id = (
            await self._request_json_async(
                "POST",
                url=_models_url(model_name, "extraction", "start"),
                params={"api-version": self._api_version},
                headers=headers,
                json={"documentId": document_id},
            )
        )["operationId"]

        return StartModelExtractionResponse(
            operation_id=operation_id,
            document_id=document_id,
            model_name=model_name,
            folder_key=folder_key,
        )

    def _model_extraction_result_url(
        self, start_response: StartModelExtractionResponse
    ) -> Endpoint:
        return _models_url(
            start_response.model_name,
            "extraction",
            "result",
            start_response.operation_id,
        )

    def _model_extraction_response(
        self, response: Dict[str, Any], start_response: StartModelExtractionResponse
    ) -> ModelExtractionResponse:
        result = _operation_result(
            response, start_response.operation_id, "Model extraction"
        )
        return ModelExtractionResponse.model_validate(
            {
                **result,
                "modelName": start_response.model_name,
                "folderKey": start_response.folder_key,
            }
        )

    def _retrieve_model_extraction_result(
        self, start_response: StartModelExtractionResponse
    ) -> ModelExtractionResponse:
        response = self._request_json(
            "GET",
            url=self._model_extraction_result_url(start_response),
            params={"api-version": self._api_version},
            headers=self._model_headers(start_response.folder_key),
        )
        return self._model_extraction_response(response, start_response)

    async def _retrieve_model_extraction_result_async(
        self, start_response: StartModelExtractionResponse
    ) -> ModelExtractionResponse:
        response = await self._request_json_async(
            "GET",
            url=self._model_extraction_result_url(start_response),
            params={"api-version": self._api_version},
            headers=self._model_headers(start_response.folder_key),
        )
        return self._model_extraction_response(response, start_response)

    @traced(name="documents_retrieve_model_extraction_result", run_type="uipath")
    def retrieve_model_extraction_result(
        self, start_response: StartModelExtractionResponse
    ) -> ModelExtractionResponse:
        """Retrieve the result of an extraction started with `start_model_extraction` (single-shot, non-blocking).

        It makes a single request and returns the result if available, or raises an exception if not complete.

        Args:
            start_response (StartModelExtractionResponse): The response returned by `start_model_extraction`.

        Returns:
            ModelExtractionResponse: The extraction response containing the extracted data.

        Raises:
            OperationNotCompleteException: If the extraction is not yet complete.
            OperationFailedException: If the extraction operation failed.

        Examples:
            ```python
            extraction_response = uipath.documents_v2.retrieve_model_extraction_result(start_response)
            ```
        """
        return self._retrieve_model_extraction_result(start_response)

    @traced(name="documents_retrieve_model_extraction_result_async", run_type="uipath")
    async def retrieve_model_extraction_result_async(
        self, start_response: StartModelExtractionResponse
    ) -> ModelExtractionResponse:
        """Asynchronous version of the [`retrieve_model_extraction_result`][uipath.platform.documents._documents_service_v2.DocumentsServiceV2.retrieve_model_extraction_result] method."""
        return await self._retrieve_model_extraction_result_async(start_response)

    @traced(name="documents_extract_with_model", run_type="uipath")
    def extract_with_model(
        self,
        model_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ModelExtractionResponse:
        """Extract data from a document with an IXP model deployed to a folder, waiting for the result.

        It is `start_model_extraction` followed by `retrieve_model_extraction_result` until the result is ready.

        Args:
            model_name (str): Name of the model deployed to the folder, e.g. `invoices-ixp`. This is the model's URL name, not its display name.
            file (FileContent, optional): The document file to be processed.
            file_path (str, optional): Path to the document file to be processed.
            folder_key (str, optional): Key of the folder the model is deployed to.
            folder_path (str, optional): Path of the folder the model is deployed to. Its key is looked up.

        Note:
            Either `file` or `file_path` must be provided, but not both.
            Pass at most one of `folder_key` and `folder_path`. Without either, the current job's folder is used.

        Returns:
            ModelExtractionResponse: The extraction response containing the extracted data.

        Raises:
            OperationFailedException: If the extraction operation failed.
            TimeoutError: If the extraction didn't finish within the polling timeout.

        Examples:
            ```python
            with open("path/to/document.pdf", "rb") as file:
                extraction_response = uipath.documents_v2.extract_with_model(
                    model_name="invoices-ixp",
                    file=file,
                    folder_path="Shared/Invoices",
                )
            ```
        """
        start_response = self.start_model_extraction(
            model_name=model_name,
            file=file,
            file_path=file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        start_time = time.monotonic()
        while True:
            try:
                return self._retrieve_model_extraction_result(start_response)
            except OperationNotCompleteException:
                if time.monotonic() - start_time >= self.polling_timeout:
                    raise TimeoutError("Operation timed out.") from None
                time.sleep(self.polling_interval)

    @traced(name="documents_extract_with_model_async", run_type="uipath")
    async def extract_with_model_async(
        self,
        model_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> ModelExtractionResponse:
        """Asynchronous version of the [`extract_with_model`][uipath.platform.documents._documents_service_v2.DocumentsServiceV2.extract_with_model] method."""
        start_response = await self.start_model_extraction_async(
            model_name=model_name,
            file=file,
            file_path=file_path,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        start_time = time.monotonic()
        while True:
            try:
                return await self._retrieve_model_extraction_result_async(
                    start_response
                )
            except OperationNotCompleteException:
                if time.monotonic() - start_time >= self.polling_timeout:
                    raise TimeoutError("Operation timed out.") from None
                await asyncio.sleep(self.polling_interval)
