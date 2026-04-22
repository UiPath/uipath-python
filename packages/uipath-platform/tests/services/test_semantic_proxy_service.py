"""Tests for SemanticProxyService."""

import json
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.semantic_proxy import (
    PiiDetectionRequest,
    PiiDetectionResponse,
    PiiDocument,
    PiiEntityThreshold,
    PiiFile,
    SemanticProxyService,
)


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> SemanticProxyService:
    return SemanticProxyService(config=config, execution_context=execution_context)


@pytest.fixture
def sample_response_json() -> dict[str, Any]:
    return {
        "response": [
            {
                "id": "user-prompt",
                "role": "user",
                "maskedDocument": "Contact [Person-1]",
                "initialDocument": "Contact Alison",
                "piiEntities": [
                    {
                        "piiText": "Alison",
                        "replacementText": "[Person-1]",
                        "piiType": "Person",
                        "offset": 8,
                        "confidenceScore": 0.99,
                    }
                ],
            }
        ],
        "files": [
            {
                "fileName": "doc.pdf",
                "fileUrl": "https://blob.example.com/redacted/doc.pdf",
                "piiEntities": [
                    {
                        "piiText": "alice@example.com",
                        "replacementText": "[Email-1]",
                        "piiType": "Email",
                        "offset": 100,
                        "confidenceScore": 0.88,
                    }
                ],
            }
        ],
    }


class TestSemanticProxyService:
    """Test SemanticProxyService functionality."""

    class TestDetectPii:
        """Test detect_pii (sync)."""

        def test_returns_typed_response(
            self,
            httpx_mock: HTTPXMock,
            service: SemanticProxyService,
            base_url: str,
            org: str,
            tenant: str,
            sample_response_json: dict[str, Any],
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/semanticproxy_/api/pii-detection",
                status_code=200,
                json=sample_response_json,
            )

            request = PiiDetectionRequest(
                documents=[
                    PiiDocument(
                        id="user-prompt", role="user", document="Contact Alison"
                    )
                ]
            )
            result = service.detect_pii(request)

            assert isinstance(result, PiiDetectionResponse)
            assert len(result.response) == 1
            assert result.response[0].masked_document == "Contact [Person-1]"
            assert len(result.files) == 1
            assert result.files[0].file_name == "doc.pdf"
            assert result.files[0].pii_entities[0].replacement_text == "[Email-1]"

    class TestDetectPiiAsync:
        """Test detect_pii_async."""

        async def test_returns_typed_response(
            self,
            httpx_mock: HTTPXMock,
            service: SemanticProxyService,
            base_url: str,
            org: str,
            tenant: str,
            sample_response_json: dict[str, Any],
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/semanticproxy_/api/pii-detection",
                status_code=200,
                json=sample_response_json,
            )

            request = PiiDetectionRequest(
                files=[
                    PiiFile(
                        file_name="doc.pdf",
                        file_url="https://input.example.com/doc.pdf",
                        file_type="pdf",
                    )
                ]
            )
            result = await service.detect_pii_async(request)

            assert isinstance(result, PiiDetectionResponse)
            assert (
                result.files[0].file_url == "https://blob.example.com/redacted/doc.pdf"
            )

        async def test_request_payload_uses_aliases(
            self,
            httpx_mock: HTTPXMock,
            service: SemanticProxyService,
            base_url: str,
            org: str,
            tenant: str,
            sample_response_json: dict[str, Any],
        ) -> None:
            captured_request: httpx.Request | None = None

            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(status_code=200, json=sample_response_json)

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/semanticproxy_/api/pii-detection",
                callback=capture,
            )

            request = PiiDetectionRequest(
                documents=[
                    PiiDocument(id="user-prompt", role="user", document="Hello")
                ],
                files=[
                    PiiFile(
                        file_name="doc.pdf",
                        file_url="https://input.example.com/doc.pdf",
                        file_type="pdf",
                    )
                ],
                language_code="en",
                confidence_threshold=0.5,
                entity_thresholds=[
                    PiiEntityThreshold(category="Person", confidence_threshold=0.7),
                ],
            )
            await service.detect_pii_async(request)

            assert captured_request is not None
            payload = json.loads(captured_request.content)

            # Top-level uses camelCase aliases
            assert "documents" in payload
            assert "files" in payload
            assert "languageCode" in payload
            assert "confidenceThreshold" in payload
            assert "entityThresholds" in payload

            # File uses camelCase aliases
            assert payload["files"][0]["fileName"] == "doc.pdf"
            assert payload["files"][0]["fileUrl"] == "https://input.example.com/doc.pdf"
            assert payload["files"][0]["fileType"] == "pdf"

            # Entity threshold uses kebab-case aliases
            threshold = payload["entityThresholds"][0]
            assert threshold["pii-entity-category"] == "Person"
            assert threshold["pii-entity-confidence-threshold"] == 0.7

        async def test_request_excludes_none_fields(
            self,
            httpx_mock: HTTPXMock,
            service: SemanticProxyService,
            base_url: str,
            org: str,
            tenant: str,
            sample_response_json: dict[str, Any],
        ) -> None:
            captured_request: httpx.Request | None = None

            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(status_code=200, json=sample_response_json)

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/semanticproxy_/api/pii-detection",
                callback=capture,
            )

            # Only documents set; other optional fields should be omitted
            request = PiiDetectionRequest(
                documents=[PiiDocument(id="user-prompt", role="user", document="Hello")]
            )
            await service.detect_pii_async(request)

            assert captured_request is not None
            payload = json.loads(captured_request.content)
            assert "files" not in payload
            assert "languageCode" not in payload
            assert "confidenceThreshold" not in payload
            assert "entityThresholds" not in payload

        async def test_url_is_tenant_scoped(
            self,
            httpx_mock: HTTPXMock,
            service: SemanticProxyService,
            base_url: str,
            org: str,
            tenant: str,
            sample_response_json: dict[str, Any],
        ) -> None:
            captured_request: httpx.Request | None = None

            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(status_code=200, json=sample_response_json)

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/semanticproxy_/api/pii-detection",
                callback=capture,
            )

            request = PiiDetectionRequest(
                documents=[PiiDocument(id="user-prompt", role="user", document="Hello")]
            )
            await service.detect_pii_async(request)

            assert captured_request is not None
            assert org.strip("/") in captured_request.url.path
            assert tenant.strip("/") in captured_request.url.path
            assert "/semanticproxy_/api/pii-detection" in captured_request.url.path
