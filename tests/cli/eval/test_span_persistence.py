"""Tests for span persistence: serialization roundtrip and processor fallback.

Tests cover:
1. serialize_span / deserialize_span roundtrip preserves all span data
2. ExecutionSpanProcessor.on_start() fallback to execution_id_context ContextVar
"""

from typing import Any
from unittest.mock import Mock, patch

from opentelemetry.sdk.trace import Event, ReadableSpan, Span
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags

from uipath._cli._evals._span_collection import ExecutionSpanCollector
from uipath._cli._evals._span_persistence_helpers import (
    deserialize_span,
    serialize_span,
)
from uipath._cli._evals.mocks.mocks import execution_id_context


def _make_span_context(
    trace_id: int = 0xABCDEF1234567890, span_id: int = 0x1234567890ABCDEF
) -> SpanContext:
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(0x01),
    )


def _make_full_span() -> ReadableSpan:
    """Create a ReadableSpan with all fields populated."""
    return ReadableSpan(
        name="test-span",
        context=_make_span_context(),
        parent=_make_span_context(trace_id=0xABCDEF1234567890, span_id=0xFEDCBA),
        attributes={
            "execution.id": "exec-123",
            "span_type": "evaluation",
            "score": 0.95,
            "count": 42,
            "active": True,
        },
        events=[
            Event(
                name="test-event",
                attributes={"key": "value", "num": 10},
                timestamp=1000000000,
            ),
        ],
        status=Status(StatusCode.OK),
        start_time=5000000000,
        end_time=6000000000,
        kind=SpanKind.INTERNAL,
    )


# --- Serialization Roundtrip Tests ---


