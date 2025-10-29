import json
import os
import unittest
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from uipath.tracing._otel_exporters import LlmOpsHttpExporter


@pytest.fixture
def mock_env_vars():
    """Fixture to set and clean up environment variables for testing."""
    original_values = {}

    # Save original values
    for var in ["UIPATH_URL", "UIPATH_ACCESS_TOKEN"]:
        original_values[var] = os.environ.get(var)

    # Set test values
    os.environ["UIPATH_URL"] = "https://test.uipath.com/org/tenant/"
    os.environ["UIPATH_ACCESS_TOKEN"] = "test-token"

    yield

    # Restore original values
    for var, value in original_values.items():
        if value is None:
            if var in os.environ:
                del os.environ[var]
        else:
            os.environ[var] = value


@pytest.fixture
def mock_span():
    """Create a mock ReadableSpan for testing."""
    span = MagicMock(spec=ReadableSpan)
    return span


@pytest.fixture
def exporter(mock_env_vars):
    """Create an exporter instance for testing."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
        # Mock _build_url to include query parameters as in the actual implementation
        exporter._build_url = MagicMock(  # type: ignore
            return_value="https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/spans?traceId=test-trace-id&source=Robots"
        )
        yield exporter


def test_init_with_env_vars(mock_env_vars):
    """Test initialization with environment variables."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()

        assert exporter.base_url == "https://test.uipath.com/org/tenant"
        assert exporter.auth_token == "test-token"
        assert exporter.headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }


def test_init_with_default_url():
    """Test initialization with default URL when environment variable is not set."""
    with (
        patch("uipath.tracing._otel_exporters.httpx.Client"),
        patch.dict(os.environ, {"UIPATH_ACCESS_TOKEN": "test-token"}, clear=True),
    ):
        exporter = LlmOpsHttpExporter()

        assert exporter.base_url == "https://cloud.uipath.com/dummyOrg/dummyTennant"
        assert exporter.auth_token == "test-token"


