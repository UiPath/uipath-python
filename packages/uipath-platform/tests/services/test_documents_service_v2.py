import json
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPath, UiPathApiConfig, UiPathExecutionContext
from uipath.platform.documents import (
    DocumentsServiceV2,
    FieldType,
    ModelExtractionResponse,
    ProjectType,
    StartModelExtractionResponse,
    ValidateExtractionAction,
)
from uipath.platform.errors import (
    OperationFailedException,
    OperationNotCompleteException,
)
from uipath.platform.orchestrator import FolderService

# Responses only DU Framework API v2 returns. Behavior both versions share is
# tested against both services in test_documents_service.py.


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> DocumentsServiceV2:
    return DocumentsServiceV2(
        config=config,
        execution_context=execution_context,
        polling_interval=0.001,  # 1ms for fast tests
        polling_timeout=10,  # 10 seconds for tests
    )


# Document Processing contract payloads are PascalCase in every API version.
CONTRACT_PAYLOAD_KEYS = {
    "extractionResult",
    "classificationResults",
    "validatedExtractionResults",
    "validatedClassificationResults",
}


def to_pascal_case(value: Any) -> Any:
    """Mimics DU Framework v2 responses for orgs with PascalCase responses enabled."""
    if isinstance(value, list):
        return [to_pascal_case(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key[:1].upper() + key[1:]: (
            item if key in CONTRACT_PAYLOAD_KEYS else to_pascal_case(item)
        )
        for key, item in value.items()
    }


@pytest.fixture
def ixp_extraction_response_v2(documents_tests_data_path: Path) -> dict:  # type: ignore
    with open(documents_tests_data_path / "ixp_extraction_response_v2.json", "r") as f:
        return json.load(f)


class TestDocumentsServiceV2:
    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_classify_modern_with_tag_pascal_case_responses(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        classification_response: dict,  # type: ignore
    ):
        # ARRANGE
        project_id = str(uuid4())
        document_id = str(uuid4())
        operation_id = str(uuid4())
        base = f"{base_url}{org}{tenant}/du_/api/framework/projects"

        httpx_mock.add_response(
            url=f"{base}?api-version=2.0&type=Modern",
            json=to_pascal_case(
                {"projects": [{"id": project_id, "name": "TestProject"}]}
            ),
        )
        httpx_mock.add_response(
            url=f"{base}/{project_id}/tags?api-version=2.0",
            json=to_pascal_case({"tags": [{"name": "Production"}]}),
        )
        httpx_mock.add_response(
            url=f"{base}/{project_id}/digitization/start?api-version=2.0",
            json=to_pascal_case({"documentId": document_id}),
        )
        httpx_mock.add_response(
            url=f"{base}/{project_id}/digitization/result/{document_id}?api-version=2.0",
            json=to_pascal_case(
                {"status": "Succeeded", "result": {"documentObjectModel": {}}}
            ),
        )
        httpx_mock.add_response(
            url=f"{base}/{project_id}/tags/Production/classification/start?api-version=2.0",
            match_json={"documentId": document_id},
            json=to_pascal_case({"operationId": operation_id}),
        )
        httpx_mock.add_response(
            url=f"{base}/{project_id}/tags/Production/classification/result/{operation_id}?api-version=2.0",
            json=to_pascal_case(
                {"status": "Succeeded", "result": classification_response}
            ),
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
        expected = classification_response["classificationResults"][0]
        expected["ProjectId"] = project_id
        expected["ProjectType"] = ProjectType.MODERN.value
        expected["ClassifierId"] = None
        expected["Tag"] = "Production"
        assert response[0].model_dump() == expected

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize("pascal_case", [False, True])
    @pytest.mark.asyncio
    async def test_retrieve_ixp_extraction_result_with_field_groups(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        pascal_case: bool,
        ixp_extraction_response_v2: dict,  # type: ignore
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())
        body = {"status": "Succeeded", "result": ixp_extraction_response_v2}

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags/live/document-types/{UUID(int=0)}/extraction/result/{operation_id}?api-version=2.0",
            json=to_pascal_case(body) if pascal_case else body,
        )

        # ACT
        if mode == "async":
            response = await service.retrieve_ixp_extraction_result_async(
                project_id=project_id,
                tag="live",
                operation_id=operation_id,
            )
        else:
            response = service.retrieve_ixp_extraction_result(
                project_id=project_id,
                tag="live",
                operation_id=operation_id,
            )

        # ASSERT
        assert (
            response.extraction_result.model_dump()
            == (ixp_extraction_response_v2["extractionResult"])
        )
        [field_group] = response.data_projection
        assert field_group.field_group_name == "Details"
        total, due_date = field_group.field_values
        assert total.id == "Default.Details.Total"
        assert total.type == FieldType.MONETARY_QUANTITY
        assert total.value == "66.79 RON"
        assert due_date.type == FieldType.DATE
        assert due_date.value is None

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_get_validate_extraction_result_pascal_case_responses(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
        service: DocumentsServiceV2,
        create_validation_action_response: dict,  # type: ignore
        ixp_extraction_response_v2: dict,  # type: ignore
        mode: str,
    ):
        # ARRANGE
        project_id = str(uuid4())
        operation_id = str(uuid4())
        document_type_id = str(UUID(int=0))
        url = f"{base_url}{org}{tenant}/du_/api/framework/projects/{project_id}/tags/live/document-types/{document_type_id}/validation/result/{operation_id}?api-version=2.0"

        validation_action = ValidateExtractionAction(
            action_data=create_validation_action_response["actionData"],
            action_status="Unassigned",
            project_id=project_id,
            project_type=ProjectType.IXP,
            tag="live",
            operation_id=operation_id,
            extractor_id=None,
            document_type_id=document_type_id,
        )
        completed = {
            **create_validation_action_response,
            "actionStatus": "Completed",
            "validatedExtractionResults": ixp_extraction_response_v2[
                "extractionResult"
            ],
            "dataProjection": ixp_extraction_response_v2["dataProjection"],
        }

        httpx_mock.add_response(
            url=url,
            json=to_pascal_case(
                {"status": "Succeeded", "result": create_validation_action_response}
            ),
        )
        httpx_mock.add_response(
            url=url,
            json=to_pascal_case({"status": "Succeeded", "result": completed}),
        )

        # ACT
        if mode == "async":
            response = await service.get_validate_extraction_result_async(
                validation_action=validation_action
            )
        else:
            response = service.get_validate_extraction_result(
                validation_action=validation_action
            )

        # ASSERT
        assert (
            response.extraction_result.model_dump()
            == (ixp_extraction_response_v2["extractionResult"])
        )
        assert response.data_projection[0].field_values[0].id == (
            "Default.Details.Total"
        )
        assert response.tag == "live"


FOLDER_KEY = str(uuid4())


@pytest.fixture
def make_service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., DocumentsServiceV2]:
    """Builds a service after the test sets the job folder environment."""
    monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
    monkeypatch.delenv("UIPATH_FOLDER_PATH", raising=False)

    def make(
        polling_timeout: float = 10, with_folders_service: bool = True
    ) -> DocumentsServiceV2:
        return DocumentsServiceV2(
            config=config,
            execution_context=execution_context,
            polling_interval=0.001,
            polling_timeout=polling_timeout,
            folders_service=(
                FolderService(config=config, execution_context=execution_context)
                if with_folders_service
                else None
            ),
        )

    return make


