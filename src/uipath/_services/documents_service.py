import asyncio
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint
from ..models.documents import (
    ActionPriority,
    ClassificationResponse,
    ClassificationResult,
    ExtractionResponse,
    ExtractionResponseIXP,
    FileContent,
    ProjectType,
    ValidateClassificationAction,
    ValidateExtractionAction,
)
from ..tracing import traced
from ._base_service import BaseService

POLLING_INTERVAL = 2  # seconds
POLLING_TIMEOUT = 300  # seconds


def _must_not_be_provided(**kwargs: Any) -> None:
    for name, value in kwargs.items():
        if value is not None:
            raise ValueError(f"`{name}` must not be provided")


def _must_be_provided(**kwargs: Any) -> None:
    for name, value in kwargs.items():
        if value is None:
            raise ValueError(f"`{name}` must be provided")


def _exactly_one_must_be_provided(**kwargs: Any) -> None:
    provided = [name for name, value in kwargs.items() if value is not None]
    if len(provided) != 1:
        raise ValueError(
            f"Exactly one of `{', '.join(kwargs.keys())}` must be provided"
        )


def _validate_classify_params(
    project_type: ProjectType,
    tag: Optional[str],
    project_name: Optional[str],
    file: Optional[FileContent],
    file_path: Optional[str],
) -> None:
    _exactly_one_must_be_provided(file=file, file_path=file_path)
    if project_type == ProjectType.PRETRAINED:
        _must_not_be_provided(
            project_name=project_name,
            tag=tag,
        )
    else:
        _must_be_provided(
            project_name=project_name,
            tag=tag,
        )


def _validate_extract_params_and_get_project_type(
    tag: Optional[str],
    project_name: Optional[str],
    file: Optional[FileContent],
    file_path: Optional[str],
    classification_result: Optional[ClassificationResult],
    project_type: Optional[ProjectType],
    document_type_name: Optional[str],
) -> ProjectType:
    if file or file_path:
        _exactly_one_must_be_provided(file=file, file_path=file_path)
        _must_be_provided(project_type=project_type)
        _must_not_be_provided(
            classification_result=classification_result,
        )

        if project_type == ProjectType.PRETRAINED:
            _must_not_be_provided(tag=tag, project_name=project_name)
            _must_be_provided(document_type_name=document_type_name)
        elif project_type == ProjectType.MODERN:
            _must_be_provided(
                project_name=project_name,
                tag=tag,
                document_type_name=document_type_name,
            )
        else:
            _must_be_provided(project_name=project_name, tag=tag)
            _must_not_be_provided(document_type_name=document_type_name)
    else:
        _must_be_provided(classification_result=classification_result)
        _must_not_be_provided(
            tag=tag,
            project_name=project_name,
            project_type=project_type,
            file=file,
            file_path=file_path,
            document_type_name=document_type_name,
        )
        project_type = classification_result.project_type  # type: ignore

    return project_type  # type: ignore


