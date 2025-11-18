import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.documents_service import DocumentsService
from uipath.models.documents import (
    ActionPriority,
    ClassificationResult,
    ExtractionResponse,
    ProjectType,
    ValidateClassificationAction,
    ValidateExtractionAction,
)


@pytest.fixture
def service(config: Config, execution_context: ExecutionContext):
    return DocumentsService(config=config, execution_context=execution_context)


@pytest.fixture
def documents_tests_data_path(tests_data_path: Path) -> Path:
    return tests_data_path / "documents_service"


@pytest.fixture
def classification_response(documents_tests_data_path: Path) -> dict:  # type: ignore
    with open(documents_tests_data_path / "classification_response.json", "r") as f:
        return json.load(f)


@pytest.fixture
def ixp_extraction_response(documents_tests_data_path: Path) -> dict:  # type: ignore
    with open(documents_tests_data_path / "ixp_extraction_response.json", "r") as f:
        return json.load(f)


@pytest.fixture
def modern_extraction_response(documents_tests_data_path: Path) -> dict:  # type: ignore
    with open(documents_tests_data_path / "modern_extraction_response.json", "r") as f:
        return json.load(f)


@pytest.fixture
def create_validation_action_response(documents_tests_data_path: Path) -> dict:  # type: ignore
    with open(
        documents_tests_data_path / "create_validation_action_response.json",
        "r",
    ) as f:
        return json.load(f)