@pytest.fixture
def model_extraction_result(ixp_extraction_response_v2: dict) -> dict:  # type: ignore
    return {"extractionResult": ixp_extraction_response_v2["extractionResult"]}


async def call(
    mode: str, service: DocumentsServiceV2, method: str, **kwargs: Any
) -> Any:
    """Calls `method`, or its `_async` twin in async mode."""
    if mode == "async":
        return await getattr(service, f"{method}_async")(**kwargs)
    return getattr(service, method)(**kwargs)


class TestDocumentsServiceV2FolderModels:
    @pytest.fixture
    def models_url(self, base_url: str, org: str, tenant: str) -> str:
        return f"{base_url}{org}{tenant}/du_/api/framework/models"

    def mock_start(
        self,
        httpx_mock: HTTPXMock,
        models_url: str,
        model_route: str,
        folder_key: str,
        document_id: str,
        operation_id: str,
        pascal_case: bool = False,
    ) -> None:
        def body(value: dict) -> dict:  # type: ignore
            return to_pascal_case(value) if pascal_case else value

        headers = {
            "X-UiPath-Internal-ConsumptionSourceType": "CodedAgents",
            "x-uipath-folderkey": folder_key,
        }
        httpx_mock.add_response(
            method="POST",
            url=f"{models_url}/{model_route}/digitization/start?api-version=2.0",
            match_headers=headers,
            json=body({"documentId": document_id}),
        )
        for status in ["NotStarted", "Running", "Succeeded"]:
            httpx_mock.add_response(
                method="GET",
                url=f"{models_url}/{model_route}/digitization/result/{document_id}?api-version=2.0",
                match_headers=headers,
                json=body({"status": status}),
            )
        httpx_mock.add_response(
            method="POST",
            url=f"{models_url}/{model_route}/extraction/start?api-version=2.0",
            match_headers=headers,
            match_json={"documentId": document_id},
            json=body({"operationId": operation_id}),
        )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize("pascal_case", [False, True])
    @pytest.mark.asyncio
    async def test_extract_with_model(
        self,
        httpx_mock: HTTPXMock,
        make_service: Callable[..., DocumentsServiceV2],
        models_url: str,
        mode: str,
        pascal_case: bool,
        model_extraction_result: dict,  # type: ignore
    ):
        # ARRANGE
        service = make_service()
        document_id, operation_id = str(uuid4()), str(uuid4())
        self.mock_start(
            httpx_mock,
            models_url,
            "my%20model",
            FOLDER_KEY,
            document_id,
            operation_id,
            pascal_case,
        )
        for status in ["NotStarted", "Running", "Succeeded"]:
            body = {"status": status, "result": model_extraction_result}
            httpx_mock.add_response(
                method="GET",
                url=f"{models_url}/my%20model/extraction/result/{operation_id}?api-version=2.0",
                match_headers={"x-uipath-folderkey": FOLDER_KEY},
                json=to_pascal_case(body) if pascal_case else body,
            )

        # ACT
        if mode == "async":
            response = await service.extract_with_model_async(
                model_name="my model", file=b"test content", folder_key=FOLDER_KEY
            )
        else:
            response = service.extract_with_model(
                model_name="my model", file=b"test content", folder_key=FOLDER_KEY
            )

        # ASSERT
        assert isinstance(response, ModelExtractionResponse)
        assert response.model_name == "my model"
        assert response.folder_key == FOLDER_KEY
        assert (
            response.extraction_result.model_dump()
            == model_extraction_result["extractionResult"]
        )
        [upload] = [
            request
            for request in httpx_mock.get_requests()
            if request.url.path.endswith("/digitization/start")
        ]
        assert b"test content" in upload.read()

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_start_and_retrieve_model_extraction(
        self,
        httpx_mock: HTTPXMock,
        make_service: Callable[..., DocumentsServiceV2],
        models_url: str,
        mode: str,
        model_extraction_result: dict,  # type: ignore
        tmp_path: Path,
    ):
        # ARRANGE
        service = make_service()
        document = tmp_path / "invoice.pdf"
        document.write_bytes(b"test content")
        document_id, operation_id = str(uuid4()), str(uuid4())
        self.mock_start(
            httpx_mock, models_url, "invoices", FOLDER_KEY, document_id, operation_id
        )
        result_url = (
            f"{models_url}/invoices/extraction/result/{operation_id}?api-version=2.0"
        )
        httpx_mock.add_response(url=result_url, json={"status": "Running"})
        httpx_mock.add_response(
            url=result_url,
            json={"status": "Succeeded", "result": model_extraction_result},
        )

        # ACT
        if mode == "async":
            start_response = await service.start_model_extraction_async(
                model_name="invoices", file_path=str(document), folder_key=FOLDER_KEY
            )
        else:
            start_response = service.start_model_extraction(
                model_name="invoices", file_path=str(document), folder_key=FOLDER_KEY
            )
        # Resume triggers keep the start response as a dict and rebuild it.
        restored = StartModelExtractionResponse.model_validate(
            json.loads(start_response.model_dump_json())
        )

        # ASSERT
        [upload] = [
            request
            for request in httpx_mock.get_requests()
            if request.url.path.endswith("/digitization/start")
        ]
        # DU checks the content type, which comes from the file name.
        body = upload.read()
        assert b'filename="invoice.pdf"' in body
        assert b"Content-Type: application/pdf" in body
        assert b"test content" in body
        assert restored == StartModelExtractionResponse(
            operation_id=operation_id,
            document_id=document_id,
            model_name="invoices",
            folder_key=FOLDER_KEY,
        )
        with pytest.raises(OperationNotCompleteException):
            await call(
                mode,
                service,
                "retrieve_model_extraction_result",
                start_response=restored,
            )

        if mode == "async":
            response = await service.retrieve_model_extraction_result_async(restored)
        else:
            response = service.retrieve_model_extraction_result(restored)
        assert (
            response.extraction_result.document_id
            == (model_extraction_result["extractionResult"]["DocumentId"])
        )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_retrieve_model_extraction_result_failed(
        self,
        httpx_mock: HTTPXMock,
        make_service: Callable[..., DocumentsServiceV2],
        models_url: str,
        mode: str,
    ):
        # ARRANGE
        service = make_service()
        start_response = StartModelExtractionResponse(
            operation_id="op", document_id="doc", model_name="m", folder_key=FOLDER_KEY
        )
        httpx_mock.add_response(
            url=f"{models_url}/m/extraction/result/op?api-version=2.0",
            json={"status": "Failed", "error": "Model not found"},
        )

        # ACT & ASSERT
        with pytest.raises(OperationFailedException, match="Model not found"):
            await call(
                mode,
                service,
                "retrieve_model_extraction_result",
                start_response=start_response,
            )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_extract_with_model_times_out(
        self,
        httpx_mock: HTTPXMock,
        make_service: Callable[..., DocumentsServiceV2],
        models_url: str,
        mode: str,
    ):
        # ARRANGE
        service = make_service(polling_timeout=0.05)
        document_id, operation_id = str(uuid4()), str(uuid4())
        self.mock_start(
            httpx_mock, models_url, "invoices", FOLDER_KEY, document_id, operation_id
        )
        httpx_mock.add_response(
            url=f"{models_url}/invoices/extraction/result/{operation_id}?api-version=2.0",
            json={"status": "Running"},
            is_reusable=True,
        )

        # ACT & ASSERT
        with pytest.raises(TimeoutError):
            await call(
                mode,
                service,
                "extract_with_model",
                model_name="invoices",
                file=b"x",
                folder_key=FOLDER_KEY,
            )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize(
        "env, folder_path",
        [
            # The job folder from the environment.
            ({"UIPATH_FOLDER_KEY": FOLDER_KEY}, None),
            # A job folder path, looked up.
            ({"UIPATH_FOLDER_PATH": "Shared/Invoices"}, None),
            # An explicit folder path wins over the job folder.
            ({"UIPATH_FOLDER_KEY": str(uuid4())}, "Shared/Invoices"),
        ],
        ids=["env-key", "env-path", "explicit-path"],
    )
    @pytest.mark.asyncio
    async def test_start_model_extraction_resolves_folder(
        self,
        httpx_mock: HTTPXMock,
        make_service: Callable[..., DocumentsServiceV2],
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
        models_url: str,
        mode: str,
        env: dict,  # type: ignore
        folder_path: str,
    ):
        # ARRANGE
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        service = make_service()
        if folder_path or "UIPATH_FOLDER_PATH" in env:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=Invoices&skip=0&take=20",
                json={
                    "PageItems": [
                        {"Key": FOLDER_KEY, "FullyQualifiedName": "Shared/Invoices"}
                    ]
                },
            )
        document_id, operation_id = str(uuid4()), str(uuid4())
        self.mock_start(
            httpx_mock, models_url, "invoices", FOLDER_KEY, document_id, operation_id
        )

        # ACT
        if mode == "async":
            start_response = await service.start_model_extraction_async(
                model_name="invoices", file=b"x", folder_path=folder_path
            )
        else:
            start_response = service.start_model_extraction(
                model_name="invoices", file=b"x", folder_path=folder_path
            )

        # ASSERT
        assert start_response.folder_key == FOLDER_KEY

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({}, "A folder is required"),
            (
                {"folder_key": FOLDER_KEY, "folder_path": "Shared"},
                "Only one of `folder_key` or `folder_path`",
            ),
            ({"folder_key": "not-a-guid"}, "`folder_key` must be a GUID"),
            ({"model_name": "", "folder_key": FOLDER_KEY}, "Invalid URL path segment"),
            ({"model_name": ".", "folder_key": FOLDER_KEY}, "Invalid URL path segment"),
            (
                {"model_name": "..", "folder_key": FOLDER_KEY},
                "Invalid URL path segment",
            ),
        ],
        ids=["no-folder", "key-and-path", "bad-key", "empty-name", "dot", "dot-dot"],
    )
    @pytest.mark.asyncio
    async def test_start_model_extraction_rejects_invalid_arguments(
        self,
        make_service: Callable[..., DocumentsServiceV2],
        mode: str,
        kwargs: dict,  # type: ignore
        message: str,
    ):
        # ARRANGE
        service = make_service()
        kwargs = {"model_name": "invoices", "file": b"x", **kwargs}

        # ACT & ASSERT: it fails before sending any request.
        with pytest.raises(ValueError, match=message):
            await call(mode, service, "start_model_extraction", **kwargs)

    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.asyncio
    async def test_folder_path_needs_a_folders_service(
        self,
        make_service: Callable[..., DocumentsServiceV2],
        mode: str,
    ):
        # ARRANGE
        service = make_service(with_folders_service=False)

        # ACT & ASSERT: it fails before sending any request.
        with pytest.raises(ValueError, match="needs a `FolderService`"):
            await call(
                mode,
                service,
                "start_model_extraction",
                model_name="invoices",
                file=b"x",
                folder_path="Shared/Invoices",
            )


def test_only_documents_v2_extracts_with_folder_models(
    config: UiPathApiConfig,
) -> None:
    sdk = UiPath(base_url=config.base_url, secret=config.secret)

    assert hasattr(sdk.documents_v2, "extract_with_model")
    assert isinstance(sdk.documents_v2._folders(), FolderService)
    assert not hasattr(sdk.documents, "extract_with_model")
    assert not hasattr(sdk.documents, "start_model_extraction")
