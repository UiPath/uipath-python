import os
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
    with patch("uipath.tracing._otel_exporters.Client"):
        exporter = LlmOpsHttpExporter()
        # Mock _build_url to include query parameters as in the actual implementation
        exporter._build_url = MagicMock(  # type: ignore
            return_value="https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/spans?traceId=test-trace-id&source=Robots"
        )
        yield exporter


def test_init_with_env_vars(mock_env_vars):
    """Test initialization with environment variables."""
    with patch("uipath.tracing._otel_exporters.Client"):
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
        patch("uipath.tracing._otel_exporters.Client"),
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
        with patch("uipath.tracing._otel_exporters.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://custom.uipath.com/org/tenant"

    # Test with environment variable set but with no trailing slash
    with patch.dict(
        os.environ, {"UIPATH_URL": "https://custom.uipath.com/org/tenant"}, clear=True
    ):
        with patch("uipath.tracing._otel_exporters.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://custom.uipath.com/org/tenant"

    # Test with no environment variable
    with patch.dict(os.environ, {}, clear=True):
        with patch("uipath.tracing._otel_exporters.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://cloud.uipath.com/dummyOrg/dummyTennant"


def test_send_with_retries_success():
    """Test _send_with_retries method with successful response."""
    with patch("uipath.tracing._otel_exporters.Client"):
        exporter = LlmOpsHttpExporter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        exporter.http_client.post.return_value = mock_response  # type: ignore

        result = exporter._send_with_retries("http://example.com", [{"span": "data"}])

        assert result == SpanExportResult.SUCCESS
        exporter.http_client.post.assert_called_once_with(  # type: ignore
            "http://example.com", json=[{"span": "data"}]
        )
