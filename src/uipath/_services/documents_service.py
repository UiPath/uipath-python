import asyncio
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple
from uuid import UUID

from httpx._types import FileContent

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint
from ..models.documents import (
    ActionPriority,
    ExtractionResponse,
    ValidatedResult,
    ValidationAction,
)
from ..tracing._traced import traced
from ._base_service import BaseService

POLLING_INTERVAL = 2  # seconds
POLLING_TIMEOUT = 300  # seconds


class DocumentsService(FolderContext, BaseService):
    """Service for managing UiPath DocumentUnderstanding Document Operations.

    This service provides methods to extract data from documents using UiPath's Document Understanding capabilities.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def _get_common_headers(self) -> Dict[str, str]:
        return {
            "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
        }

    def _get_project_id_by_name(self, project_name: str) -> str:
        response = self.request(
            "GET",
            url=Endpoint("/du_/api/framework/projects"),
            params={"api-version": 1.1, "type": "IXP"},
            headers=self._get_common_headers(),
        )

        try:
            return next(
                project["id"]
                for project in response.json()["projects"]
                if project["name"] == project_name
            )
        except StopIteration:
            raise ValueError(f"Project '{project_name}' not found.") from None

    async def _get_project_id_by_name_async(self, project_name: str) -> str:
        response = await self.request_async(
            "GET",
            url=Endpoint("/du_/api/framework/projects"),
            params={"api-version": 1.1, "type": "IXP"},
            headers=self._get_common_headers(),
        )

        try:
            return next(
                project["id"]
                for project in response.json()["projects"]
                if project["name"] == project_name
            )
        except StopIteration:
            raise ValueError(f"Project '{project_name}' not found.") from None

    def _get_project_tags(self, project_id: str) -> Set[str]:
        response = self.request(
            "GET",
            url=Endpoint(f"/du_/api/framework/projects/{project_id}/tags"),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        )
        return {tag["name"] for tag in response.json().get("tags", [])}

    async def _get_project_tags_async(self, project_id: str) -> Set[str]:
        response = await self.request_async(
            "GET",
            url=Endpoint(f"/du_/api/framework/projects/{project_id}/tags"),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        )
        return {tag["name"] for tag in response.json().get("tags", [])}

    def _get_project_id_and_validate_tag(self, project_name: str, tag: str) -> str:
        project_id = self._get_project_id_by_name(project_name)
        tags = self._get_project_tags(project_id)
        if tag not in tags:
            raise ValueError(
                f"Tag '{tag}' not found in project '{project_name}'. Available tags: {tags}"
            )

        return project_id

    async def _get_project_id_and_validate_tag_async(
        self, project_name: str, tag: str
    ) -> str:
        project_id = await self._get_project_id_by_name_async(project_name)
        tags = await self._get_project_tags_async(project_id)
        if tag not in tags:
            raise ValueError(
                f"Tag '{tag}' not found in project '{project_name}'. Available tags: {tags}"
            )

        return project_id

    def _start_digitization(
        self,
        project_id: str,
        file: FileContent,
    ) -> str:
        return self.request(
            "POST",
            url=Endpoint(
                f"/du_/api/framework/projects/{project_id}/digitization/start"
            ),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
            files={"File": file},
        ).json()["documentId"]

    async def _start_digitization_async(
        self,
        project_id: str,
        file: FileContent,
    ) -> str:
        return (
            await self.request_async(
                "POST",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/digitization/start"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                files={"File": file},
            )
        ).json()["documentId"]

    def _start_extraction(
        self,
        project_id: str,
        tag: str,
        document_id: str,
    ) -> str:
        return self.request(
            "POST",
            url=Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/extraction/start"
            ),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
            json={"documentId": document_id},
        ).json()["operationId"]

    async def _start_extraction_async(
        self,
        project_id: str,
        tag: str,
        document_id: str,
    ) -> str:
        return (
            await self.request_async(
                "POST",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/extraction/start"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                json={"documentId": document_id},
            )
        ).json()["operationId"]

    def _wait_for_operation(
        self,
        result_getter: Callable[[], Tuple[str, Any]],
        wait_statuses: List[str],
        success_status: str,
    ) -> Any:
        start_time = time.monotonic()
        status = wait_statuses[0]
        result = None

        while (
            status in wait_statuses
            and (time.monotonic() - start_time) < POLLING_TIMEOUT
        ):
            status, result = result_getter()
            time.sleep(POLLING_INTERVAL)

        if status != success_status:
            if time.monotonic() - start_time >= POLLING_TIMEOUT:
                raise TimeoutError("Operation timed out.")
            raise RuntimeError(f"Operation failed with status: {status}")

        return result

    async def _wait_for_operation_async(
        self,
        result_getter: Callable[[], Awaitable[Tuple[str, Any]]],
        wait_statuses: List[str],
        success_status: str,
    ) -> Any:
        start_time = time.monotonic()
        status = wait_statuses[0]
        result = None

        while (
            status in wait_statuses
            and (time.monotonic() - start_time) < POLLING_TIMEOUT
        ):
            status, result = await result_getter()
            await asyncio.sleep(POLLING_INTERVAL)

        if status != success_status:
            if time.monotonic() - start_time >= POLLING_TIMEOUT:
                raise TimeoutError("Operation timed out.")
            raise RuntimeError(f"Operation failed with status: {status}")

        return result

    def _wait_for_extraction(
        self, project_id: str, tag: str, operation_id: str
    ) -> ExtractionResponse:
        extraction_response = self._wait_for_operation(
            result_getter=lambda: (
                (
                    result := self.request(
                        method="GET",
                        url=Endpoint(
                            f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/extraction/result/{operation_id}"
                        ),
                        params={"api-version": 1.1},
                        headers=self._get_common_headers(),
                    ).json()
                )["status"],
                result.get("result", None),
            ),
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        extraction_response["projectId"] = project_id
        extraction_response["tag"] = tag
        return ExtractionResponse.model_validate(extraction_response)

    async def _wait_for_extraction_async(
        self, project_id: str, tag: str, operation_id: str
    ) -> ExtractionResponse:
        async def result_getter() -> Tuple[str, Any]:
            result = await self.request_async(
                method="GET",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/extraction/result/{operation_id}"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            )
            json_result = result.json()
            return json_result["status"], json_result.get("result", None)

        extraction_response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        extraction_response["projectId"] = project_id
        extraction_response["tag"] = tag
        return ExtractionResponse.model_validate(extraction_response)

    @traced(name="documents_extract", run_type="uipath")
    def extract(
        self,
        project_name: str,
        tag: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> ExtractionResponse:
        """Extract predicted data from a document using an IXP project.

        Args:
            project_name (str): Name of the IXP project. Details about IXP projects can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/overview/managing-projects#creating-a-new-project).
            tag (str): Tag of the published project version.
            file (FileContent, optional): The document file to be processed.
            file_path (str, optional): Path to the document file to be processed.

        Note:
            Either `file` or `file_path` must be provided, but not both.

        Returns:
            ExtractionResponse: The extraction result containing predicted data.

        Examples:
            ```python
            with open("path/to/document.pdf", "rb") as file:
                extraction_response = service.extract(
                    project_name="MyProject",
                    tag="live",
                    file=file,
                )
            ```
        """
        if file is None and file_path is None:
            raise ValueError("Either `file` or `file_path` must be provided")
        if file is not None and file_path is not None:
            raise ValueError("`file` and `file_path` are mutually exclusive")

        project_id = self._get_project_id_and_validate_tag(
            project_name=project_name, tag=tag
        )

        if file_path is not None:
            with open(Path(file_path), "rb") as handle:
                document_id = self._start_digitization(
                    project_id=project_id, file=handle
                )
        else:
            document_id = self._start_digitization(project_id=project_id, file=file)  # type: ignore

        operation_id = self._start_extraction(
            project_id=project_id, tag=tag, document_id=document_id
        )

        return self._wait_for_extraction(
            project_id=project_id, tag=tag, operation_id=operation_id
        )

    @traced(name="documents_extract_async", run_type="uipath")
    async def extract_async(
        self,
        project_name: str,
        tag: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> ExtractionResponse:
        """Asynchronously extract predicted data from a document using an IXP project."""
        if file is None and file_path is None:
            raise ValueError("Either `file` or `file_path` must be provided")
        if file is not None and file_path is not None:
            raise ValueError("`file` and `file_path` are mutually exclusive")

        project_id = await self._get_project_id_and_validate_tag_async(
            project_name=project_name, tag=tag
        )

        if file_path is not None:
            with open(Path(file_path), "rb") as handle:
                document_id = await self._start_digitization_async(
                    project_id=project_id, file=handle
                )
        else:
            document_id = await self._start_digitization_async(
                project_id=project_id,
                file=file,  # type: ignore
            )

        operation_id = await self._start_extraction_async(
            project_id=project_id, tag=tag, document_id=document_id
        )

        return await self._wait_for_extraction_async(
            project_id=project_id, tag=tag, operation_id=operation_id
        )

    def _start_validation(
        self,
        project_id: str,
        tag: str,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> str:
        return self.request(
            "POST",
            url=Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/start"
            ),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
            json={
                "extractionResult": extraction_response.extraction_result.model_dump(),
                "documentId": extraction_response.extraction_result.document_id,
                "actionTitle": action_title,
                "actionPriority": action_priority,
                "actionCatalog": action_catalog,
                "actionFolder": action_folder,
                "storageBucketName": storage_bucket_name,
                "allowChangeOfDocumentType": True,
                "storageBucketDirectoryPath": storage_bucket_directory_path,
            },
        ).json()["operationId"]

    async def _start_validation_async(
        self,
        project_id: str,
        tag: str,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> str:
        return (
            await self.request_async(
                "POST",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/start"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                json={
                    "extractionResult": extraction_response.extraction_result.model_dump(),
                    "documentId": extraction_response.extraction_result.document_id,
                    "actionTitle": action_title,
                    "actionPriority": action_priority,
                    "actionCatalog": action_catalog,
                    "actionFolder": action_folder,
                    "storageBucketName": storage_bucket_name,
                    "allowChangeOfDocumentType": True,
                    "storageBucketDirectoryPath": storage_bucket_directory_path,
                },
            )
        ).json()["operationId"]

    def _get_validation_result(
        self, project_id: str, tag: str, operation_id: str
    ) -> Dict:  # type: ignore
        return self.request(
            method="GET",
            url=Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/result/{operation_id}"
            ),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        ).json()

    async def _get_validation_result_async(
        self, project_id: str, tag: str, operation_id: str
    ) -> Dict:  # type: ignore
        return (
            await self.request_async(
                method="GET",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/result/{operation_id}"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            )
        ).json()

    def _wait_for_create_validation_action(
        self, project_id: str, tag: str, operation_id: str
    ) -> ValidationAction:
        response = self._wait_for_operation(
            lambda: (
                (
                    result := self._get_validation_result(
                        project_id=project_id, tag=tag, operation_id=operation_id
                    )
                )["status"],
                result.get("result", None),
            ),
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        response["projectId"] = project_id
        response["tag"] = tag
        response["operationId"] = operation_id
        return ValidationAction.model_validate(response)

    async def _wait_for_create_validation_action_async(
        self, project_id: str, tag: str, operation_id: str
    ) -> ValidationAction:
        async def result_getter() -> Tuple[str, Any]:
            result = await self._get_validation_result_async(
                project_id=project_id, tag=tag, operation_id=operation_id
            )
            return result["status"], result.get("result", None)

        response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        response["projectId"] = project_id
        response["tag"] = tag
        response["operationId"] = operation_id
        return ValidationAction.model_validate(response)

    @traced(name="documents_create_validation_action", run_type="uipath")
    def create_validation_action(
        self,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> ValidationAction:
        """Create a validation action for a document based on the extraction response. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-extractions).

        Args:
            action_title (str): Title of the action.
            action_priority (ActionPriority): Priority of the action.
            action_catalog (str): Catalog of the action.
            action_folder (str): Folder of the action.
            storage_bucket_name (str): Name of the storage bucket.
            storage_bucket_directory_path (str): Directory path in the storage bucket.
            extraction_response (ExtractionResponse): The extraction result to be validated, typically obtained from the [`extract`][uipath._services.documents_service.DocumentsService.extract] method.

        Returns:
            ValidationAction: The created validation action.

        Examples:
            ```python
            validation_action = service.create_validation_action(
                action_title="Test Validation Action",
                action_priority=ActionPriority.MEDIUM,
                action_catalog="default_du_actions",
                action_folder="Shared",
                storage_bucket_name="TestBucket",
                storage_bucket_directory_path="TestDirectory",
                extraction_response=extraction_response,
            )
            ```
        """
        operation_id = self._start_validation(
            project_id=extraction_response.project_id,
            tag=extraction_response.tag,  # should I validate tag again?
            action_title=action_title,
            action_priority=action_priority,
            action_catalog=action_catalog,
            action_folder=action_folder,
            storage_bucket_name=storage_bucket_name,
            storage_bucket_directory_path=storage_bucket_directory_path,
            extraction_response=extraction_response,
        )

        return self._wait_for_create_validation_action(
            project_id=extraction_response.project_id,
            tag=extraction_response.tag,
            operation_id=operation_id,
        )

    @traced(name="documents_create_validation_action_async", run_type="uipath")
    async def create_validation_action_async(
        self,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> ValidationAction:
        """Asynchronously create a validation action for a document based on the extraction response."""
        # Add reference to sync method docstring
        operation_id = await self._start_validation_async(
            project_id=extraction_response.project_id,
            tag=extraction_response.tag,  # should I validate tag again?
            action_title=action_title,
            action_priority=action_priority,
            action_catalog=action_catalog,
            action_folder=action_folder,
            storage_bucket_name=storage_bucket_name,
            storage_bucket_directory_path=storage_bucket_directory_path,
            extraction_response=extraction_response,
        )

        return await self._wait_for_create_validation_action_async(
            project_id=extraction_response.project_id,
            tag=extraction_response.tag,
            operation_id=operation_id,
        )

    @traced(name="documents_get_validation_result", run_type="uipath")
    def get_validation_result(
        self, validation_action: ValidationAction
    ) -> ValidatedResult:
        """Get the result of a validation action.

        Note:
            This method will block until the validation action is completed, meaning the user has completed the validation in UiPath Action Center.

        Args:
            validation_action (ValidationAction): The validation action to get the result for, typically obtained from the [`create_validation_action`][uipath._services.documents_service.DocumentsService.create_validation_action] method.

        Returns:
            ValidatedResult: The result of the validation action.

        Examples:
            ```python
            validated_result = service.get_validation_result(validation_action)
            ```
        """
        response = self._wait_for_operation(
            result_getter=lambda: (
                (
                    result := self._get_validation_result(
                        project_id=validation_action.project_id,
                        tag=validation_action.tag,
                        operation_id=validation_action.operation_id,
                    )
                )["result"]["actionStatus"],
                result["result"].get("validatedExtractionResults", None),
            ),
            wait_statuses=["Unassigned", "Pending"],
            success_status="Completed",
        )

        return ValidatedResult.model_validate(response)

    @traced(name="documents_get_validation_result_async", run_type="uipath")
    async def get_validation_result_async(
        self, validation_action: ValidationAction
    ) -> ValidatedResult:
        """Asynchronously get the result of a validation action."""

        async def result_getter() -> Tuple[str, Any]:
            result = await self._get_validation_result_async(
                project_id=validation_action.project_id,
                tag=validation_action.tag,
                operation_id=validation_action.operation_id,
            )
            return result["result"]["actionStatus"], result["result"].get(
                "validatedExtractionResults", None
            )

        response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["Unassigned", "Pending"],
            success_status="Completed",
        )

        return ValidatedResult.model_validate(response)
