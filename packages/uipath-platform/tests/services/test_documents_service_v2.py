import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.documents import (
    DocumentsServiceV2,
    FieldType,
    ProjectType,
    ValidateExtractionAction,
)

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
