import json
import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from opentelemetry.sdk.trace import Span as OTelSpan
from opentelemetry.trace import SpanContext, StatusCode

from uipath.tracing._utils import UiPathSpan, _SpanUtils


class TestNormalizeIds:
    """Tests for OTEL ID normalization functions."""

    def test_normalize_trace_id_from_hex(self):
        """Test normalizing a 32-char hex trace ID."""
        trace_id = "1234567890abcdef1234567890abcdef"
        result = _SpanUtils.normalize_trace_id(trace_id)
        assert result == "1234567890abcdef1234567890abcdef"

    def test_normalize_trace_id_from_uuid(self):
        """Test normalizing a UUID format trace ID to hex."""
        trace_id = "12345678-90ab-cdef-1234-567890abcdef"
        result = _SpanUtils.normalize_trace_id(trace_id)
        assert result == "1234567890abcdef1234567890abcdef"

    def test_normalize_trace_id_uppercase(self):
        """Test normalizing uppercase hex to lowercase."""
        trace_id = "1234567890ABCDEF1234567890ABCDEF"
        result = _SpanUtils.normalize_trace_id(trace_id)
        assert result == "1234567890abcdef1234567890abcdef"

    def test_normalize_trace_id_invalid_length(self):
        """Test that invalid length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid trace ID format"):
            _SpanUtils.normalize_trace_id("1234")

    def test_normalize_span_id_from_hex(self):
        """Test normalizing a 16-char hex span ID."""
        span_id = "1234567890abcdef"
        result = _SpanUtils.normalize_span_id(span_id)
        assert result == "1234567890abcdef"

    def test_normalize_span_id_from_uuid(self):
        """Test normalizing a UUID format span ID (takes last 16 chars)."""
        span_id = "00000000-0000-0000-1234-567890abcdef"
        result = _SpanUtils.normalize_span_id(span_id)
        assert result == "1234567890abcdef"

    def test_normalize_span_id_uppercase(self):
        """Test normalizing uppercase hex to lowercase."""
        span_id = "1234567890ABCDEF"
        result = _SpanUtils.normalize_span_id(span_id)
        assert result == "1234567890abcdef"

    def test_normalize_span_id_invalid_length(self):
        """Test that invalid length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid span ID format"):
            _SpanUtils.normalize_span_id("1234")


