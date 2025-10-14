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
    ExtractionResponse,
    ProjectType,
    ValidationAction,
)


@pytest.fixture
def service(config: Config, execution_context: ExecutionContext):
    return DocumentsService(config=config, execution_context=execution_context)


@pytest.fixture
def documents_tests_data_path(tests_data_path: Path) -> Path:
    return tests_data_path / "documents_service"


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


@pytest.fixture
def validated_result(documents_tests_data_path: Path) -> dict:  # type: ignore
    with open(
        documents_tests_data_path / "validated_result.json",
        "r",
    ) as f:
        return json.load(f)


class TestDocumentsService:
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
                project_name="TestProjectIXP", tag="live", file=b"test content"
            )
        else:
            response = service.extract(
                project_name="TestProjectIXP", tag="live", file=b"test content"
            )

        # ASSERT
        expected_response = ixp_extraction_response
        expected_response["projectId"] = project_id
        expected_response["tag"] = "live"
        expected_response["documentTypeId"] = str(UUID(int=0))
        assert response.model_dump() == ixp_extraction_response

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
            response = service.extract(
                project_name="TestProjectModern",
                tag="Production",
                file=b"test content",
                project_type=ProjectType.MODERN,
                document_type_name="Invoice",
            )
        else:
            response = await service.extract_async(
                project_name="TestProjectModern",
                tag="Production",
                file=b"test content",
                project_type=ProjectType.MODERN,
                document_type_name="Invoice",
            )

        # ASSERT
        expected_response = modern_extraction_response
        expected_response["projectId"] = project_id
        expected_response["tag"] = "Production"
        expected_response["documentTypeId"] = document_type_id
        assert response.model_dump() == modern_extraction_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_modern_without_document_type_name(
        self, service: DocumentsService, mode: str
    ):
        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match="`document_type_name` must be provided when `project_type` is `ProjectType.MODERN`",
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
                )
            else:
                service._get_document_type_id(
                    project_id="dummy_project_id",
                    document_type_name="NonExistentType",
                    project_type=ProjectType.MODERN,
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_document_type_id_for_modern_without_document_type_name(
        self, service: DocumentsService, mode: str
    ):
        with pytest.raises(
            ValueError,
            match="`document_type_name` must be provided when `project_type` is `ProjectType.MODERN`",
        ):
            if mode == "async":
                await service._get_document_type_id_async(
                    project_id=str(uuid4()),
                    document_type_name=None,
                    project_type=ProjectType.MODERN,
                )
            else:
                service._get_document_type_id(
                    project_id=str(uuid4()),
                    document_type_name=None,
                    project_type=ProjectType.MODERN,
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
            match="`file` and `file_path` are mutually exclusive",
        ):
            if mode == "async":
                await service.extract_async(
                    project_name="TestProject",
                    tag="live",
                    file=b"test content",
                    file_path="path/to/file.pdf",
                )
            else:
                service.extract(
                    project_name="TestProject",
                    tag="live",
                    file=b"test content",
                    file_path="path/to/file.pdf",
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_neither_file_nor_file_path_provided(
        self,
        service: DocumentsService,
        mode: str,
    ):
        # ACT & ASSERT
        with pytest.raises(
            ValueError,
            match="Either `file` or `file_path` must be provided",
        ):
            if mode == "async":
                await service.extract_async(
                    project_name="TestProject",
                    tag="live",
                )
            else:
                service.extract(
                    project_name="TestProject",
                    tag="live",
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
                    project_name="TestProject", tag="live", file=b"test content"
                )
            else:
                service.extract(
                    project_name="TestProject", tag="live", file=b"test content"
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
                    project_name="TestProject", tag="live", file=b"test content"
                )
            else:
                service.extract(
                    project_name="TestProject", tag="live", file=b"test content"
                )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_create_validation_action(
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
        ixp_extraction_response["tag"] = tag
        ixp_extraction_response["documentTypeId"] = document_type_id

        # ACT
        if mode == "async":
            response = await service.create_validation_action_async(
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
            response = service.create_validation_action(
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
        create_validation_action_response["tag"] = tag
        create_validation_action_response["documentTypeId"] = document_type_id
        create_validation_action_response["operationId"] = operation_id
        assert response.model_dump() == create_validation_action_response

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_validation_result(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
        service: DocumentsService,
        create_validation_action_response: dict,  # type: ignore
        validated_result: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())
        document_type_id = str(UUID(int=0))

        create_validation_action_response["projectId"] = project_id
        create_validation_action_response["tag"] = "live"
        create_validation_action_response["documentTypeId"] = document_type_id
        create_validation_action_response["operationId"] = operation_id
        create_validation_action_response["actionStatus"] = "Completed"
        create_validation_action_response["validatedExtractionResults"] = (
            validated_result
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/live/document-types/{document_type_id}/validation/result/{operation_id}?api-version=1.1",
            status_code=200,
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            json={"status": "Succeeded", "result": create_validation_action_response},
        )

        # ACT
        if mode == "async":
            response = await service.get_validation_result_async(
                validation_action=ValidationAction.model_validate(
                    create_validation_action_response
                )
            )
        else:
            response = service.get_validation_result(
                validation_action=ValidationAction.model_validate(
                    create_validation_action_response
                )
            )

        # ASSERT
        assert response.model_dump() == validated_result

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
