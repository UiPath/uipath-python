import json

import httpx

from uipath.platform.errors import EnrichedException

# URL patterns that route to specific extractors
_ORCHESTRATOR_URL = "https://cloud.uipath.com/org/tenant/orchestrator_/api/v1"
_LLM_URL = "https://cloud.uipath.com/org/tenant/orchestrator_/llm/chat"
_AGENTHUB_URL = "https://cloud.uipath.com/org/tenant/agenthub_/api/v1"
_APPS_URL = "https://cloud.uipath.com/org/tenant/apps_/api/v1"
_ELEMENTS_URL = "https://cloud.uipath.com/org/tenant/elements_/api/v1"
_LLMOPS_URL = "https://cloud.uipath.com/org/tenant/llmopstenant_/api/v1"
_GENERIC_URL = "https://cloud.uipath.com/api/test"


def _make_error(
    status_code: int = 500,
    body: str | bytes = b"",
    content_type: str = "application/json",
    url: str = _GENERIC_URL,
    method: str = "POST",
) -> httpx.HTTPStatusError:
    if isinstance(body, str):
        body = body.encode()
    return httpx.HTTPStatusError(
        message=f"Server error {status_code}",
        request=httpx.Request(method, url),
        response=httpx.Response(
            status_code,
            content=body,
            headers={"content-type": content_type},
        ),
    )


class TestBasicProperties:
    def test_status_code(self):
        exc = EnrichedException(_make_error(404))
        assert exc.status_code == 404

    def test_url(self):
        exc = EnrichedException(
            _make_error(url="https://cloud.uipath.com/org/tenant/api/v1")
        )
        assert exc.url == "https://cloud.uipath.com/org/tenant/api/v1"

    def test_http_method(self):
        exc = EnrichedException(_make_error(method="DELETE"))
        assert exc.http_method == "DELETE"

    def test_response_content_short(self):
        exc = EnrichedException(_make_error(body=b'{"message":"oops"}'))
        assert exc.response_content == '{"message":"oops"}'

    def test_response_content_truncated(self):
        long_body = "x" * 300
        exc = EnrichedException(_make_error(body=long_body.encode()))
        assert exc.response_content.endswith("... (truncated)")
        assert len(exc.response_content) < 300

    def test_str_contains_status_code(self):
        exc = EnrichedException(_make_error(404))
        assert "404" in str(exc)

    def test_status_code_is_int(self):
        exc = EnrichedException(_make_error(502))
        assert isinstance(exc.status_code, int)


class TestErrorInfo:
    def test_none_for_empty_body(self):
        exc = EnrichedException(_make_error(body=b""))
        assert exc.error_info is None

    def test_none_for_non_json(self):
        exc = EnrichedException(_make_error(body=b"not json"))
        assert exc.error_info is None

    def test_cached(self):
        body = json.dumps({"message": "test"})
        exc = EnrichedException(_make_error(body=body))
        first = exc.error_info
        second = exc.error_info
        assert first is second