class TestSpanUtils:
    @patch.dict(
        os.environ,
        {
            "UIPATH_ORGANIZATION_ID": "test-org",
            "UIPATH_TENANT_ID": "test-tenant",
            "UIPATH_FOLDER_KEY": "test-folder",
            "UIPATH_PROCESS_UUID": "test-process",
            "UIPATH_JOB_KEY": "test-job",
        },
    )
    def test_otel_span_to_uipath_span(self):
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {
            "key1": "value1",
            "key2": 123,
            "span_type": "CustomSpanType",
        }
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000  # 1ms later

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify the conversion
        assert isinstance(uipath_span, UiPathSpan)
        assert uipath_span.name == "test-span"
        assert uipath_span.status == 1  # OK
        assert uipath_span.span_type == "CustomSpanType"

        # Verify IDs are in OTEL hex format
        assert uipath_span.trace_id == "123456789abcdef0123456789abcdef0"  # 32-char hex
        assert uipath_span.id == "0123456789abcdef"  # 16-char hex
        assert uipath_span.parent_id is None

        # Verify attributes
        attributes_value = uipath_span.attributes
        attributes = (
            json.loads(attributes_value)
            if isinstance(attributes_value, str)
            else attributes_value
        )
        assert attributes["key1"] == "value1"
        assert attributes["key2"] == 123

        # Test with error status
        mock_span.status.description = "Test error description"
        mock_span.status.status_code = StatusCode.ERROR
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert uipath_span.status == 2  # Error

    @patch.dict(
        os.environ,
        {
            "UIPATH_ORGANIZATION_ID": "test-org",
            "UIPATH_TENANT_ID": "test-tenant",
        },
    )
    def test_otel_span_to_uipath_span_optimized_path(self):
        """Test the optimized path where attributes are kept as dict."""
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {
            "key1": "value1",
            "key2": 123,
        }
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        # Test optimized path: serialize_attributes=False
        uipath_span = _SpanUtils.otel_span_to_uipath_span(
            mock_span, serialize_attributes=False
        )

        # Verify attributes is a dict (not JSON string)
        assert isinstance(uipath_span.attributes, dict)
        assert uipath_span.attributes["key1"] == "value1"
        assert uipath_span.attributes["key2"] == 123

        # Test to_dict with serialize_attributes=False
        span_dict = uipath_span.to_dict(serialize_attributes=False)
        assert isinstance(span_dict["Attributes"], dict)
        assert span_dict["Attributes"]["key1"] == "value1"

        # Test to_dict with serialize_attributes=True
        span_dict_serialized = uipath_span.to_dict(serialize_attributes=True)
        assert isinstance(span_dict_serialized["Attributes"], str)
        attrs = json.loads(span_dict_serialized["Attributes"])
        assert attrs["key1"] == "value1"
        assert attrs["key2"] == 123

    @patch.dict(os.environ, {"UIPATH_TRACE_ID": "00000000-0000-4000-8000-000000000000"})
    def test_otel_span_to_uipath_span_with_env_trace_id_uuid_format(self):
        """Test that UUID format UIPATH_TRACE_ID is normalized to hex."""
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000  # 1ms later

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify the trace ID is normalized to 32-char hex format
        assert uipath_span.trace_id == "00000000000040008000000000000000"

    @patch.dict(os.environ, {"UIPATH_TRACE_ID": "1234567890abcdef1234567890abcdef"})
    def test_otel_span_to_uipath_span_with_env_trace_id_hex_format(self):
        """Test that hex format UIPATH_TRACE_ID is used directly."""
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000  # 1ms later

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify the trace ID is used as-is (lowercase)
        assert uipath_span.trace_id == "1234567890abcdef1234567890abcdef"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_includes_execution_type(self):
        """Test that executionType from attributes becomes top-level ExecutionType."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"executionType": 0}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["ExecutionType"] == 0
        assert uipath_span.execution_type == 0

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_includes_agent_version(self):
        """Test that agentVersion from attributes becomes top-level AgentVersion."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"agentVersion": "2.0.0"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["AgentVersion"] == "2.0.0"
        assert uipath_span.agent_version == "2.0.0"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_execution_type_and_agent_version_both(self):
        """Test that both executionType and agentVersion are extracted together."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "Agent run - Agent"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"executionType": 1, "agentVersion": "1.0.0"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["ExecutionType"] == 1
        assert span_dict["AgentVersion"] == "1.0.0"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_missing_execution_type_and_agent_version(self):
        """Test that missing executionType and agentVersion default to None."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"someOtherAttr": "value"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["ExecutionType"] is None
        assert span_dict["AgentVersion"] is None

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_source_defaults_to_robots(self):
        """Test that Source defaults to 4 (Robots) and ignores attributes.source."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        # source in attributes should NOT override top-level Source
        mock_span.attributes = {"source": "runtime"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        # Top-level Source should be 4 (Robots), string "runtime" is ignored
        assert uipath_span.source == 4
        assert span_dict["Source"] == 4

        # attributes.source string should still be in Attributes JSON
        attrs = json.loads(span_dict["Attributes"])
        assert attrs["source"] == "runtime"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_source_override_with_uipath_source(self):
        """Test that uipath.source attribute overrides default (for low-code agents)."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        # uipath.source=1 (Agents) overrides default of 4 (Robots)
        mock_span.attributes = {"uipath.source": 1, "source": "runtime"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        # uipath.source overrides - low-code agents use 1 (Agents)
        assert uipath_span.source == 1
        assert span_dict["Source"] == 1

        # String source still in Attributes JSON
        attrs = json.loads(span_dict["Attributes"])
        assert attrs["source"] == "runtime"