class TestSerializationRoundtrip:
    """Tests that serialize_span -> deserialize_span preserves all span data."""

    def test_roundtrip_preserves_name(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.name == "test-span"

    def test_roundtrip_preserves_context(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.context is not None
        assert span.context is not None
        assert result.context.trace_id == span.context.trace_id
        assert result.context.span_id == span.context.span_id
        assert int(result.context.trace_flags) == int(span.context.trace_flags)

    def test_roundtrip_preserves_parent(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.parent is not None
        assert span.parent is not None
        assert result.parent.trace_id == span.parent.trace_id
        assert result.parent.span_id == span.parent.span_id

    def test_roundtrip_preserves_attributes(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.attributes is not None
        assert result.attributes["execution.id"] == "exec-123"
        assert result.attributes["span_type"] == "evaluation"
        assert result.attributes["score"] == 0.95
        assert result.attributes["count"] == 42
        assert result.attributes["active"] is True

    def test_roundtrip_preserves_tuple_attributes(self) -> None:
        """Tuples are converted to lists during serialization."""
        span = ReadableSpan(
            name="tuple-span",
            attributes={"tags": ("a", "b", "c")},
        )
        result = deserialize_span(serialize_span(span))
        assert result.attributes is not None
        assert result.attributes["tags"] == ["a", "b", "c"]

    def test_roundtrip_preserves_events(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert len(result.events) == 1
        event = result.events[0]
        assert event.name == "test-event"
        assert event.attributes is not None
        assert event.attributes["key"] == "value"
        assert event.attributes["num"] == 10
        assert event.timestamp == 1000000000

    def test_roundtrip_preserves_status(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.status.status_code == StatusCode.OK

    def test_roundtrip_preserves_error_status(self) -> None:
        span = ReadableSpan(
            name="error-span",
            status=Status(StatusCode.ERROR, "something failed"),
        )
        result = deserialize_span(serialize_span(span))
        assert result.status.status_code == StatusCode.ERROR
        assert result.status.description == "something failed"

    def test_roundtrip_preserves_timestamps(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.start_time == 5000000000
        assert result.end_time == 6000000000

    def test_roundtrip_preserves_kind(self) -> None:
        span = _make_full_span()
        result = deserialize_span(serialize_span(span))
        assert result.kind == SpanKind.INTERNAL

    def test_roundtrip_span_with_no_parent(self) -> None:
        span = ReadableSpan(
            name="orphan-span",
            context=_make_span_context(),
            parent=None,
            attributes={"key": "val"},
        )
        result = deserialize_span(serialize_span(span))
        assert result.parent is None
        assert result.context is not None

    def test_roundtrip_span_with_no_events(self) -> None:
        span = ReadableSpan(
            name="no-events-span",
            attributes={"key": "val"},
        )
        result = deserialize_span(serialize_span(span))
        assert len(result.events) == 0

    def test_roundtrip_span_with_no_attributes(self) -> None:
        span = ReadableSpan(name="minimal-span")
        result = deserialize_span(serialize_span(span))
        assert result.name == "minimal-span"

    def test_roundtrip_multiple_events(self) -> None:
        span = ReadableSpan(
            name="multi-event-span",
            events=[
                Event(name="event-1", attributes={"a": 1}, timestamp=100),
                Event(name="event-2", attributes={"b": 2}, timestamp=200),
                Event(name="event-3", attributes={}, timestamp=300),
            ],
        )
        result = deserialize_span(serialize_span(span))
        assert len(result.events) == 3
        assert result.events[0].name == "event-1"
        assert result.events[1].name == "event-2"
        assert result.events[2].name == "event-3"


# --- ExecutionSpanProcessor Fallback Tests ---


class TestExecutionSpanProcessorFallback:
    """Tests for ExecutionSpanProcessor.on_start() execution_id_context fallback."""

    def _create_processor(self) -> tuple[Any, ExecutionSpanCollector, Mock]:
        from uipath._cli._evals._runtime import ExecutionSpanProcessor

        mock_exporter = Mock(spec=SpanExporter)
        collector = ExecutionSpanCollector()
        processor = ExecutionSpanProcessor(mock_exporter, collector)
        return processor, collector, mock_exporter

    def _create_mock_span(self, attributes: dict[str, Any] | None = None) -> Mock:
        span = Mock(spec=Span)
        span.attributes = attributes or {}
        return span

    @patch("uipath._cli._evals._runtime.UiPathExecutionBatchTraceProcessor.on_start")
    def test_span_with_execution_id_added_to_collector(
        self, mock_super_on_start: Mock
    ) -> None:
        processor, collector, _ = self._create_processor()
        span = self._create_mock_span({"execution.id": "exec-123"})

        processor.on_start(span)

        spans = collector.get_spans("exec-123")
        assert len(spans) == 1
        assert spans[0] is span

    @patch("uipath._cli._evals._runtime.UiPathExecutionBatchTraceProcessor.on_start")
    def test_span_without_execution_id_not_added(
        self, mock_super_on_start: Mock
    ) -> None:
        processor, collector, _ = self._create_processor()
        span = self._create_mock_span({"span_type": "agent"})

        # Ensure context var is empty
        token = execution_id_context.set(None)
        try:
            processor.on_start(span)
        finally:
            execution_id_context.reset(token)

        assert collector.get_spans("") == []

    @patch("uipath._cli._evals._runtime.UiPathExecutionBatchTraceProcessor.on_start")
    def test_fallback_sets_execution_id_from_context_var(
        self, mock_super_on_start: Mock
    ) -> None:
        """Core bug fix test: NonRecordingSpan parent doesn't propagate execution.id,
        so the processor should fall back to execution_id_context."""
        processor, collector, _ = self._create_processor()
        span = self._create_mock_span({"span_type": "agent"})

        # After set_attribute, the mock's attributes dict should reflect the change
        def side_effect_set_attr(key: str, value: Any) -> None:
            span.attributes[key] = value

        span.set_attribute = Mock(side_effect=side_effect_set_attr)

        token = execution_id_context.set("exec-from-context")
        try:
            processor.on_start(span)
        finally:
            execution_id_context.reset(token)

        # Verify set_attribute was called with the context var value
        span.set_attribute.assert_called_once_with("execution.id", "exec-from-context")

        # Verify span was added to collector
        spans = collector.get_spans("exec-from-context")
        assert len(spans) == 1
        assert spans[0] is span

    @patch("uipath._cli._evals._runtime.UiPathExecutionBatchTraceProcessor.on_start")
    def test_no_fallback_when_context_var_empty(
        self, mock_super_on_start: Mock
    ) -> None:
        processor, collector, _ = self._create_processor()
        span = self._create_mock_span({"span_type": "agent"})

        token = execution_id_context.set(None)
        try:
            processor.on_start(span)
        finally:
            execution_id_context.reset(token)

        # Span should not have been added anywhere
        span.set_attribute.assert_not_called()

    @patch("uipath._cli._evals._runtime.UiPathExecutionBatchTraceProcessor.on_start")
    def test_span_with_non_string_execution_id_not_added(
        self, mock_super_on_start: Mock
    ) -> None:
        processor, collector, _ = self._create_processor()
        span = self._create_mock_span({"execution.id": 12345})

        processor.on_start(span)

        # Non-string execution.id should not be added to collector
        assert collector.get_spans("12345") == []