def test_export_success(exporter, mock_span):
    """Test successful export of spans."""
    mock_uipath_span = MagicMock()
    mock_uipath_span.to_dict.return_value = {"span": "data", "TraceId": "test-trace-id"}

    with patch(
        "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span",
        return_value=mock_uipath_span,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        exporter.http_client.post.return_value = mock_response

        result = exporter.export([mock_span])

        assert result == SpanExportResult.SUCCESS
        exporter._build_url.assert_called_once_with(
            [{"span": "data", "TraceId": "test-trace-id"}]
        )
        exporter.http_client.post.assert_called_once_with(
            "https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/spans?traceId=test-trace-id&source=Robots",
            json=[{"span": "data", "TraceId": "test-trace-id"}],
        )


def test_export_failure(exporter, mock_span):
    """Test export failure with multiple retries."""
    mock_uipath_span = MagicMock()
    mock_uipath_span.to_dict.return_value = {"span": "data"}

    with patch(
        "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span",
        return_value=mock_uipath_span,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        exporter.http_client.post.return_value = mock_response

        with patch("uipath.tracing._otel_exporters.time.sleep") as mock_sleep:
            result = exporter.export([mock_span])

        assert result == SpanExportResult.FAILURE
        assert exporter.http_client.post.call_count == 4  # Default max_retries is 3
        assert (
            mock_sleep.call_count == 3
        )  # Should sleep between retries (except after the last one)


def test_export_exception(exporter, mock_span):
    """Test export with exceptions during HTTP request."""
    mock_uipath_span = MagicMock()
    mock_uipath_span.to_dict.return_value = {"span": "data"}

    with patch(
        "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span",
        return_value=mock_uipath_span,
    ):
        exporter.http_client.post.side_effect = Exception("Connection error")

        with patch("uipath.tracing._otel_exporters.time.sleep"):
            result = exporter.export([mock_span])

        assert result == SpanExportResult.FAILURE
        assert exporter.http_client.post.call_count == 4  # Default max_retries is 3


def test_force_flush(exporter):
    """Test force_flush returns True."""
    assert exporter.force_flush() is True


def test_get_base_url():
    """Test _get_base_url method with different environment configurations."""
    # Test with environment variable set
    with patch.dict(
        os.environ, {"UIPATH_URL": "https://custom.uipath.com/org/tenant/"}, clear=True
    ):
        with patch("uipath.tracing._otel_exporters.httpx.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://custom.uipath.com/org/tenant"

    # Test with environment variable set but with no trailing slash
    with patch.dict(
        os.environ, {"UIPATH_URL": "https://custom.uipath.com/org/tenant"}, clear=True
    ):
        with patch("uipath.tracing._otel_exporters.httpx.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://custom.uipath.com/org/tenant"

    # Test with no environment variable
    with patch.dict(os.environ, {}, clear=True):
        with patch("uipath.tracing._otel_exporters.httpx.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://cloud.uipath.com/dummyOrg/dummyTennant"


def test_send_with_retries_success():
    """Test _send_with_retries method with successful response."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        exporter.http_client.post.return_value = mock_response  # type: ignore

        result = exporter._send_with_retries("http://example.com", [{"span": "data"}])

        assert result == SpanExportResult.SUCCESS
        exporter.http_client.post.assert_called_once_with(  # type: ignore
            "http://example.com", json=[{"span": "data"}]
        )


class TestLangchainExporter(unittest.TestCase):
    def setUp(self):
        self.exporter = LlmOpsHttpExporter(extra_process_spans=True)

    def test_process_span_with_dict_attributes(self):
        """
        Tests that the span is processed correctly when Attributes is a dictionary.
        When attributes start as dict, they remain as dict (optimized path).
        """
        span_data = {
            "Id": "501e2c8c-066a-43a8-8e14-7a8d51773a13",
            "TraceId": "8b706075-9bfc-452c-be10-766aa8827c35",
            "ParentId": "607b554d-f340-4cb7-9793-501d21c25bc1",
            "Name": "UiPathChat",
            "StartTime": "2025-09-18T14:35:47.523Z",
            "EndTime": "2025-09-18T14:35:48.988Z",
            "Attributes": {
                "input.value": '{"messages": [[{"lc": 1, "type": "constructor", "id": ["langchain", "schema", "messages", "HumanMessage"], "kwargs": {"content": "Test content", "type": "human"}}]]}',
                "output.value": '{"generations": []}',
                "llm.model_name": "gpt-4o-mini-2024-07-18",
                "openinference.span.kind": "LLM",
            },
            "Status": 1,
        }

        self.exporter._process_span_attributes(span_data)

        self.assertEqual(span_data["SpanType"], "completion")
        self.assertIn("Attributes", span_data)

        # When input is dict, output stays as dict (optimized path)
        attributes = span_data["Attributes"]
        assert isinstance(attributes, dict)
        self.assertIsInstance(attributes, dict)
        self.assertEqual(attributes["model"], "gpt-4o-mini-2024-07-18")
        self.assertIn("input", attributes)
        self.assertIn("output", attributes)

    def test_process_span_with_json_string_attributes(self):
        """
        Tests that the span is processed correctly when Attributes is a JSON string.
        """
        attributes_dict = {
            "input.value": '{"messages": [[{"lc": 1, "type": "constructor", "id": ["langchain", "schema", "messages", "HumanMessage"], "kwargs": {"content": "Test content", "type": "human"}}]]}',
            "output.value": '{"generations": []}',
            "llm.model_name": "gpt-4o-mini-2024-07-18",
            "openinference.span.kind": "LLM",
        }
        span_data = {
            "Id": "501e2c8c-066a-43a8-8e14-7a8d51773a13",
            "TraceId": "8b706075-9bfc-452c-be10-766aa8827c35",
            "ParentId": "607b554d-f340-4cb7-9793-501d21c25bc1",
            "Name": "UiPathChat",
            "StartTime": "2025-09-18T14:35:47.523Z",
            "EndTime": "2025-09-18T14:35:48.988Z",
            "Attributes": json.dumps(attributes_dict),
            "Status": 1,
        }

        self.exporter._process_span_attributes(span_data)

        self.assertEqual(span_data["SpanType"], "completion")
        self.assertIn("Attributes", span_data)

        attributes_value = span_data["Attributes"]
        assert isinstance(attributes_value, str)
        attributes = json.loads(attributes_value)
        self.assertEqual(attributes["model"], "gpt-4o-mini-2024-07-18")
        self.assertIn("input", attributes)
        self.assertIn("output", attributes)

    def test_process_tool_span(self):
        """
        Tests that a tool span is processed correctly.
        When attributes start as dict, they remain as dict (optimized path).
        """
        span_data = {
            "Id": "b667e7d7-913f-4e99-8d95-1a7660e40edd",
            "TraceId": "8b706075-9bfc-452c-be10-766aa8827c35",
            "ParentId": "607b554d-f340-4cb7-9793-501d21c25bc1",
            "Name": "get_current_time",
            "StartTime": "2025-09-18T14:35:48.992Z",
            "EndTime": "2025-09-18T14:35:48.993Z",
            "Attributes": {
                "input.value": "{}",
                "output.value": "2025-09-18 14:35:48",
                "tool.name": "get_current_time",
                "openinference.span.kind": "TOOL",
            },
            "Status": 1,
        }

        self.exporter._process_span_attributes(span_data)

        self.assertEqual(span_data["SpanType"], "toolCall")
        self.assertIn("Attributes", span_data)

        # When input is dict, output stays as dict (optimized path)
        attributes = span_data["Attributes"]
        assert isinstance(attributes, dict)
        self.assertIsInstance(attributes, dict)
        self.assertEqual(attributes["toolName"], "get_current_time")
        self.assertEqual(attributes["arguments"], {})
        self.assertEqual(attributes["result"], "2025-09-18 14:35:48")
        self.assertIn("input.value", attributes)
        self.assertIn("output.value", attributes)

    def test_process_span_attributes_tool_call(self):
        span_data = {
            "PermissionStatus": 0,
            "Id": "7ec33180-5fe5-49ec-87aa-03d5a1e9ccc7",
            "TraceId": "fde81e6a-cb40-496a-bff1-939b061dd6c9",
            "ParentId": "0babf3dd-aff3-4961-a8b3-1e7f64259832",
            "Name": "get_current_time",
            "StartTime": "2025-09-18T14:58:31.417Z",
            "EndTime": "2025-09-18T14:58:31.418Z",
            "Attributes": {
                "input.value": "{}",
                "output.value": "2025-09-18 14:58:31",
                "tool.name": "get_current_time",
                "tool.description": "Get the current date and time.",
                "session.id": "0b3cf051-6446-4467-a9a1-3b4b699f476b",
                "metadata": '{"thread_id": "0b3cf051-6446-4467-a9a1-3b4b699f476b", "langgraph_step": 1, "langgraph_node": "make_tool_calls", "langgraph_triggers": ["branch:to:make_tool_calls"], "langgraph_path": ["__pregel_pull", "make_tool_calls"], "langgraph_checkpoint_ns": "make_tool_calls:efdce94a-e49a-99f3-180a-f1b3e44f08f7", "checkpoint_ns": "make_tool_calls:efdce94a-e49a-99f3-180a-f1b3e44f08f7"}',
                "openinference.span.kind": "TOOL",
            },
            "Status": 1,
            "OrganizationId": "b7006b1c-11c3-4a80-802e-fee0ebf9c360",
            "TenantId": "6961a069-3392-40ca-bf5d-276f4e54c8ff",
            "ExpiryTimeUtc": None,
            "FolderKey": "d0e72980-7a97-44e1-93b7-4087689521b7",
            "Source": 0,
            "SpanType": "OpenTelemetry",
            "ProcessKey": "65965c09-87e3-4fa3-a7be-3fdb3955bd47",
            "JobKey": "0b3cf051-6446-4467-a9a1-3b4b699f476b",
            "ReferenceId": None,
            "VerbosityLevel": 2,
            "ExecutionType": None,
            "UpdatedAt": "2025-09-18T14:58:36.891Z",
        }

        self.exporter._process_span_attributes(span_data)
        self.assertEqual(span_data["SpanType"], "toolCall")

        # When input is dict, output stays as dict (optimized path)
        attributes = span_data["Attributes"]
        assert isinstance(attributes, dict)
        self.assertIsInstance(attributes, dict)
        self.assertEqual(attributes["toolName"], "get_current_time")
        self.assertEqual(attributes["input"], {})
        self.assertEqual(attributes["output"], "2025-09-18 14:58:31")

    def test_tool_span_mapping_issue(self):
        """
        Test the specific TOOL span that fails to map correctly.
        This reproduces the issue where TOOL spans don't get properly mapped.
        """
        span_data = {
            "PermissionStatus": 0,
            "Id": "79398bc6-f01f-424b-9238-342d71f38d3e",
            "TraceId": "731b01dd-ae81-4681-ad27-a56d33e80fe1",
            "ParentId": "2529b799-c3b9-4506-8e00-6824f6b5c30a",
            "Name": "get_current_time",
            "StartTime": "2025-09-18T15:14:19.639Z",
            "EndTime": "2025-09-18T15:14:19.640Z",
            "Attributes": {
                "input.value": "{}",
                "output.value": "2025-09-18 15:14:19",
                "tool.name": "get_current_time",
                "tool.description": "Get the current date and time.",
                "session.id": "8364fdaf-3915-414b-9f64-f90a62a7454c",
                "metadata": '{"thread_id": "8364fdaf-3915-414b-9f64-f90a62a7454c", "langgraph_step": 1, "langgraph_node": "make_tool_calls", "langgraph_triggers": ["branch:to:make_tool_calls"], "langgraph_path": ["__pregel_pull", "make_tool_calls"], "langgraph_checkpoint_ns": "make_tool_calls:1758151e-7e11-2f93-d853-06bf123710ca", "checkpoint_ns": "make_tool_calls:1758151e-7e11-2f93-d853-06bf123710ca"}',
                "openinference.span.kind": "TOOL",
            },
            "Status": 1,
            "OrganizationId": "b7006b1c-11c3-4a80-802e-fee0ebf9c360",
            "TenantId": "6961a069-3392-40ca-bf5d-276f4e54c8ff",
            "ExpiryTimeUtc": None,
            "FolderKey": "d0e72980-7a97-44e1-93b7-4087689521b7",
            "Source": 0,
            "SpanType": "OpenTelemetry",
            "ProcessKey": "65965c09-87e3-4fa3-a7be-3fdb3955bd47",
            "JobKey": "8364fdaf-3915-414b-9f64-f90a62a7454c",
            "ReferenceId": None,
            "VerbosityLevel": 2,
            "ExecutionType": None,
            "UpdatedAt": "2025-09-18T15:14:20.482Z",
        }

        self.exporter._process_span_attributes(span_data)

        # SpanType should be mapped to toolCall
        self.assertEqual(span_data["SpanType"], "toolCall")

        # Attributes should be processed
        self.assertIn("Attributes", span_data)

        # When input is dict, output stays as dict (optimized path)
        attributes = span_data["Attributes"]
        assert isinstance(attributes, dict)
        self.assertIsInstance(attributes, dict)

        # These are the expected attributes for a tool call
        self.assertEqual(attributes["toolName"], "get_current_time")
        self.assertEqual(attributes["type"], "toolCall")
        self.assertEqual(attributes["arguments"], {})
        self.assertEqual(attributes["result"], "2025-09-18 15:14:19")
        self.assertEqual(attributes["toolType"], "Integration")
        self.assertIsNone(attributes["error"])

        # input.value should be mapped to input
        self.assertIn("input", attributes)
        self.assertEqual(attributes["input"], {})

    def test_llm_span_mapping_consistency(self):
        """
        Test that LLM spans are consistently mapped to completion type.
        This verifies the fix for flaky span type mapping.
        """
        span_data = {
            "PermissionStatus": 0,
            "Id": "8198780d-9d79-4270-b69d-aaf012189c50",
            "TraceId": "78e8f5a6-d694-456f-a639-ab161ac8ac5b",
            "ParentId": "c8c6e2bb-241b-429a-8471-95da8693a28f",
            "Name": "UiPathChat",
            "StartTime": "2025-09-18T15:25:36.486Z",
            "EndTime": "2025-09-18T15:25:37.720Z",
            "Attributes": {
                "input.value": '{"messages": []}',
                "output.value": '{"generations": []}',
                "llm.model_name": "gpt-4o-mini-2024-07-18",
                "llm.token_count.prompt": 219,
                "llm.token_count.completion": 66,
                "llm.token_count.total": 285,
                "openinference.span.kind": "LLM",
            },
            "Status": 1,
            "OrganizationId": "b7006b1c-11c3-4a80-802e-fee0ebf9c360",
            "TenantId": "6961a069-3392-40ca-bf5d-276f4e54c8ff",
            "ExpiryTimeUtc": None,
            "FolderKey": "d0e72980-7a97-44e1-93b7-4087689521b7",
            "Source": 0,
            "SpanType": "OpenTelemetry",
            "ProcessKey": "65965c09-87e3-4fa3-a7be-3fdb3955bd47",
            "JobKey": "04ecd5b3-72ef-4302-beae-7d21a94ab0de",
            "ReferenceId": None,
            "VerbosityLevel": 2,
            "ExecutionType": None,
            "UpdatedAt": "2025-09-18T15:25:38.591Z",
        }

        self.exporter._process_span_attributes(span_data)

        # Verify LLM span gets mapped to completion
        self.assertEqual(span_data["SpanType"], "completion")

        # Verify attributes are processed
        self.assertIn("Attributes", span_data)

        # When input is dict, output stays as dict (optimized path)
        attributes = span_data["Attributes"]
        assert isinstance(attributes, dict)
        self.assertIsInstance(attributes, dict)

        # Verify LLM-specific attributes are present
        self.assertEqual(attributes["model"], "gpt-4o-mini-2024-07-18")
        self.assertIn("usage", attributes)
        usage = attributes["usage"]
        assert isinstance(usage, dict)
        self.assertEqual(usage["promptTokens"], 219)
        self.assertEqual(usage["completionTokens"], 66)
        self.assertEqual(usage["totalTokens"], 285)

    def test_unknown_span_type_preserved(self):
        """
        Test that spans with UNKNOWN or unrecognized openinference.span.kind
        are still exported and don't get dropped.

        This tests the real-world case from the logs where PydanticOutputParser
        spans have openinference.span.kind=UNKNOWN and should be preserved.
        """
        # Original span data from actual logs
        span_data = {
            "Id": "7325f1a7-71ea-4ec1-82c0-266b0a7242a7",
            "TraceId": "3d53656e-8523-4917-8c58-686ab29b98da",
            "ParentId": "0d173f1f-015e-47b5-80c4-b63111b63536",
            "Name": "PydanticOutputParser",
            "StartTime": "2025-10-29T12:34:48.379494",
            "EndTime": "2025-10-29T12:34:48.380852",
            "Attributes": {
                "input.value": '{"content": "```json\\n{\\"label\\": \\"security\\", \\"confidence\\": 0.95}\\n```", "additional_kwargs": {}, "response_metadata": {"token_usage": {"completion_tokens": 19, "prompt_tokens": 333, "total_tokens": 352}}}',
                "input.mime_type": "application/json",
                "output.value": '{"label": "security", "confidence": 0.95}',
                "output.mime_type": "application/json",
                "session.id": "default",
                "metadata": '{"thread_id": "default", "langgraph_step": 2, "langgraph_node": "classify"}',
                "openinference.span.kind": "UNKNOWN",
            },
            "Status": 1,
            "SpanType": "OpenTelemetry",
        }

        print("\n=== Testing UNKNOWN span type preservation ===")
        print(f"Initial SpanType: {span_data['SpanType']}")
        attributes_before = span_data["Attributes"]
        assert isinstance(attributes_before, dict)
        print(
            f"openinference.span.kind: {attributes_before['openinference.span.kind']}"
        )
        print(f"Attributes type before: {type(attributes_before)}")

        # Process the span
        self.exporter._process_span_attributes(span_data)

        print(f"SpanType after processing: {span_data['SpanType']}")
        print(f"Attributes type after: {type(span_data['Attributes'])}")

        # Verify span is processed correctly
        self.assertEqual(
            span_data["SpanType"],
            "UNKNOWN",
            "SpanType should be mapped to UNKNOWN from openinference.span.kind",
        )
        self.assertIn("Attributes", span_data, "Attributes should still be present")

        # When input is dict, output stays as dict (optimized path)
        attributes = span_data["Attributes"]
        assert isinstance(attributes, dict)
        self.assertIsInstance(
            attributes, dict, "Attributes should remain as dict in optimized path"
        )

        # Basic attribute mapping should still work
        self.assertIn(
            "input",
            attributes,
            "input.value should be mapped to input by ATTRIBUTE_MAPPING",
        )
        self.assertIn(
            "output",
            attributes,
            "output.value should be mapped to output by ATTRIBUTE_MAPPING",
        )

        # Verify mime types are preserved
        self.assertEqual(attributes["input.mime_type"], "application/json")
        self.assertEqual(attributes["output.mime_type"], "application/json")

        # Verify parsed values
        input_val = attributes["input"]
        assert isinstance(input_val, dict)
        self.assertIsInstance(input_val, dict, "input should be parsed from JSON")
        self.assertIn("content", input_val)

        output_val = attributes["output"]
        assert isinstance(output_val, dict)
        self.assertIsInstance(output_val, dict, "output should be parsed from JSON")
        self.assertEqual(output_val["label"], "security")
        self.assertEqual(output_val["confidence"], 0.95)

        print("✓ UNKNOWN span preserved and processed correctly")
        print(f"✓ Final attributes keys: {list(attributes.keys())}")


if __name__ == "__main__":
    unittest.main()