class TestDocumentsService:
    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize(
        "tag,project_name,project_type,file,file_path,error",
        [
            (
                "Production",
                "TestProject",
                ProjectType.MODERN,
                None,
                None,
                "Exactly one of `file, file_path` must be provided",
            ),
            (
                "Production",
                "TestProject",
                ProjectType.MODERN,
                b"something",
                "something",
                "Exactly one of `file, file_path` must be provided",
            ),
            (
                "Production",
                None,
                ProjectType.PRETRAINED,
                b"something",
                None,
                "`tag` must not be provided",
            ),
            (
                None,
                "TestProject",
                ProjectType.PRETRAINED,
                b"something",
                None,
                "`project_name` must not be provided",
            ),
            (
                None,
                None,
                ProjectType.PRETRAINED,
                b"something",
                "pathto/file.pdf",
                "Exactly one of `file, file_path` must be provided",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_classify_with_invalid_parameters(
        self,
        service: DocumentsService,
        mode: str,
        tag,
        project_name,
        project_type,
        file,
        file_path,
        error,
    ):
        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match=error,
        ):
            if mode == "async":
                await service.classify_async(
                    tag=tag,
                    project_name=project_name,
                    project_type=project_type,
                    file=file,
                    file_path=file_path,
                )
            else:
                service.classify(
                    tag=tag,
                    project_name=project_name,
                    project_type=project_type,
                    file=file,
                    file_path=file_path,
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_classification_result_predefined(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        classification_response: dict,  # type: ignore
        modern_extraction_response: dict,  # type: ignore
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        document_id = str(uuid4())
        document_type_id = str(uuid4())
        operation_id = str(uuid4())
        classification_response["classificationResults"][0]["ProjectId"] = project_id
        classification_response["classificationResults"][0]["ProjectType"] = (
            ProjectType.PRETRAINED.value
        )
        classification_response["classificationResults"][0]["Tag"] = None
        classification_response["classificationResults"][0]["DocumentId"] = document_id
        classification_response["classificationResults"][0]["DocumentTypeId"] = (
            document_type_id
        )
        classification_result = ClassificationResult.model_validate(
            classification_response["classificationResults"][0]
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": modern_extraction_response},
        )

        # ACT
        if mode == "async":
            response = await service.extract_async(
                classification_result=classification_result
            )
        else:
            response = service.extract(classification_result=classification_result)

        # ASSERT
        modern_extraction_response["projectId"] = project_id
        modern_extraction_response["projectType"] = ProjectType.PRETRAINED
        modern_extraction_response["tag"] = None
        modern_extraction_response["documentTypeId"] = document_type_id
        assert response.model_dump() == modern_extraction_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_classification_result_modern(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        classification_response: dict,  # type: ignore
        modern_extraction_response: dict,  # type: ignore
    ):
        # ARRANGE
        project_id = str(uuid4())
        document_id = str(uuid4())
        document_type_id = str(uuid4())
        classification_response["classificationResults"][0]["ProjectId"] = project_id
        classification_response["classificationResults"][0]["ProjectType"] = (
            ProjectType.MODERN.value
        )
        classification_response["classificationResults"][0]["Tag"] = "Production"
        classification_response["classificationResults"][0]["DocumentId"] = document_id
        classification_response["classificationResults"][0]["DocumentTypeId"] = (
            document_type_id
        )
        classification_result = ClassificationResult.model_validate(
            classification_response["classificationResults"][0]
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "tags": [
                    {"name": "Staging"},
                    {"name": "Production"},
                ]
            },
        )
        operation_id = str(uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/document-types/{document_type_id}/extraction/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/document-types/{document_type_id}/extraction/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": modern_extraction_response},
        )

        # ACT
        if mode == "async":
            response = await service.extract_async(
                classification_result=classification_result
            )
        else:
            response = service.extract(classification_result=classification_result)

        # ASSERT
        modern_extraction_response["projectId"] = project_id
        modern_extraction_response["projectType"] = ProjectType.MODERN
        modern_extraction_response["tag"] = "Production"
        modern_extraction_response["documentTypeId"] = document_type_id
        assert response.model_dump() == modern_extraction_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_classify_predefined(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        classification_response: dict,  # type: ignore
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        document_id = str(uuid4())

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_files={"File": b"test content"},
            json={"documentId": document_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/result/{document_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": {}},
        )

        operation_id = str(uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/classifiers/ml-classification/classification/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/classifiers/ml-classification/classification/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": classification_response},
        )

        # ACT
        if mode == "async":
            response = await service.classify_async(
                project_type=ProjectType.PRETRAINED,
                file=b"test content",
            )
        else:
            response = service.classify(
                project_type=ProjectType.PRETRAINED,
                file=b"test content",
            )

        # ASSERT
        classification_response["classificationResults"][0]["ProjectId"] = project_id
        classification_response["classificationResults"][0]["ProjectType"] = (
            ProjectType.PRETRAINED.value
        )
        classification_response["classificationResults"][0]["Tag"] = None
        assert (
            response[0].model_dump()
            == classification_response["classificationResults"][0]
        )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_classify_modern(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        classification_response: dict,  # type: ignore
    ):
        # ARRANGE
        project_id = str(uuid4())
        document_id = str(uuid4())

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects?api-version=1.1&type=Modern",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "projects": [
                    {"id": str(uuid4()), "name": "OtherProject"},
                    {"id": project_id, "name": "TestProject"},
                    {"id": str(uuid4()), "name": "AnotherProject"},
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "tags": [
                    {"name": "Production"},
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_files={"File": b"test content"},
            json={"documentId": document_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/result/{document_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": {}},
        )

        operation_id = str(uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/classification/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/classification/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": classification_response},
        )

        # ACT
        if mode == "async":
            response = await service.classify_async(
                tag="Production",
                project_name="TestProject",
                project_type=ProjectType.MODERN,
                file=b"test content",
            )
        else:
            response = service.classify(
                tag="Production",
                project_name="TestProject",
                project_type=ProjectType.MODERN,
                file=b"test content",
            )

        # ASSERT
        classification_response["classificationResults"][0]["ProjectId"] = project_id
        classification_response["classificationResults"][0]["ProjectType"] = (
            ProjectType.MODERN.value
        )
        classification_response["classificationResults"][0]["Tag"] = "Production"
        assert (
            response[0].model_dump()
            == classification_response["classificationResults"][0]
        )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "tag,project_name,file,file_path,classification_result,project_type,document_type_name, error",
        [
            (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "`classification_result` must be provided",
            ),
            (
                "live",
                "TestProject",
                None,
                None,
                None,
                None,
                None,
                "`classification_result` must be provided",
            ),
            (
                "live",
                "TestProject",
                None,
                None,
                None,
                ProjectType.IXP,
                None,
                "`classification_result` must be provided",
            ),
            (
                "live",
                "TestProject",
                b"something",
                None,
                None,
                ProjectType.MODERN,
                None,
                "`document_type_name` must be provided",
            ),
            (
                "live",
                "TestProject",
                b"something",
                None,
                "dummy classification result",
                ProjectType.MODERN,
                "dummy doctype",
                "`classification_result` must not be provided",
            ),
            (
                None,
                "TestProject",
                b"something",
                None,
                None,
                ProjectType.MODERN,
                "dummy doctype",
                "`tag` must be provided",
            ),
            (
                "live",
                "TestProject",
                b"something",
                "path/to/file.pdf",
                None,
                ProjectType.MODERN,
                "dummy doctype",
                "Exactly one of `file, file_path` must be provided",
            ),
            (
                "live",
                None,
                b"something",
                None,
                None,
                ProjectType.PRETRAINED,
                "dummy doctype",
                "`tag` must not be provided",
            ),
        ],
    )
    async def test_extract_with_invalid_parameters(
        self,
        service: DocumentsService,
        mode: str,
        tag,
        project_name,
        file,
        file_path,
        classification_result,
        project_type,
        document_type_name,
        error,
    ):
        # ACT & ASSERT
        with pytest.raises(ValueError, match=error):
            if mode == "async":
                await service.extract_async(
                    tag=tag,
                    project_name=project_name,
                    project_type=project_type,
                    file=file,
                    file_path=file_path,
                    classification_result=classification_result,
                    document_type_name=document_type_name,
                )
            else:
                service.extract(
                    tag=tag,
                    project_name=project_name,
                    project_type=project_type,
                    file=file,
                    file_path=file_path,
                    classification_result=classification_result,
                    document_type_name=document_type_name,
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_ixp(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        ixp_extraction_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        document_id = str(uuid4())
        operation_id = str(uuid4())

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects?api-version=1.1&type=IXP",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "projects": [
                    {"id": str(uuid4()), "name": "OtherProject"},
                    {"id": project_id, "name": "TestProjectIXP"},
                    {"id": str(uuid4()), "name": "AnotherProject"},
                ]
            },
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "tags": [
                    {"name": "draft"},
                    {"name": "live"},
                    {"name": "production"},
                ]
            },
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_files={"File": b"test content"},
            json={"documentId": document_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/result/{document_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": {}},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/live/document-types/{UUID(int=0)}/extraction/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/live/document-types/{UUID(int=0)}/extraction/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "NotStarted", "result": ixp_extraction_response},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/live/document-types/{UUID(int=0)}/extraction/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Running", "result": ixp_extraction_response},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/live/document-types/{UUID(int=0)}/extraction/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": ixp_extraction_response},
        )

        # ACT
        if mode == "async":
            response = await service.extract_async(
                project_name="TestProjectIXP",
                project_type=ProjectType.IXP,
                tag="live",
                file=b"test content",
            )
        else:
            response = service.extract(
                project_name="TestProjectIXP",
                project_type=ProjectType.IXP,
                tag="live",
                file=b"test content",
            )

        # ASSERT
        expected_response = ixp_extraction_response
        expected_response["projectId"] = project_id
        expected_response["projectType"] = ProjectType.IXP.value
        expected_response["tag"] = "live"
        expected_response["documentTypeId"] = str(UUID(int=0))
        assert response.model_dump() == expected_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_predefined(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        modern_extraction_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        document_id = str(uuid4())
        document_type_id = str(uuid4())
        operation_id = str(uuid4())

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_files={"File": b"test content"},
            json={"documentId": document_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/result/{document_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": {}},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/document-types?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "documentTypes": [
                    {"id": str(uuid4()), "name": "Receipt"},
                    {"id": document_type_id, "name": "Invoice"},
                    {"id": str(uuid4()), "name": "Contract"},
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )

        statuses = ["NotStarted", "Running", "Succeeded"]
        for status in statuses:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/extraction/result/{operation_id}?api-version=1.1",
                status_code=200,
                match_headers={
                    "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
                },
                json={"status": status, "result": modern_extraction_response},
            )

        # ACT
        if mode == "async":
            response = await service.extract_async(
                project_type=ProjectType.PRETRAINED,
                file=b"test content",
                document_type_name="Invoice",
            )
        else:
            response = service.extract(
                project_type=ProjectType.PRETRAINED,
                file=b"test content",
                document_type_name="Invoice",
            )

        # ASSERT
        expected_response = modern_extraction_response
        expected_response["projectId"] = project_id
        expected_response["projectType"] = ProjectType.PRETRAINED.value
        expected_response["tag"] = None
        expected_response["documentTypeId"] = document_type_id
        assert response.model_dump() == expected_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_modern(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        modern_extraction_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        document_type_id = str(uuid4())
        document_id = str(uuid4())
        operation_id = str(uuid4())

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects?api-version=1.1&type=Modern",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "projects": [
                    {"id": str(uuid4()), "name": "OtherProject"},
                    {"id": project_id, "name": "TestProjectModern"},
                    {"id": str(uuid4()), "name": "AnotherProject"},
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "tags": [
                    {"name": "Development"},
                    {"name": "Staging"},
                    {"name": "Production"},
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_files={"File": b"test content"},
            json={"documentId": document_id},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/digitization/result/{document_id}?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={"status": "Succeeded", "result": {}},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/document-types?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            json={
                "documentTypes": [
                    {"id": str(uuid4()), "name": "Receipt"},
                    {"id": document_type_id, "name": "Invoice"},
                    {"id": str(uuid4()), "name": "Contract"},
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/document-types/{document_type_id}/extraction/start?api-version=1.1",
            status_code=200,
            match_headers={
                "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            },
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )

        statuses = ["NotStarted", "Running", "Succeeded"]
        for status in statuses:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/document-types/{document_type_id}/extraction/result/{operation_id}?api-version=1.1",
                status_code=200,
                match_headers={
                    "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
                },
                json={"status": status, "result": modern_extraction_response},
            )

        # ACT
        if mode == "async":
            response = await service.extract_async(
                project_name="TestProjectModern",
                tag="Production",
                file=b"test content",
                project_type=ProjectType.MODERN,
                document_type_name="Invoice",
            )
        else:
            response = service.extract(
                project_name="TestProjectModern",
                tag="Production",
                file=b"test content",
                project_type=ProjectType.MODERN,
                document_type_name="Invoice",
            )

        # ASSERT
        expected_response = modern_extraction_response
        expected_response["projectId"] = project_id
        expected_response["projectType"] = ProjectType.MODERN.value
        expected_response["tag"] = "Production"
        expected_response["documentTypeId"] = document_type_id
        assert response.model_dump() == expected_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_modern_without_document_type_name(
        self, service: DocumentsService, mode: str
    ):
        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match="`document_type_name` must be provided",
        ):
            if mode == "async":
                await service.extract_async(
                    project_name="TestProjectModern",
                    tag="Production",
                    file=b"test content",
                    project_type=ProjectType.MODERN,
                )
            else:
                service.extract(
                    project_name="TestProjectModern",
                    tag="Production",
                    file=b"test content",
                    project_type=ProjectType.MODERN,
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_document_type_id_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
    ):
        # ARRANGE
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/dummy_project_id/document-types?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={
                "documentTypes": [
                    {"id": str(uuid4()), "name": "Receipt"},
                    {"id": str(uuid4()), "name": "Invoice"},
                    {"id": str(uuid4()), "name": "Contract"},
                ]
            },
        )

        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match="Document type 'NonExistentType' not found.",
        ):
            if mode == "async":
                await service._get_document_type_id_async(
                    project_id="dummy_project_id",
                    document_type_name="NonExistentType",
                    project_type=ProjectType.MODERN,
                    classification_result=None,
                )
            else:
                service._get_document_type_id(
                    project_id="dummy_project_id",
                    document_type_name="NonExistentType",
                    project_type=ProjectType.MODERN,
                    classification_result=None,
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_both_file_and_file_path_provided(
        self,
        service: DocumentsService,
        mode: str,
    ):
        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match="Exactly one of `file, file_path` must be provided",
        ):
            if mode == "async":
                await service.extract_async(
                    project_name="TestProject",
                    project_type=ProjectType.IXP,
                    tag="live",
                    file=b"test content",
                    file_path="path/to/file.pdf",
                )
            else:
                service.extract(
                    project_name="TestProject",
                    project_type=ProjectType.IXP,
                    tag="live",
                    file=b"test content",
                    file_path="path/to/file.pdf",
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_wrong_project_name(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
    ):
        # ARRANGE
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects?api-version=1.1&type=IXP",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={
                "projects": [
                    {"id": str(uuid4()), "name": "OtherProject"},
                    {"id": str(uuid4()), "name": "YetAnotherProject"},
                    {"id": str(uuid4()), "name": "AnotherProject"},
                ]
            },
        )

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Project 'TestProject' not found."):
            if mode == "async":
                await service.extract_async(
                    project_name="TestProject",
                    project_type=ProjectType.IXP,
                    tag="live",
                    file=b"test content",
                )
            else:
                service.extract(
                    project_name="TestProject",
                    project_type=ProjectType.IXP,
                    tag="live",
                    file=b"test content",
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_wrong_tag(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects?api-version=1.1&type=IXP",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={
                "projects": [
                    {"id": str(uuid4()), "name": "OtherProject"},
                    {"id": project_id, "name": "TestProject"},
                    {"id": str(uuid4()), "name": "AnotherProject"},
                ]
            },
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"tags": [{"name": "staging"}]},
        )

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Tag 'live' not found."):
            if mode == "async":
                await service.extract_async(
                    project_name="TestProject",
                    project_type=ProjectType.IXP,
                    tag="live",
                    file=b"test content",
                )
            else:
                service.extract(
                    project_name="TestProject",
                    project_type=ProjectType.IXP,
                    tag="live",
                    file=b"test content",
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_create_validate_classification_action_pretrained(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        classification_response: dict,  # type: ignore
        create_validation_action_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        operation_id = str(uuid4())
        tag = None
        action_title = "TestAction"
        action_priority = ActionPriority.LOW
        action_catalog = "TestCatalog"
        action_folder = "TestFolder"
        storage_bucket_name = "TestBucket"
        storage_bucket_directory_path = "Test/Directory/Path"

        classification_result = classification_response["classificationResults"][0]
        classification_result["ProjectId"] = project_id
        classification_result["ProjectType"] = ProjectType.PRETRAINED.value
        classification_result["Tag"] = tag
        classification_result = ClassificationResult.model_validate(
            classification_result
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/start?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            match_json={
                "actionTitle": action_title,
                "actionPriority": action_priority,
                "actionCatalog": action_catalog,
                "actionFolder": action_folder,
                "storageBucketName": storage_bucket_name,
                "storageBucketDirectoryPath": storage_bucket_directory_path,
                "classificationResults": [
                    classification_result.model_dump(),
                ],
                "documentId": classification_result.document_id,
            },
            json={"operationId": operation_id},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        # ACT
        if mode == "async":
            response = await service.create_validate_classification_action_async(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                classification_results=[classification_result],
            )
        else:
            response = service.create_validate_classification_action(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                classification_results=[classification_result],
            )

        # ASSERT
        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.PRETRAINED.value
        create_validation_action_response["tag"] = tag
        create_validation_action_response["operationId"] = operation_id
        assert response.model_dump() == create_validation_action_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_create_validate_classification_action_modern(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        classification_response: dict,  # type: ignore
        create_validation_action_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())
        tag = "Production"
        action_title = "TestAction"
        action_priority = ActionPriority.MEDIUM
        action_catalog = "TestCatalog"
        action_folder = "TestFolder"
        storage_bucket_name = "TestBucket"
        storage_bucket_directory_path = "Test/Directory/Path"

        classification_result = classification_response["classificationResults"][0]
        classification_result["ProjectId"] = project_id
        classification_result["ProjectType"] = ProjectType.MODERN.value
        classification_result["Tag"] = tag
        classification_result = ClassificationResult.model_validate(
            classification_result
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/classifiers/validation/start?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            match_json={
                "actionTitle": action_title,
                "actionPriority": action_priority,
                "actionCatalog": action_catalog,
                "actionFolder": action_folder,
                "storageBucketName": storage_bucket_name,
                "storageBucketDirectoryPath": storage_bucket_directory_path,
                "classificationResults": [
                    classification_result.model_dump(),
                ],
                "documentId": classification_result.document_id,
            },
            json={"operationId": operation_id},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/classifiers/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        # ACT
        if mode == "async":
            response = await service.create_validate_classification_action_async(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                classification_results=[classification_result],
            )
        else:
            response = service.create_validate_classification_action(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                classification_results=[classification_result],
            )
        # ASSERT
        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.MODERN.value
        create_validation_action_response["tag"] = tag
        create_validation_action_response["operationId"] = operation_id
        assert response.model_dump() == create_validation_action_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_create_validate_classification_action_with_empty_classification_results(
        self,
        service: DocumentsService,
        mode: str,
    ):
        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match="`classification_results` must not be empty",
        ):
            if mode == "async":
                await service.create_validate_classification_action_async(
                    action_title="TestAction",
                    action_priority=ActionPriority.MEDIUM,
                    action_catalog="TestCatalog",
                    action_folder="TestFolder",
                    storage_bucket_name="TestBucket",
                    storage_bucket_directory_path="Test/Directory/Path",
                    classification_results=[],
                )
            else:
                service.create_validate_classification_action(
                    action_title="TestAction",
                    action_priority=ActionPriority.MEDIUM,
                    action_catalog="TestCatalog",
                    action_folder="TestFolder",
                    storage_bucket_name="TestBucket",
                    storage_bucket_directory_path="Test/Directory/Path",
                    classification_results=[],
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_create_validate_extraction_action_pretrained(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        modern_extraction_response: dict,  # type: ignore
        create_validation_action_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        operation_id = str(uuid4())
        document_type_id = str(UUID(int=0))
        tag = None
        action_title = "TestAction"
        action_priority = ActionPriority.MEDIUM
        action_catalog = "TestCatalog"
        action_folder = "TestFolder"
        storage_bucket_name = "TestBucket"
        storage_bucket_directory_path = "Test/Directory/Path"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/start?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            match_json={
                "extractionResult": modern_extraction_response["extractionResult"],
                "documentId": modern_extraction_response["extractionResult"][
                    "DocumentId"
                ],
                "actionTitle": action_title,
                "actionPriority": action_priority,
                "actionCatalog": action_catalog,
                "actionFolder": action_folder,
                "storageBucketName": storage_bucket_name,
                "allowChangeOfDocumentType": True,
                "storageBucketDirectoryPath": storage_bucket_directory_path,
            },
            json={"operationId": operation_id},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        modern_extraction_response["projectId"] = project_id
        modern_extraction_response["projectType"] = ProjectType.PRETRAINED.value
        modern_extraction_response["tag"] = tag
        modern_extraction_response["documentTypeId"] = document_type_id

        # ACT
        if mode == "async":
            response = await service.create_validate_extraction_action_async(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                extraction_response=ExtractionResponse.model_validate(
                    modern_extraction_response
                ),
            )
        else:
            response = service.create_validate_extraction_action(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                extraction_response=ExtractionResponse.model_validate(
                    modern_extraction_response
                ),
            )

        # ASSERT
        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.PRETRAINED.value
        create_validation_action_response["tag"] = tag
        create_validation_action_response["documentTypeId"] = document_type_id
        create_validation_action_response["operationId"] = operation_id
        assert response.model_dump() == create_validation_action_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_create_validate_extraction_action_ixp(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService,
        base_url: str,
        org: str,
        tenant: str,
        ixp_extraction_response: dict,  # type: ignore
        create_validation_action_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())
        document_type_id = str(UUID(int=0))
        tag = "live"
        action_title = "TestAction"
        action_priority = ActionPriority.HIGH
        action_catalog = "TestCatalog"
        action_folder = "TestFolder"
        storage_bucket_name = "TestBucket"
        storage_bucket_directory_path = "Test/Directory/Path"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/start?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            match_json={
                "extractionResult": ixp_extraction_response["extractionResult"],
                "documentId": ixp_extraction_response["extractionResult"]["DocumentId"],
                "actionTitle": action_title,
                "actionPriority": action_priority,
                "actionCatalog": action_catalog,
                "actionFolder": action_folder,
                "storageBucketName": storage_bucket_name,
                "allowChangeOfDocumentType": True,
                "storageBucketDirectoryPath": storage_bucket_directory_path,
            },
            json={"operationId": operation_id},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "NotStarted"},
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Running"},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/document-types/{UUID(int=0)}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        ixp_extraction_response["projectId"] = project_id
        ixp_extraction_response["projectType"] = ProjectType.IXP.value
        ixp_extraction_response["tag"] = tag
        ixp_extraction_response["documentTypeId"] = document_type_id

        # ACT
        if mode == "async":
            response = await service.create_validate_extraction_action_async(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                extraction_response=ExtractionResponse.model_validate(
                    ixp_extraction_response
                ),
            )
        else:
            response = service.create_validate_extraction_action(
                action_title=action_title,
                action_priority=action_priority,
                action_catalog=action_catalog,
                action_folder=action_folder,
                storage_bucket_name=storage_bucket_name,
                storage_bucket_directory_path=storage_bucket_directory_path,
                extraction_response=ExtractionResponse.model_validate(
                    ixp_extraction_response
                ),
            )

        # ASSERT
        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.IXP.value
        create_validation_action_response["tag"] = tag
        create_validation_action_response["documentTypeId"] = document_type_id
        create_validation_action_response["operationId"] = operation_id
        assert response.model_dump() == create_validation_action_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_validate_classification_result_pretrained(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
        service: DocumentsService,
        create_validation_action_response: dict,  # type: ignore
        classification_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        operation_id = str(uuid4())

        create_validation_action_response["actionStatus"] = "Completed"
        create_validation_action_response["validatedClassificationResults"] = (
            classification_response["classificationResults"]
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/classifiers/ml-classification/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.PRETRAINED.value
        create_validation_action_response["tag"] = None
        create_validation_action_response["operationId"] = operation_id

        # ACT
        if mode == "async":
            results = await service.get_validate_classification_result_async(
                validation_action=ValidateClassificationAction.model_validate(
                    create_validation_action_response
                )
            )
        else:
            results = service.get_validate_classification_result(
                validation_action=ValidateClassificationAction.model_validate(
                    create_validation_action_response
                )
            )

        # ASSERT
        classification_response["classificationResults"][0]["ProjectId"] = project_id
        classification_response["classificationResults"][0]["ProjectType"] = (
            ProjectType.PRETRAINED.value
        )
        classification_response["classificationResults"][0]["Tag"] = None
        assert (
            results[0].model_dump()
            == classification_response["classificationResults"][0]
        )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_validate_classification_result_modern(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
        service: DocumentsService,
        create_validation_action_response: dict,  # type: ignore
        classification_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())

        create_validation_action_response["actionStatus"] = "Completed"
        create_validation_action_response["validatedClassificationResults"] = (
            classification_response["classificationResults"]
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/Production/classifiers/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.MODERN.value
        create_validation_action_response["tag"] = "Production"
        create_validation_action_response["operationId"] = operation_id

        # ACT
        if mode == "async":
            results = await service.get_validate_classification_result_async(
                validation_action=ValidateClassificationAction.model_validate(
                    create_validation_action_response
                )
            )
        else:
            results = service.get_validate_classification_result(
                validation_action=ValidateClassificationAction.model_validate(
                    create_validation_action_response
                )
            )

        # ASSERT
        classification_response["classificationResults"][0]["ProjectId"] = project_id
        classification_response["classificationResults"][0]["ProjectType"] = (
            ProjectType.MODERN.value
        )
        classification_response["classificationResults"][0]["Tag"] = "Production"
        assert (
            results[0].model_dump()
            == classification_response["classificationResults"][0]
        )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_validate_extraction_result_pretrained(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
        service: DocumentsService,
        create_validation_action_response: dict,  # type: ignore
        modern_extraction_response: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(UUID(int=0))
        operation_id = str(uuid4())
        document_type_id = str(UUID(int=0))

        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = ProjectType.PRETRAINED.value
        create_validation_action_response["tag"] = None
        create_validation_action_response["documentTypeId"] = document_type_id
        create_validation_action_response["operationId"] = operation_id
        create_validation_action_response["actionStatus"] = "Completed"
        create_validation_action_response["validatedExtractionResults"] = (
            modern_extraction_response["extractionResult"]
        )
        create_validation_action_response["dataProjection"] = (
            modern_extraction_response.get("dataProjection", None)
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/extractors/{document_type_id}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        # ACT
        if mode == "async":
            response = await service.get_validate_extraction_result_async(
                validation_action=ValidateExtractionAction.model_validate(
                    create_validation_action_response
                )
            )
        else:
            response = service.get_validate_extraction_result(
                validation_action=ValidateExtractionAction.model_validate(
                    create_validation_action_response
                )
            )

        # ASSERT
        modern_extraction_response["projectId"] = project_id
        modern_extraction_response["projectType"] = ProjectType.PRETRAINED.value
        modern_extraction_response["tag"] = None
        modern_extraction_response["documentTypeId"] = document_type_id
        assert response.model_dump() == modern_extraction_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize(
        "project_type,tag,extraction_response_fixture",
        [
            (ProjectType.MODERN, "Production", "modern_extraction_response"),
            (ProjectType.IXP, "live", "ixp_extraction_response"),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_validate_extraction_result(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
        service: DocumentsService,
        create_validation_action_response: dict,  # type: ignore
        modern_extraction_response: dict,  # type: ignore
        ixp_extraction_response: dict,  # type: ignore
        mode: str,
        project_type: ProjectType,
        tag: str,
        extraction_response_fixture: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())
        document_type_id = str(UUID(int=0))

        # Select the appropriate extraction response based on the fixture name
        extraction_response = (
            modern_extraction_response
            if extraction_response_fixture == "modern_extraction_response"
            else ixp_extraction_response
        )

        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["projectType"] = project_type.value
        create_validation_action_response["tag"] = tag
        create_validation_action_response["documentTypeId"] = document_type_id
        create_validation_action_response["operationId"] = operation_id
        create_validation_action_response["actionStatus"] = "Completed"
        create_validation_action_response["validatedExtractionResults"] = (
            extraction_response["extractionResult"]
        )
        create_validation_action_response["dataProjection"] = extraction_response.get(
            "dataProjection", None
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/{tag}/document-types/{document_type_id}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        # ACT
        if mode == "async":
            response = await service.get_validate_extraction_result_async(
                validation_action=ValidateExtractionAction.model_validate(
                    create_validation_action_response
                )
            )
        else:
            response = service.get_validate_extraction_result(
                validation_action=ValidateExtractionAction.model_validate(
                    create_validation_action_response
                )
            )

        # ASSERT
        extraction_response["projectId"] = project_id
        extraction_response["projectType"] = project_type
        extraction_response["tag"] = tag
        extraction_response["documentTypeId"] = document_type_id
        assert response.model_dump() == extraction_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    @patch("uipath._services.documents_service.time")
    async def test_wait_for_operation_timeout(
        self,
        mock_time: Mock,
        service: DocumentsService,
        mode: str,
    ):
        # ARRANGE
        mock_time.monotonic.side_effect = [0, 10, 30, 60, 200, 280, 310, 350]

        def mock_result_getter():
            return "Running", None, None

        async def mock_result_getter_async():
            return "Running", None, None

        # ACT & ASSERT
        with pytest.raises(TimeoutError, match="Operation timed out."):
            if mode == "async":
                await service._wait_for_operation_async(
                    result_getter=mock_result_getter_async,
                    wait_statuses=["NotStarted", "Running"],
                    success_status="Succeeded",
                )
            else:
                service._wait_for_operation(
                    result_getter=mock_result_getter,
                    wait_statuses=["NotStarted", "Running"],
                    success_status="Succeeded",
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_wait_for_operation_failed(
        self,
        service: DocumentsService,
        mode: str,
    ):
        # ARRANGE

        def mock_result_getter():
            return "Failed", "Dummy error", None

        async def mock_result_getter_async():
            return "Failed", "Dummy error", None

        # ACT & ASSERT
        with pytest.raises(
            Exception, match="Operation failed with status: Failed, error: Dummy error"
        ):
            if mode == "async":
                await service._wait_for_operation_async(
                    result_getter=mock_result_getter_async,
                    wait_statuses=["NotStarted", "Running"],
                    success_status="Succeeded",
                )
            else:
                service._wait_for_operation(
                    result_getter=mock_result_getter,
                    wait_statuses=["NotStarted", "Running"],
                    success_status="Succeeded",
                )
