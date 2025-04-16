import inspect
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
        attributes = json.loads(uipath_span.attributes)
        assert attributes["key1"] == "value1"
        assert attributes["key2"] == 123

        # Test with error status
        mock_span.status.status_code = StatusCode.ERROR
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert uipath_span.status == 2  # Error

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

    def test_format_args_for_trace(self):
        # Simple function signature
        def func1(a, b, c=3):
            pass

        sig = inspect.signature(func1)
        result = _SpanUtils.format_args_for_trace(sig, 1, 2)
        assert result == {"a": 1, "b": 2, "c": 3}

        # Test with kwargs
        result = _SpanUtils.format_args_for_trace(sig, 1, c=4, b=5)
        assert result == {"a": 1, "b": 5, "c": 4}

        # Function with self parameter
        class TestClass:
            def method(self, x, y):
                pass

        sig = inspect.signature(TestClass.method)
        result = _SpanUtils.format_args_for_trace(sig, TestClass(), 10, 20)
        assert result == {"x": 10, "y": 20}

        # Function with **kwargs
        def func2(a, **kwargs):
            pass

        sig = inspect.signature(func2)
        result = _SpanUtils.format_args_for_trace(sig, 1, b=2, c=3)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_format_args_for_trace_json(self):
        def sample_func(a, b=None):
            pass

        sig = inspect.signature(sample_func)

        # Test with simple args
        json_result = _SpanUtils.format_args_for_trace_json(sig, 1, b="test")
        parsed = json.loads(json_result)
        assert parsed == {"a": 1, "b": "test"}

        # Test with non-serializable object
        class NonSerializable:
            pass

        json_result = _SpanUtils.format_args_for_trace_json(sig, 1, b=NonSerializable())
        # Should not raise exception
        parsed = json.loads(json_result)
        assert parsed["a"] == 1
        assert "b" in parsed  # The value will be a string representation
