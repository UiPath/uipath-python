import json
import os
import uuid
from datetime import datetime
from unittest.mock import Mock, patch

from opentelemetry.sdk.trace import Span as OTelSpan
from opentelemetry.trace import SpanContext, StatusCode

from uipath.tracing._utils import UiPathSpan, _SpanUtils


class TestUUIDMapper:
    def test_trace_id_to_uuid4(self):
        """Test that trace_id_to_uuid4 converts trace IDs to valid UUID4 format."""
        trace_id = int("1234567890ABCDEF1234567890ABCDEF", 16)  # 128-bit trace ID

        # Convert to UUID
        uuid_obj = _SpanUtils.trace_id_to_uuid4(trace_id)

        # Check that it's a valid UUID4
        assert uuid_obj.version == 4
        assert uuid_obj.variant == uuid.RFC_4122

        # Check that the same trace_id always maps to the same UUID
        uuid_obj2 = _SpanUtils.trace_id_to_uuid4(trace_id)
        assert uuid_obj == uuid_obj2

    def test_span_id_to_uuid4_deterministic(self):
        """Test that span_id_to_uuid4 is deterministic for the same span_id."""
        span_id = 0x1234567890ABCDEF  # 64-bit span ID

        # Convert to UUID twice
        uuid_obj1 = _SpanUtils.span_id_to_uuid4(span_id)
        uuid_obj2 = _SpanUtils.span_id_to_uuid4(span_id)

        # They should be the same
        assert uuid_obj1 == uuid_obj2

        # Check that it's a valid UUID4
        assert uuid_obj1.version == 4
        assert uuid_obj1.variant == uuid.RFC_4122

    def test_span_id_to_uuid4_different_ids(self):
        """Test that different span_ids map to different UUIDs."""
        span_id1 = 0x1234567890ABCDEF  # 64-bit span ID
        span_id2 = 0x2345678901BCDEF0  # Different 64-bit span ID

        # Convert to UUIDs
        uuid_obj1 = _SpanUtils.span_id_to_uuid4(span_id1)
        uuid_obj2 = _SpanUtils.span_id_to_uuid4(span_id2)

        # They should be different
        assert uuid_obj1 != uuid_obj2

        # But both should be valid UUID4
        assert uuid_obj1.version == 4
        assert uuid_obj1.variant == uuid.RFC_4122
        assert uuid_obj2.version == 4
        assert uuid_obj2.variant == uuid.RFC_4122


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
    def test_otel_span_to_uipath_span_with_env_trace_id(self):
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

        # Verify the trace ID is taken from environment
        assert str(uipath_span.trace_id) == "00000000-0000-4000-8000-000000000000"

    @patch.dict(os.environ, {"UIPATH_PROCESS_VERSION": "1.0.0"})
    def test_uipath_span_agent_version_from_env(self):
        """Test that AgentVersion is populated from UIPATH_PROCESS_VERSION env variable."""
        # Create a UiPathSpan
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            name="test-span",
            attributes="{}",
        )

        # Verify the agent_version is taken from environment
        assert span.agent_version == "1.0.0"

        # Verify it's included in the dict output
        span_dict = span.to_dict()
        assert span_dict["AgentVersion"] == "1.0.0"

    @patch.dict(os.environ, {}, clear=True)
    def test_uipath_span_agent_version_missing(self):
        """Test that AgentVersion is None when env variable is not set."""
        # Create a UiPathSpan
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            name="test-span",
            attributes="{}",
        )

        # Verify the agent_version is None
        assert span.agent_version is None

        # Verify it's included in the dict output as None
        span_dict = span.to_dict()
        assert span_dict["AgentVersion"] is None

    @patch.dict(os.environ, {"UIPATH_IS_DEBUG": "true"})
    def test_uipath_span_execution_type_debug_mode(self):
        """Test that ExecutionType is 0 when UIPATH_IS_DEBUG is true."""
        # Create a UiPathSpan
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            name="test-span",
            attributes="{}",
        )

        # Verify execution_type is 0 (debug mode)
        assert span.execution_type == 0

        # Verify it's included in the dict output
        span_dict = span.to_dict()
        assert span_dict["ExecutionType"] == 0

    @patch.dict(os.environ, {"UIPATH_IS_DEBUG": "True"})
    def test_uipath_span_execution_type_debug_mode_uppercase(self):
        """Test that ExecutionType is 0 when UIPATH_IS_DEBUG is True (case-insensitive)."""
        # Create a UiPathSpan
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            name="test-span",
            attributes="{}",
        )

        # Verify execution_type is 0 (debug mode)
        assert span.execution_type == 0

    @patch.dict(os.environ, {"UIPATH_IS_DEBUG": "false"})
    def test_uipath_span_execution_type_production_mode(self):
        """Test that ExecutionType is 1 when UIPATH_IS_DEBUG is false."""
        # Create a UiPathSpan
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            name="test-span",
            attributes="{}",
        )

        # Verify execution_type is 1 (production mode)
        assert span.execution_type == 1

        # Verify it's included in the dict output
        span_dict = span.to_dict()
        assert span_dict["ExecutionType"] == 1

    @patch.dict(os.environ, {}, clear=True)
    def test_uipath_span_execution_type_default(self):
        """Test that ExecutionType defaults to 1 when UIPATH_IS_DEBUG is not set."""
        # Create a UiPathSpan
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=uuid.uuid4(),
            name="test-span",
            attributes="{}",
        )

        # Verify execution_type is 1 (production mode, default)
        assert span.execution_type == 1

        # Verify it's included in the dict output
        span_dict = span.to_dict()
        assert span_dict["ExecutionType"] == 1

    @patch.dict(
        os.environ,
        {
            "UIPATH_PROCESS_VERSION": "2.1.5",
            "UIPATH_IS_DEBUG": "true",
        },
    )
    def test_otel_span_to_uipath_span_includes_new_fields(self):
        """Test that converting OTel span includes AgentVersion and ExecutionType."""
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
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify new fields are populated from environment
        assert uipath_span.agent_version == "2.1.5"
        assert uipath_span.execution_type == 0

        # Verify they're included in the dict output
        span_dict = uipath_span.to_dict()
        assert span_dict["AgentVersion"] == "2.1.5"
        assert span_dict["ExecutionType"] == 0