class DocumentsService(FolderContext, BaseService):
    """Service for managing UiPath DocumentUnderstanding Document Operations.

    This service provides methods to extract data from documents using UiPath's Document Understanding capabilities.

    !!! warning "Preview Feature"
        This function is currently experimental.
        Behavior and parameters are subject to change in future versions.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def _get_common_headers(self) -> Dict[str, str]:
        return {
            "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
        }

    def _get_project_id_by_name(
        self, project_name: str, project_type: ProjectType
    ) -> str:
        response = self.request(
            "GET",
            url=Endpoint("/du_/api/framework/projects"),
            params={"api-version": 1.1, "type": project_type.value},
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

    async def _get_project_id_by_name_async(
        self, project_name: str, project_type: ProjectType
    ) -> str:
        response = await self.request_async(
            "GET",
            url=Endpoint("/du_/api/framework/projects"),
            params={"api-version": 1.1, "type": project_type.value},
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

    def _get_document_id(
        self,
        project_id: Optional[str],
        file: Optional[FileContent],
        file_path: Optional[str],
        classification_result: Optional[ClassificationResult],
    ) -> str:
        if classification_result is not None:
            return classification_result.document_id

        document_id = self._start_digitization(
            project_id=project_id,  # type: ignore
            file=file,
            file_path=file_path,
        )
        self._wait_for_digitization(
            project_id=project_id,  # type: ignore
            document_id=document_id,
        )

        return document_id

    async def _get_document_id_async(
        self,
        project_id: Optional[str],
        file: Optional[FileContent],
        file_path: Optional[str],
        classification_result: Optional[ClassificationResult],
    ) -> str:
        if classification_result is not None:
            return classification_result.document_id

        document_id = await self._start_digitization_async(
            project_id=project_id,  # type: ignore
            file=file,
            file_path=file_path,
        )
        await self._wait_for_digitization_async(
            project_id=project_id,  # type: ignore
            document_id=document_id,
        )

        return document_id

    def _get_project_id_and_tag(
        self,
        tag: Optional[str],
        project_name: Optional[str],
        project_type: Optional[ProjectType],
        classification_result: Optional[ClassificationResult],
    ) -> Tuple[str, Optional[str]]:
        if project_name is not None:
            project_id = self._get_project_id_by_name(
                project_name,
                project_type,  # type: ignore
            )
        elif project_type == ProjectType.PRETRAINED:
            return str(UUID(int=0)), None
        else:
            project_id = classification_result.project_id  # type: ignore
            tag = classification_result.tag  # type: ignore

        tags = self._get_project_tags(project_id)
        if tag not in tags:
            raise ValueError(
                f"Tag '{tag}' not found in project '{project_name}'. Available tags: {tags}"
            )

        return project_id, tag

    async def _get_project_id_and_tag_async(
        self,
        tag: Optional[str],
        project_name: Optional[str],
        project_type: Optional[ProjectType],
        classification_result: Optional[ClassificationResult],
    ) -> Tuple[str, Optional[str]]:
        if project_name is not None:
            project_id = await self._get_project_id_by_name_async(
                project_name,
                project_type,  # type: ignore
            )
        elif project_type == ProjectType.PRETRAINED:
            return str(UUID(int=0)), None
        else:
            project_id = classification_result.project_id  # type: ignore
            tag = classification_result.tag  # type: ignore

        tags = await self._get_project_tags_async(project_id)
        if tag not in tags:
            raise ValueError(
                f"Tag '{tag}' not found in project '{project_name}'. Available tags: {tags}"
            )

        return project_id, tag

    def _start_digitization(
        self,
        project_id: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> str:
        with open(Path(file_path), "rb") if file_path else nullcontext(file) as handle:
            return self.request(
                "POST",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/digitization/start"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                files={"File": handle},
            ).json()["documentId"]

    async def _start_digitization_async(
        self,
        project_id: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> str:
        with open(Path(file_path), "rb") if file_path else nullcontext(file) as handle:
            return (
                await self.request_async(
                    "POST",
                    url=Endpoint(
                        f"/du_/api/framework/projects/{project_id}/digitization/start"
                    ),
                    params={"api-version": 1.1},
                    headers=self._get_common_headers(),
                    files={"File": handle},
                )
            ).json()["documentId"]

    def _wait_for_digitization(self, project_id: str, document_id: str) -> None:
        def result_getter() -> Tuple[str, Optional[str], Optional[str]]:
            result = self.request(
                method="GET",
                url=Endpoint(
                    f"/du_/api/framework/projects/{project_id}/digitization/result/{document_id}"
                ),
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            ).json()
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

    async def _wait_for_digitization_async(
        self, project_id: str, document_id: str
    ) -> None:
        async def result_getter() -> Tuple[str, Optional[str], Optional[str]]:
            result = (
                await self.request_async(
                    method="GET",
                    url=Endpoint(
                        f"/du_/api/framework/projects/{project_id}/digitization/result/{document_id}"
                    ),
                    params={"api-version": 1.1},
                    headers=self._get_common_headers(),
                )
            ).json()
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

    def _get_document_type_id(
        self,
        project_id: str,
        document_type_name: Optional[str],
        project_type: ProjectType,
        classification_result: Optional[ClassificationResult],
    ) -> str:
        if project_type == ProjectType.IXP:
            return str(UUID(int=0))

        if classification_result is not None:
            return classification_result.document_type_id

        response = self.request(
            "GET",
            url=Endpoint(f"/du_/api/framework/projects/{project_id}/document-types"),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        )

        try:
            return next(
                extractor["id"]
                for extractor in response.json().get("documentTypes", [])
                if extractor["name"].lower() == document_type_name.lower()  # type: ignore
            )
        except StopIteration:
            raise ValueError(
                f"Document type '{document_type_name}' not found."
            ) from None

    async def _get_document_type_id_async(
        self,
        project_id: str,
        document_type_name: Optional[str],
        project_type: ProjectType,
        classification_result: Optional[ClassificationResult],
    ) -> str:
        if project_type == ProjectType.IXP:
            return str(UUID(int=0))

        if classification_result is not None:
            return classification_result.document_type_id

        response = await self.request_async(
            "GET",
            url=Endpoint(f"/du_/api/framework/projects/{project_id}/document-types"),
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        )

        try:
            return next(
                extractor["id"]
                for extractor in response.json().get("documentTypes", [])
                if extractor["name"].lower() == document_type_name.lower()  # type: ignore
            )
        except StopIteration:
            raise ValueError(
                f"Document type '{document_type_name}' not found."
            ) from None

    def _start_extraction(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        document_id: str,
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/extraction/start"
            )

        return self.request(
            "POST",
            url=url,
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
            json={"documentId": document_id},
        ).json()["operationId"]

    async def _start_extraction_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        document_id: str,
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/extraction/start"
            )

        return (
            await self.request_async(
                "POST",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                json={"documentId": document_id},
            )
        ).json()["operationId"]

    def _wait_for_operation(
        self,
        result_getter: Callable[[], Tuple[Any, Optional[Any], Optional[Any]]],
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
            status, error, result = result_getter()
            time.sleep(POLLING_INTERVAL)

        if status != success_status:
            if time.monotonic() - start_time >= POLLING_TIMEOUT:
                raise TimeoutError("Operation timed out.")
            raise RuntimeError(
                f"Operation failed with status: {status}, error: {error}"
            )

        return result

    async def _wait_for_operation_async(
        self,
        result_getter: Callable[
            [], Awaitable[Tuple[Any, Optional[Any], Optional[Any]]]
        ],
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
            status, error, result = await result_getter()
            await asyncio.sleep(POLLING_INTERVAL)

        if status != success_status:
            if time.monotonic() - start_time >= POLLING_TIMEOUT:
                raise TimeoutError("Operation timed out.")
            raise RuntimeError(
                f"Operation failed with status: {status}, error: {error}"
            )

        return result

    def _wait_for_extraction(
        self,
        project_id: str,
        tag: Optional[str],
        document_type_id: str,
        operation_id: str,
        project_type: ProjectType,
    ) -> Union[ExtractionResponse, ExtractionResponseIXP]:
        def result_getter() -> Tuple[str, str, Any]:
            if project_type == ProjectType.PRETRAINED:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/result/{operation_id}"
                )
            else:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/extraction/result/{operation_id}"
                )

            result = self.request(
                method="GET",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            ).json()
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        extraction_response = self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        extraction_response["projectId"] = project_id
        extraction_response["tag"] = tag
        extraction_response["documentTypeId"] = document_type_id
        extraction_response["projectType"] = project_type

        if project_type == ProjectType.IXP:
            return ExtractionResponseIXP.model_validate(extraction_response)

        return ExtractionResponse.model_validate(extraction_response)

    async def _wait_for_extraction_async(
        self,
        project_id: str,
        tag: Optional[str],
        document_type_id: str,
        operation_id: str,
        project_type: ProjectType,
    ) -> Union[ExtractionResponse, ExtractionResponseIXP]:
        async def result_getter() -> Tuple[str, str, Any]:
            if project_type == ProjectType.PRETRAINED:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/result/{operation_id}"
                )
            else:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/extraction/result/{operation_id}"
                )

            result = (
                await self.request_async(
                    method="GET",
                    url=url,
                    params={"api-version": 1.1},
                    headers=self._get_common_headers(),
                )
            ).json()
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        extraction_response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        extraction_response["projectId"] = project_id
        extraction_response["tag"] = tag
        extraction_response["documentTypeId"] = document_type_id
        extraction_response["projectType"] = project_type

        if project_type == ProjectType.IXP:
            return ExtractionResponseIXP.model_validate(extraction_response)

        return ExtractionResponse.model_validate(extraction_response)

    def _start_classification(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_id: str,
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/classification/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/classification/start"
            )

        return self.request(
            "POST",
            url=url,
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
            json={"documentId": document_id},
        ).json()["operationId"]

    async def _start_classification_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_id: str,
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/classification/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/classification/start"
            )

        return (
            await self.request_async(
                "POST",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                json={"documentId": document_id},
            )
        ).json()["operationId"]

    def _wait_for_classification(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        operation_id: str,
    ) -> List[ClassificationResult]:
        def result_getter() -> Tuple[str, Optional[str], Optional[str]]:
            if project_type == ProjectType.PRETRAINED:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/classification/result/{operation_id}"
                )
            else:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/classification/result/{operation_id}"
                )

            result = self.request(
                method="GET",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            ).json()
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        classification_response = self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )
        for classification_result in classification_response["classificationResults"]:
            classification_result["ProjectId"] = project_id
            classification_result["ProjectType"] = project_type
            classification_result["Tag"] = tag

        return ClassificationResponse.model_validate(
            classification_response
        ).classification_results

    async def _wait_for_classification_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        operation_id: str,
    ) -> List[ClassificationResult]:
        async def result_getter() -> Tuple[str, Optional[str], Optional[str]]:
            if project_type == ProjectType.PRETRAINED:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/classification/result/{operation_id}"
                )
            else:
                url = Endpoint(
                    f"/du_/api/framework/projects/{project_id}/{tag}/classification/result/{operation_id}"
                )

            result = (
                await self.request_async(
                    method="GET",
                    url=url,
                    params={"api-version": 1.1},
                    headers=self._get_common_headers(),
                )
            ).json()
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        classification_response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )
        for classification_result in classification_response["classificationResults"]:
            classification_result["ProjectId"] = project_id
            classification_result["ProjectType"] = project_type
            classification_result["Tag"] = tag

        return ClassificationResponse.model_validate(
            classification_response
        ).classification_results

    @traced(name="documents_classify", run_type="uipath")
    def classify(
        self,
        project_type: ProjectType,
        tag: Optional[str] = None,
        project_name: Optional[str] = None,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> List[ClassificationResult]:
        """Classify a document using a DU Modern project.

        Args:
            project_type (ProjectType): Type of the project.
            project_name (str, optional): Name of the [DU Modern](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding) project. Must be provided if `project_type` is not `ProjectType.PRETRAINED`.
            tag (str, optional): Tag of the published project version. Must be provided if `project_type` is not `ProjectType.PRETRAINED`.
            file (FileContent, optional): The document file to be classified.
            file_path (str, optional): Path to the document file to be classified.

        Note:
            Either `file` or `file_path` must be provided, but not both.

        Returns:
            List[ClassificationResult]: A list of classification results.

        Examples:
            ```python
            Modern DU project:
            with open("path/to/document.pdf", "rb") as file:
                classification_results = service.classify(
                    project_name="MyModernProjectName",
                    tag="Production",
                    file=file,
                )

            Pretrained project:
            with open("path/to/document.pdf", "rb") as file:
                classification_results = service.classify(
                    project_type=ProjectType.PRETRAINED,
                    file=file,
                )
            ```
        """
        _validate_classify_params(
            project_type=project_type,
            tag=tag,
            project_name=project_name,
            file=file,
            file_path=file_path,
        )

        project_id, tag = self._get_project_id_and_tag(
            tag=tag,
            project_name=project_name,
            project_type=project_type,
            classification_result=None,
        )

        document_id = self._get_document_id(
            project_id=project_id,
            file=file,
            file_path=file_path,
            classification_result=None,
        )

        operation_id = self._start_classification(
            project_id=project_id,
            project_type=project_type,
            tag=tag,
            document_id=document_id,
        )

        return self._wait_for_classification(
            project_id=project_id,
            project_type=project_type,
            tag=tag,
            operation_id=operation_id,
        )

    @traced(name="documents_classify_async", run_type="uipath")
    async def classify_async(
        self,
        project_type: ProjectType,
        tag: Optional[str] = None,
        project_name: Optional[str] = None,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> List[ClassificationResult]:
        """Asynchronously version of the [`classify`][uipath._services.documents_service.DocumentsService.classify] method."""
        _validate_classify_params(
            project_type=project_type,
            tag=tag,
            project_name=project_name,
            file=file,
            file_path=file_path,
        )

        project_id, tag = await self._get_project_id_and_tag_async(
            tag=tag,
            project_name=project_name,
            project_type=project_type,
            classification_result=None,
        )

        document_id = await self._get_document_id_async(
            project_id=project_id,
            file=file,
            file_path=file_path,
            classification_result=None,
        )

        operation_id = await self._start_classification_async(
            project_id=project_id,
            project_type=project_type,
            tag=tag,
            document_id=document_id,
        )

        return await self._wait_for_classification_async(
            project_id=project_id,
            project_type=project_type,
            tag=tag,
            operation_id=operation_id,
        )

    @traced(name="documents_extract", run_type="uipath")
    def extract(
        self,
        tag: Optional[str] = None,
        project_name: Optional[str] = None,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        classification_result: Optional[ClassificationResult] = None,
        project_type: Optional[ProjectType] = None,
        document_type_name: Optional[str] = None,
    ) -> Union[ExtractionResponse, ExtractionResponseIXP]:
        """Extract predicted data from a document using an DU Modern/IXP project.

        Args:
            project_name (str, optional): Name of the [IXP](https://docs.uipath.com/ixp/automation-cloud/latest/overview/managing-projects#creating-a-new-project)/[DU Modern](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding) project. Must be provided if `classification_result` is not provided.
            tag (str): Tag of the published project version. Must be provided if `classification_result` is not provided and `project_type` is not `ProjectType.PRETRAINED`.
            file (FileContent, optional): The document file to be processed. Must be provided if `classification_result` is not provided.
            file_path (str, optional): Path to the document file to be processed. Must be provided if `classification_result` is not provided.
            project_type (ProjectType, optional): Type of the project. Must be provided if `project_name` is provided.
            document_type_name (str, optional): Document type name associated with the extractor to be used for extraction. Required if `project_type` is `ProjectType.MODERN` and `project_name` is provided.
            classification_result (ClassificationResult, optional): The classification result obtained from a previous classification step. If provided, `project_name`, `project_type`, `file`, `file_path`, and `document_type_name` must not be provided.

        Note:
            Either `file` or `file_path` must be provided, but not both.

        Returns:
            Union[ExtractionResponse, ExtractionResponseIXP]: The extraction response containing the extracted data.

        Examples:
            IXP projects:
            ```python
            with open("path/to/document.pdf", "rb") as file:
                extraction_response = service.extract(
                    project_name="MyIXPProjectName",
                    tag="live",
                    file=file,
                )
            ```

            DU Modern projects (providing document type name):
            ```python
            with open("path/to/document.pdf", "rb") as file:
                extraction_response = service.extract(
                    project_name="MyModernProjectName",
                    tag="Production",
                    file=file,
                    project_type=ProjectType.MODERN,
                    document_type_name="Receipts",
                )
            ```

            DU Modern projects (using existing classification result):
            ```python
            with open("path/to/document.pdf", "rb") as file:
                classification_results = uipath.documents.classify(
                    tag="Production",
                    project_name="MyModernProjectName",
                    file=file,
                )

            extraction_result = uipath.documents.extract(
                classification_result=max(classification_results, key=lambda result: result.confidence),
            )
            ```
        """
        project_type = _validate_extract_params_and_get_project_type(
            tag=tag,
            project_name=project_name,
            file=file,
            file_path=file_path,
            classification_result=classification_result,
            project_type=project_type,
            document_type_name=document_type_name,
        )

        project_id, tag = self._get_project_id_and_tag(
            tag=tag,
            project_name=project_name,
            project_type=project_type,
            classification_result=classification_result,
        )

        document_id = self._get_document_id(
            project_id=project_id,
            file=file,
            file_path=file_path,
            classification_result=classification_result,
        )

        document_type_id = self._get_document_type_id(
            project_id=project_id,
            document_type_name=document_type_name,
            project_type=project_type,
            classification_result=classification_result,
        )

        operation_id = self._start_extraction(
            project_id=project_id,
            project_type=project_type,
            tag=tag,
            document_type_id=document_type_id,
            document_id=document_id,
        )

        return self._wait_for_extraction(
            project_id=project_id,
            tag=tag,
            document_type_id=document_type_id,
            operation_id=operation_id,
            project_type=project_type,
        )

    @traced(name="documents_extract_async", run_type="uipath")
    async def extract_async(
        self,
        tag: Optional[str] = None,
        project_name: Optional[str] = None,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        classification_result: Optional[ClassificationResult] = None,
        project_type: Optional[ProjectType] = None,
        document_type_name: Optional[str] = None,
    ) -> Union[ExtractionResponse, ExtractionResponseIXP]:
        """Asynchronously version of the [`extract`][uipath._services.documents_service.DocumentsService.extract] method."""
        project_type = _validate_extract_params_and_get_project_type(
            tag=tag,
            project_name=project_name,
            file=file,
            file_path=file_path,
            classification_result=classification_result,
            project_type=project_type,
            document_type_name=document_type_name,
        )

        project_id, tag = await self._get_project_id_and_tag_async(
            tag=tag,
            project_name=project_name,
            project_type=project_type,
            classification_result=classification_result,
        )

        document_id = await self._get_document_id_async(
            project_id=project_id,
            file=file,
            file_path=file_path,
            classification_result=classification_result,
        )

        document_type_id = await self._get_document_type_id_async(
            project_id=project_id,
            document_type_name=document_type_name,
            project_type=project_type,
            classification_result=classification_result,
        )

        operation_id = await self._start_extraction_async(
            project_id=project_id,
            project_type=project_type,
            tag=tag,
            document_type_id=document_type_id,
            document_id=document_id,
        )

        return await self._wait_for_extraction_async(
            project_id=project_id,
            tag=tag,
            document_type_id=document_type_id,
            operation_id=operation_id,
            project_type=project_type,
        )

    def _start_classification_validation(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        classification_results: List[ClassificationResult],
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/classifiers/validation/start"
            )

        return self.request(
            "POST",
            url=url,
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
            json={
                "classificationResults": [
                    cr.model_dump() for cr in classification_results
                ],
                "documentId": classification_results[0].document_id,
                "actionTitle": action_title,
                "actionPriority": action_priority,
                "actionCatalog": action_catalog,
                "actionFolder": action_folder,
                "storageBucketName": storage_bucket_name,
                "storageBucketDirectoryPath": storage_bucket_directory_path,
            },
        ).json()["operationId"]

    async def _start_classification_validation_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        classification_results: List[ClassificationResult],
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/classifiers/validation/start"
            )

        return (
            await self.request_async(
                "POST",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
                json={
                    "classificationResults": [
                        cr.model_dump() for cr in classification_results
                    ],
                    "documentId": classification_results[0].document_id,
                    "actionTitle": action_title,
                    "actionPriority": action_priority,
                    "actionCatalog": action_catalog,
                    "actionFolder": action_folder,
                    "storageBucketName": storage_bucket_name,
                    "storageBucketDirectoryPath": storage_bucket_directory_path,
                },
            )
        ).json()["operationId"]

    def _start_extraction_validation(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/validation/start"
            )

        return self.request(
            "POST",
            url=url,
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

    async def _start_extraction_validation_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> str:
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/start"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/validation/start"
            )

        return (
            await self.request_async(
                "POST",
                url=url,
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

    def _get_classification_validation_result(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        operation_id: str,
    ) -> Dict:  # type: ignore
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/result/{operation_id}"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/classifiers/validation/result/{operation_id}"
            )

        return self.request(
            method="GET",
            url=url,
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        ).json()

    async def _get_classification_validation_result_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        operation_id: str,
    ) -> Dict:  # type: ignore
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/result/{operation_id}"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/classifiers/validation/result/{operation_id}"
            )

        return (
            await self.request_async(
                method="GET",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            )
        ).json()

    def _get_extraction_validation_result(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        operation_id: str,
    ) -> Dict:  # type: ignore
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/result/{operation_id}"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/validation/result/{operation_id}"
            )

        return self.request(
            method="GET",
            url=url,
            params={"api-version": 1.1},
            headers=self._get_common_headers(),
        ).json()

    async def _get_extraction_validation_result_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        operation_id: str,
    ) -> Dict:  # type: ignore
        if project_type == ProjectType.PRETRAINED:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/result/{operation_id}"
            )
        else:
            url = Endpoint(
                f"/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/validation/result/{operation_id}"
            )

        return (
            await self.request_async(
                method="GET",
                url=url,
                params={"api-version": 1.1},
                headers=self._get_common_headers(),
            )
        ).json()

    def _wait_for_create_validate_classification_action(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        operation_id: str,
    ) -> ValidateClassificationAction:
        def result_getter() -> Tuple[Any, Optional[Any], Optional[Any]]:
            result = self._get_classification_validation_result(
                project_id=project_id,
                project_type=project_type,
                tag=tag,
                operation_id=operation_id,
            )
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        response = self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        response["projectId"] = project_id
        response["projectType"] = project_type
        response["tag"] = tag
        response["operationId"] = operation_id
        return ValidateClassificationAction.model_validate(response)

    async def _wait_for_create_validate_classification_action_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        operation_id: str,
    ) -> ValidateClassificationAction:
        async def result_getter() -> Tuple[Any, Optional[Any], Optional[Any]]:
            result = await self._get_classification_validation_result_async(
                project_id=project_id,
                project_type=project_type,
                tag=tag,
                operation_id=operation_id,
            )
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        response["projectId"] = project_id
        response["projectType"] = project_type
        response["tag"] = tag
        response["operationId"] = operation_id
        return ValidateClassificationAction.model_validate(response)

    def _wait_for_create_validate_extraction_action(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        operation_id: str,
    ) -> ValidateExtractionAction:
        def result_getter() -> Tuple[Any, Optional[Any], Optional[Any]]:
            result = self._get_extraction_validation_result(
                project_id=project_id,
                project_type=project_type,
                tag=tag,
                document_type_id=document_type_id,
                operation_id=operation_id,
            )
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        response = self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        response["projectId"] = project_id
        response["projectType"] = project_type
        response["tag"] = tag
        response["documentTypeId"] = document_type_id
        response["operationId"] = operation_id
        return ValidateExtractionAction.model_validate(response)

    async def _wait_for_create_validate_extraction_action_async(
        self,
        project_id: str,
        project_type: ProjectType,
        tag: Optional[str],
        document_type_id: str,
        operation_id: str,
    ) -> ValidateExtractionAction:
        async def result_getter_async() -> Tuple[Any, Optional[Any], Optional[Any]]:
            result = await self._get_extraction_validation_result_async(
                project_id=project_id,
                project_type=project_type,
                tag=tag,
                document_type_id=document_type_id,
                operation_id=operation_id,
            )
            return (
                result["status"],
                result.get("error", None),
                result.get("result", None),
            )

        response = await self._wait_for_operation_async(
            result_getter=result_getter_async,
            wait_statuses=["NotStarted", "Running"],
            success_status="Succeeded",
        )

        response["projectId"] = project_id
        response["projectType"] = project_type
        response["tag"] = tag
        response["documentTypeId"] = document_type_id
        response["operationId"] = operation_id
        return ValidateExtractionAction.model_validate(response)

    @traced(name="documents_create_validate_classification_action", run_type="uipath")
    def create_validate_classification_action(
        self,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        classification_results: List[ClassificationResult],
    ) -> ValidateClassificationAction:
        """Create a validate classification action for a document based on the classification results. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-classifications).

        Args:
            action_title (str): Title of the action.
            action_priority (ActionPriority): Priority of the action.
            action_catalog (str): Catalog of the action.
            action_folder (str): Folder of the action.
            storage_bucket_name (str): Name of the storage bucket.
            storage_bucket_directory_path (str): Directory path in the storage bucket.
            classification_results (List[ClassificationResult]): The classification results to be validated, typically obtained from the [`classify`][uipath._services.documents_service.DocumentsService.classify] method.

        Returns:
            ValidateClassificationAction: The created validate classification action.

        Examples:
            ```python
            validation_action = service.create_validate_classification_action(
                action_title="Test Validation Action",
                action_priority=ActionPriority.MEDIUM,
                action_catalog="default_du_actions",
                action_folder="Shared",
                storage_bucket_name="du_storage_bucket",
                storage_bucket_directory_path="TestDirectory",
                classification_results=classification_results,
            )
            ```
        """
        if not classification_results:
            raise ValueError("`classification_results` must not be empty")

        operation_id = self._start_classification_validation(
            project_id=classification_results[0].project_id,
            project_type=classification_results[0].project_type,
            tag=classification_results[0].tag,
            action_title=action_title,
            action_priority=action_priority,
            action_catalog=action_catalog,
            action_folder=action_folder,
            storage_bucket_name=storage_bucket_name,
            storage_bucket_directory_path=storage_bucket_directory_path,
            classification_results=classification_results,
        )

        return self._wait_for_create_validate_classification_action(
            project_id=classification_results[0].project_id,
            project_type=classification_results[0].project_type,
            tag=classification_results[0].tag,
            operation_id=operation_id,
        )

    @traced(name="documents_create_validate_classification_action", run_type="uipath")
    async def create_validate_classification_action_async(
        self,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        classification_results: List[ClassificationResult],
    ) -> ValidateClassificationAction:
        """Asynchronous version of the [`create_validation_action`][uipath._services.documents_service.DocumentsService.create_validate_classification_action] method."""
        if not classification_results:
            raise ValueError("`classification_results` must not be empty")

        operation_id = await self._start_classification_validation_async(
            project_id=classification_results[0].project_id,
            project_type=classification_results[0].project_type,
            tag=classification_results[0].tag,
            action_title=action_title,
            action_priority=action_priority,
            action_catalog=action_catalog,
            action_folder=action_folder,
            storage_bucket_name=storage_bucket_name,
            storage_bucket_directory_path=storage_bucket_directory_path,
            classification_results=classification_results,
        )

        return await self._wait_for_create_validate_classification_action_async(
            project_id=classification_results[0].project_id,
            project_type=classification_results[0].project_type,
            tag=classification_results[0].tag,
            operation_id=operation_id,
        )

    @traced(name="documents_create_validate_extraction_action", run_type="uipath")
    def create_validate_extraction_action(
        self,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> ValidateExtractionAction:
        """Create a validate extraction action for a document based on the extraction response. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-extractions).

        Args:
            action_title (str): Title of the action.
            action_priority (ActionPriority): Priority of the action.
            action_catalog (str): Catalog of the action.
            action_folder (str): Folder of the action.
            storage_bucket_name (str): Name of the storage bucket.
            storage_bucket_directory_path (str): Directory path in the storage bucket.
            extraction_response (ExtractionResponse): The extraction result to be validated, typically obtained from the [`extract`][uipath._services.documents_service.DocumentsService.extract] method.

        Returns:
            ValidateClassificationAction: The created validation action.

        Examples:
            ```python
            validation_action = service.create_validate_extraction_action(
                action_title="Test Validation Action",
                action_priority=ActionPriority.MEDIUM,
                action_catalog="default_du_actions",
                action_folder="Shared",
                storage_bucket_name="du_storage_bucket",
                storage_bucket_directory_path="TestDirectory",
                extraction_response=extraction_response,
            )
            ```
        """
        operation_id = self._start_extraction_validation(
            project_id=extraction_response.project_id,
            project_type=extraction_response.project_type,
            tag=extraction_response.tag,
            document_type_id=extraction_response.document_type_id,
            action_title=action_title,
            action_priority=action_priority,
            action_catalog=action_catalog,
            action_folder=action_folder,
            storage_bucket_name=storage_bucket_name,
            storage_bucket_directory_path=storage_bucket_directory_path,
            extraction_response=extraction_response,
        )

        return self._wait_for_create_validate_extraction_action(
            project_id=extraction_response.project_id,
            project_type=extraction_response.project_type,
            tag=extraction_response.tag,
            document_type_id=extraction_response.document_type_id,
            operation_id=operation_id,
        )

    @traced(name="documents_create_validate_extraction_action_async", run_type="uipath")
    async def create_validate_extraction_action_async(
        self,
        action_title: str,
        action_priority: ActionPriority,
        action_catalog: str,
        action_folder: str,
        storage_bucket_name: str,
        storage_bucket_directory_path: str,
        extraction_response: ExtractionResponse,
    ) -> ValidateExtractionAction:
        """Asynchronous version of the [`create_validation_action`][uipath._services.documents_service.DocumentsService.create_validate_extraction_action] method."""
        operation_id = await self._start_extraction_validation_async(
            project_id=extraction_response.project_id,
            project_type=extraction_response.project_type,
            tag=extraction_response.tag,
            document_type_id=extraction_response.document_type_id,
            action_title=action_title,
            action_priority=action_priority,
            action_catalog=action_catalog,
            action_folder=action_folder,
            storage_bucket_name=storage_bucket_name,
            storage_bucket_directory_path=storage_bucket_directory_path,
            extraction_response=extraction_response,
        )

        return await self._wait_for_create_validate_extraction_action_async(
            project_id=extraction_response.project_id,
            project_type=extraction_response.project_type,
            tag=extraction_response.tag,
            document_type_id=extraction_response.document_type_id,
            operation_id=operation_id,
        )

    @traced(name="documents_get_validate_classification_result", run_type="uipath")
    def get_validate_classification_result(
        self, validation_action: ValidateClassificationAction
    ) -> List[ClassificationResult]:
        """Get the result of a validate classification action.

        Note:
            This method will block until the validation action is completed, meaning the user has completed the validation in UiPath Action Center.

        Args:
            validation_action (ValidateClassificationAction): The validation action to get the result for, typically obtained from the [`create_validate_classification_action`][uipath._services.documents_service.DocumentsService.create_validate_classification_action] method.

        Returns:
            List[ClassificationResult]: The validated classification results.

        Examples:
            ```python
            validated_results = service.get_validate_classification_result(validate_classification_action)
            ```
        """

        def result_getter() -> Tuple[str, None, Any]:
            result = self._get_classification_validation_result(
                project_id=validation_action.project_id,
                project_type=validation_action.project_type,
                tag=validation_action.tag,
                operation_id=validation_action.operation_id,
            )
            return (result["result"]["actionStatus"], None, result["result"])

        response = self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["Unassigned", "Pending"],
            success_status="Completed",
        )
        classification_results = []
        for cr in response["validatedClassificationResults"]:
            cr["ProjectId"] = validation_action.project_id
            cr["ProjectType"] = validation_action.project_type
            cr["Tag"] = validation_action.tag
            classification_results.append(ClassificationResult.model_validate(cr))

        return classification_results

    @traced(
        name="documents_get_validate_classification_result_async", run_type="uipath"
    )
    async def get_validate_classification_result_async(
        self, validation_action: ValidateClassificationAction
    ) -> List[ClassificationResult]:
        """Asynchronous version of the [`get_validation_result`][uipath._services.documents_service.DocumentsService.get_validate_classification_result] method."""

        async def result_getter() -> Tuple[str, None, Any]:
            result = await self._get_classification_validation_result_async(
                project_id=validation_action.project_id,
                project_type=validation_action.project_type,
                tag=validation_action.tag,
                operation_id=validation_action.operation_id,
            )
            return (result["result"]["actionStatus"], None, result["result"])

        response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["Unassigned", "Pending"],
            success_status="Completed",
        )
        classification_results = []
        for cr in response["validatedClassificationResults"]:
            cr["ProjectId"] = validation_action.project_id
            cr["ProjectType"] = validation_action.project_type
            cr["Tag"] = validation_action.tag
            classification_results.append(ClassificationResult.model_validate(cr))

        return classification_results

    @traced(name="documents_get_validate_extraction_result", run_type="uipath")
    def get_validate_extraction_result(
        self, validation_action: ValidateExtractionAction
    ) -> Union[ExtractionResponse, ExtractionResponseIXP]:
        """Get the result of a validate extraction action.

        Note:
            This method will block until the validation action is completed, meaning the user has completed the validation in UiPath Action Center.

        Args:
            validation_action (ValidateClassificationAction): The validation action to get the result for, typically obtained from the [`create_validate_extraction_action`][uipath._services.documents_service.DocumentsService.create_validate_extraction_action] method.

        Returns:
            Union[ExtractionResponse, ExtractionResponseIXP]: The validated extraction response.

        Examples:
            ```python
            validated_result = service.get_validate_extraction_result(validate_extraction_action)
            ```
        """

        def result_getter() -> Tuple[str, None, Any]:
            result = self._get_extraction_validation_result(
                project_id=validation_action.project_id,
                project_type=validation_action.project_type,
                tag=validation_action.tag,
                document_type_id=validation_action.document_type_id,
                operation_id=validation_action.operation_id,
            )
            return (result["result"]["actionStatus"], None, result["result"])

        response = self._wait_for_operation(
            result_getter=result_getter,
            wait_statuses=["Unassigned", "Pending"],
            success_status="Completed",
        )
        response["extractionResult"] = response.pop("validatedExtractionResults")
        response["projectId"] = validation_action.project_id
        response["tag"] = validation_action.tag
        response["documentTypeId"] = validation_action.document_type_id
        response["projectType"] = validation_action.project_type

        if validation_action.project_type == ProjectType.IXP:
            return ExtractionResponseIXP.model_validate(response)

        return ExtractionResponse.model_validate(response)

    @traced(name="documents_get_validate_extraction_result_async", run_type="uipath")
    async def get_validate_extraction_result_async(
        self, validation_action: ValidateExtractionAction
    ) -> Union[ExtractionResponse, ExtractionResponseIXP]:
        """Asynchronous version of the [`get_validation_result`][uipath._services.documents_service.DocumentsService.get_validate_extraction_result] method."""

        async def result_getter() -> Tuple[str, None, Any]:
            result = await self._get_extraction_validation_result_async(
                project_id=validation_action.project_id,
                project_type=validation_action.project_type,
                tag=validation_action.tag,
                document_type_id=validation_action.document_type_id,
                operation_id=validation_action.operation_id,
            )
            return (result["result"]["actionStatus"], None, result["result"])

        response = await self._wait_for_operation_async(
            result_getter=result_getter,
            wait_statuses=["Unassigned", "Pending"],
            success_status="Completed",
        )
        response["extractionResult"] = response.pop("validatedExtractionResults")
        response["projectId"] = validation_action.project_id
        response["tag"] = validation_action.tag
        response["documentTypeId"] = validation_action.document_type_id
        response["projectType"] = validation_action.project_type

        if validation_action.project_type == ProjectType.IXP:
            return ExtractionResponseIXP.model_validate(response)

        return ExtractionResponse.model_validate(response)