class TestGenericExtraction:
    """Tests for the generic fallback extractor (no service prefix in URL)."""

    def test_message_field(self):
        body = json.dumps({"message": "some error"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.message == "some error"

    def test_error_as_string(self):
        body = json.dumps({"error": "something went wrong"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.message == "something went wrong"

    def test_nested_error_message(self):
        body = json.dumps({"error": {"message": "nested error"}})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.message == "nested error"

    def test_error_code_fields(self):
        body = json.dumps({"errorCode": "ERR_001"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.error_code == "ERR_001"

    def test_code_field(self):
        body = json.dumps({"code": "ERR_002"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.error_code == "ERR_002"

    def test_numeric_code_converted_to_str(self):
        body = json.dumps({"errorCode": 1002})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.error_code == "1002"

    def test_trace_id(self):
        body = json.dumps({"traceId": "abc-123"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.trace_id == "abc-123"

    def test_request_id(self):
        body = json.dumps({"requestId": "req-456"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.trace_id == "req-456"

    def test_no_known_fields_returns_none_message(self):
        body = json.dumps({"unknown_field": "value"})
        exc = EnrichedException(_make_error(body=body))
        assert exc.error_info is not None
        assert exc.error_info.message is None


class TestRfc7807Extraction:
    """Tests for RFC 7807 content-type based extraction."""

    def test_problem_json_content_type(self):
        body = json.dumps(
            {"detail": "Forbidden", "title": "Access Denied", "type": "AUTH_ERR"}
        )
        exc = EnrichedException(
            _make_error(403, body=body, content_type="application/problem+json")
        )
        assert exc.error_info is not None
        assert exc.error_info.message == "Forbidden"
        assert exc.error_info.error_code == "AUTH_ERR"

    def test_structural_rfc7807_detection(self):
        body = json.dumps(
            {"detail": "Not found", "title": "Error", "status": 404, "type": "E1"}
        )
        exc = EnrichedException(_make_error(404, body=body))
        assert exc.error_info is not None
        assert exc.error_info.message == "Not found"
        assert exc.error_info.error_code == "E1"


class TestOrchestratorExtraction:
    """Orchestrator uses generic extractor (message, errorCode, traceId)."""

    def test_process_not_found(self):
        body = json.dumps(
            {
                "message": "Process not found",
                "errorCode": "1002",
                "traceId": "abc-123",
            }
        )
        exc = EnrichedException(_make_error(404, body=body, url=_ORCHESTRATOR_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Process not found"
        assert exc.error_info.error_code == "1002"
        assert exc.error_info.trace_id == "abc-123"


class TestLlmGatewayExtraction:
    """LLM Gateway has nested error objects and vendor passthrough."""

    def test_nested_vendor_error(self):
        body = json.dumps(
            {
                "error": {
                    "code": "content_filter",
                    "message": "Content was filtered by safety policy",
                }
            }
        )
        exc = EnrichedException(_make_error(400, body=body, url=_LLM_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Content was filtered by safety policy"
        assert exc.error_info.error_code == "content_filter"

    def test_top_level_with_nested(self):
        body = json.dumps(
            {
                "message": "Model unavailable",
                "errorCode": "LLM_ERR",
                "error": {"message": "rate limit", "code": "429"},
            }
        )
        exc = EnrichedException(_make_error(429, body=body, url=_LLM_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Model unavailable"
        assert exc.error_info.error_code == "LLM_ERR"


class TestAgentHubExtraction:
    """AgentHub has nested problem objects."""

    def test_nested_problem(self):
        body = json.dumps({"problem": {"detail": "Agent not found", "type": "AH_404"}})
        exc = EnrichedException(_make_error(404, body=body, url=_AGENTHUB_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Agent not found"
        assert exc.error_info.error_code == "AH_404"


class TestAppsExtraction:
    """Apps prioritizes errorMessageV2 over message."""

    def test_error_message_v2_priority(self):
        body = json.dumps(
            {"errorMessageV2": "Detailed error", "message": "Short error"}
        )
        exc = EnrichedException(_make_error(400, body=body, url=_APPS_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Detailed error"


class TestElementsExtraction:
    """Elements has vendor passthrough fields (providerMessage, providerErrorCode)."""

    def test_provider_fields(self):
        body = json.dumps(
            {
                "providerMessage": "Rate limit exceeded",
                "providerErrorCode": "429",
                "requestId": "req-123",
            }
        )
        exc = EnrichedException(_make_error(429, body=body, url=_ELEMENTS_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Rate limit exceeded"
        assert exc.error_info.error_code == "429"
        assert exc.error_info.trace_id == "req-123"


class TestLlmOpsExtraction:
    """LLMOps uses errorMessage, code, requestId."""

    def test_llmops_fields(self):
        body = json.dumps(
            {
                "errorMessage": "Quota exceeded",
                "code": "QUOTA_001",
                "requestId": "req-789",
            }
        )
        exc = EnrichedException(_make_error(429, body=body, url=_LLMOPS_URL))
        assert exc.error_info is not None
        assert exc.error_info.message == "Quota exceeded"
        assert exc.error_info.error_code == "QUOTA_001"
        assert exc.error_info.trace_id == "req-789"


class TestRouterPriority:
    """RFC 7807 content-type should override service-specific extractors."""

    def test_rfc7807_content_type_beats_service_extractor(self):
        body = json.dumps(
            {"detail": "RFC detail", "type": "RFC_ERR", "errorMessageV2": "Apps msg"}
        )
        exc = EnrichedException(
            _make_error(
                400, body=body, url=_APPS_URL, content_type="application/problem+json"
            )
        )
        assert exc.error_info is not None
        assert exc.error_info.message == "RFC detail"
        assert exc.error_info.error_code == "RFC_ERR"
