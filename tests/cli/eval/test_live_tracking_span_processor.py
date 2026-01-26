"""Tests for LiveTrackingSpanProcessor."""

import threading
import time
from typing import Any
from unittest.mock import Mock

import pytest
from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span
from uipath.runtime import UiPathRuntimeFactorySettings

from uipath._cli._evals._live_tracking_processor import LiveTrackingSpanProcessor
from uipath.tracing import SpanStatus


class TestLiveTrackingSpanProcessor:
    """Test suite for LiveTrackingSpanProcessor."""

    @pytest.fixture
    def mock_exporter(self):
        """Create a mock LlmOpsHttpExporter."""
        exporter = Mock()
        exporter.upsert_span = Mock()
        return exporter

    @pytest.fixture
    def processor_no_filter(self, mock_exporter):
        """Create a LiveTrackingSpanProcessor with no filtering (settings=None)."""
        return LiveTrackingSpanProcessor(mock_exporter, settings=None)

    @pytest.fixture
    def processor_with_filter(self, mock_exporter):
        """Create a LiveTrackingSpanProcessor with custom instrumentation filter."""
        from uipath.core.tracing.types import UiPathTraceSettings

        settings = UiPathRuntimeFactorySettings(
            trace_settings=UiPathTraceSettings(
                span_filter=lambda span: bool(
                    span.attributes
                    and span.attributes.get("uipath.custom_instrumentation")
                )
            )
        )
        return LiveTrackingSpanProcessor(mock_exporter, settings=settings)

    def create_mock_span(self, attributes: dict[str, Any] | None = None):
        """Create a mock span with attributes."""
        span = Mock(spec=Span)
        span.attributes = attributes or {}
        return span

    def create_mock_readable_span(self, attributes: dict[str, Any] | None = None):
        """Create a mock ReadableSpan with attributes."""
        span = Mock(spec=ReadableSpan)
        span.attributes = attributes or {}
        return span

    def test_init(self, mock_exporter):
        """Test processor initialization."""
        processor = LiveTrackingSpanProcessor(mock_exporter)

        assert processor.exporter == mock_exporter
        assert processor.span_status == SpanStatus

    def test_init_with_no_settings(self, mock_exporter):
        """Test processor initialization with no settings."""
        processor = LiveTrackingSpanProcessor(mock_exporter, settings=None)

        assert processor.span_filter is None  # No filtering

    def test_init_with_settings_and_filter(self, mock_exporter):
        """Test processor initialization with settings containing filter."""
        from uipath.core.tracing.types import UiPathTraceSettings

        settings = UiPathRuntimeFactorySettings(
            trace_settings=UiPathTraceSettings(
                span_filter=lambda span: bool(
                    span.attributes and span.attributes.get("test")
                )
            )
        )
        processor = LiveTrackingSpanProcessor(mock_exporter, settings=settings)

        assert processor.span_filter is not None

    # Tests for no filter (all spans pass through)

    def test_on_start_no_filter_accepts_all(self, processor_no_filter, mock_exporter):
        """Test on_start with no filter accepts all spans."""
        span = self.create_mock_span({"span_type": "agent"})

        processor_no_filter.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_end_no_filter_accepts_all(self, processor_no_filter, mock_exporter):
        """Test on_end with no filter accepts all spans."""
        span = self.create_mock_readable_span({"span_type": "agent"})

        processor_no_filter.on_end(span)

        mock_exporter.upsert_span.assert_called_once_with(span)

    # Tests for custom instrumentation filter

    def test_on_start_with_filter_accepts_matching(
        self, processor_with_filter, mock_exporter
    ):
        """Test on_start with filter accepts matching spans."""
        span = self.create_mock_span({"uipath.custom_instrumentation": True})

        processor_with_filter.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_filter_rejects_non_matching(
        self, processor_with_filter, mock_exporter
    ):
        """Test on_start with filter rejects non-matching spans."""
        span = self.create_mock_span({"span_type": "agent"})

        processor_with_filter.on_start(span, None)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_end_with_filter_accepts_matching(
        self, processor_with_filter, mock_exporter
    ):
        """Test on_end with filter accepts matching spans."""
        span = self.create_mock_readable_span({"uipath.custom_instrumentation": True})

        processor_with_filter.on_end(span)

        mock_exporter.upsert_span.assert_called_once_with(span)

    def test_on_end_with_filter_rejects_non_matching(
        self, processor_with_filter, mock_exporter
    ):
        """Test on_end with filter rejects non-matching spans."""
        span = self.create_mock_readable_span({"span_type": "agent"})

        processor_with_filter.on_end(span)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_start_with_no_attributes(self, processor_with_filter, mock_exporter):
        """Test on_start with filter handles spans with no attributes."""
        span = self.create_mock_span(None)

        processor_with_filter.on_start(span, None)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_end_with_no_attributes(self, processor_with_filter, mock_exporter):
        """Test on_end with filter handles spans with no attributes."""
        span = self.create_mock_readable_span(None)

        processor_with_filter.on_end(span)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_start_exception_handling(self, processor_no_filter, mock_exporter):
        """Test on_start handles exceptions gracefully."""
        span = self.create_mock_span({"span_type": "eval"})
        mock_exporter.upsert_span.side_effect = Exception("Network error")

        # Should not raise exception
        processor_no_filter.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once()

    def test_on_end_exception_handling(self, processor_no_filter, mock_exporter):
        """Test on_end handles exceptions gracefully."""
        span = self.create_mock_readable_span({"span_type": "eval"})
        mock_exporter.upsert_span.side_effect = Exception("Network error")

        # Should not raise exception
        processor_no_filter.on_end(span)

        mock_exporter.upsert_span.assert_called_once()

    def test_shutdown(self, processor_no_filter):
        """Test shutdown method."""
        # Should not raise exception
        processor_no_filter.shutdown()

    def test_force_flush(self, processor_no_filter):
        """Test force_flush method."""
        result = processor_no_filter.force_flush()
        assert result is True

    def test_force_flush_with_timeout(self, processor_no_filter):
        """Test force_flush with custom timeout."""
        result = processor_no_filter.force_flush(timeout_millis=5000)
        assert result is True

    def test_on_start_with_parent_context(self, processor_no_filter, mock_exporter):
        """Test on_start with parent context."""
        span = self.create_mock_span({"span_type": "eval"})
        parent_context = Mock(spec=context_api.Context)

        processor_no_filter.on_start(span, parent_context)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    # Tests for ThreadPoolExecutor behavior

    def test_thread_pool_executor_used(self, mock_exporter):
        """Test that processor uses ThreadPoolExecutor for async operations."""
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        # Verify executor exists
        assert hasattr(processor, "executor")
        assert processor.executor is not None

        # Submit task and verify it's non-blocking
        start_time = time.time()
        processor.on_start(span, None)
        elapsed = time.time() - start_time

        # Should return immediately (< 0.05 seconds)
        assert elapsed < 0.05, f"on_start blocked for {elapsed} seconds"

    def test_handles_exceptions_gracefully(self, mock_exporter):
        """Test that exceptions in background threads don't crash."""
        mock_exporter.upsert_span = Mock(side_effect=Exception("Network error"))
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        # Should not raise exception
        processor.on_start(span, None)
        # Wait for background thread to process
        time.sleep(0.2)

        # Main thread should still be alive
        assert threading.current_thread().is_alive()

    def test_upsert_span_async_with_status_override(self, mock_exporter):
        """Test _upsert_span_async correctly passes status_override."""
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        processor._upsert_span_async(span, status_override=SpanStatus.RUNNING)

        # Wait for background thread to complete
        time.sleep(0.2)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_upsert_span_async_without_status_override(self, mock_exporter):
        """Test _upsert_span_async without status_override."""
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_readable_span({"span_type": "eval"})

        processor._upsert_span_async(span, status_override=None)

        # Wait for background thread to complete
        time.sleep(0.2)

        mock_exporter.upsert_span.assert_called_once_with(span)

    def test_processor_initialization_with_custom_max_workers(self, mock_exporter):
        """Test processor can be initialized with custom max_workers."""
        processor = LiveTrackingSpanProcessor(mock_exporter, max_workers=15)
        assert processor.executor._max_workers == 15

    def test_exception_in_background_thread_does_not_crash(self, mock_exporter):
        """Test that exceptions in background threads don't crash the main thread."""
        mock_exporter.upsert_span = Mock(side_effect=Exception("Background error"))
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        # Should not raise exception
        processor.on_start(span, None)
        time.sleep(0.2)  # Wait for background thread

        # Main thread should still be alive
        assert threading.current_thread().is_alive()

    # Tests for ThreadPoolExecutor and max_workers

    def test_processor_with_custom_max_workers(self, mock_exporter):
        """Test processor can be initialized with custom max_workers."""
        processor = LiveTrackingSpanProcessor(mock_exporter, max_workers=20)
        assert processor.executor._max_workers == 20

    def test_processor_default_max_workers(self, mock_exporter):
        """Test processor uses default max_workers of 10."""
        processor = LiveTrackingSpanProcessor(mock_exporter)
        assert processor.executor._max_workers == 10

    def test_thread_pool_caps_concurrent_threads(self, mock_exporter):
        """Test that thread pool caps concurrent threads to max_workers."""
        concurrent_calls = []
        max_concurrent = 0

        def slow_upsert(*args, **kwargs):
            concurrent_calls.append(1)
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, len(concurrent_calls))
            time.sleep(0.5)
            concurrent_calls.pop()

        mock_exporter.upsert_span = Mock(side_effect=slow_upsert)
        processor = LiveTrackingSpanProcessor(mock_exporter, max_workers=3)

        # Submit 10 tasks rapidly
        spans = [
            self.create_mock_span({"span_type": "eval", "id": str(i)})
            for i in range(10)
        ]

        for span in spans:
            processor.on_start(span, None)

        # Wait for all to complete
        time.sleep(2)

        # Max concurrent should not exceed max_workers (3)
        assert max_concurrent <= 3, (
            f"Max concurrent was {max_concurrent}, expected <= 3"
        )

    def test_shutdown_waits_for_pending_tasks(self, mock_exporter):
        """Test that shutdown properly cleans up the thread pool."""
        processor = LiveTrackingSpanProcessor(mock_exporter, max_workers=2)

        # Submit some tasks
        for i in range(3):
            span = self.create_mock_span({"span_type": "eval", "id": str(i)})
            processor.on_start(span, None)

        # Shutdown should complete without errors
        processor.shutdown()

        # Verify executor is shutdown (calling shutdown multiple times should be safe)
        processor.shutdown()  # Should not raise

    def test_multiple_processors_independent_thread_pools(self, mock_exporter):
        """Test that multiple processors have independent thread pools."""
        processor1 = LiveTrackingSpanProcessor(mock_exporter, max_workers=5)
        processor2 = LiveTrackingSpanProcessor(mock_exporter, max_workers=15)

        assert processor1.executor != processor2.executor
        assert processor1.executor._max_workers == 5
        assert processor2.executor._max_workers == 15

    def test_thread_pool_name_prefix(self, mock_exporter):
        """Test that thread pool uses correct name prefix."""
        processor = LiveTrackingSpanProcessor(mock_exporter)
        # ThreadPoolExecutor sets _thread_name_prefix
        assert processor.executor._thread_name_prefix == "span-upsert"

    def test_resource_exhaustion_prevention(self, mock_exporter):
        """Test that max_workers prevents resource exhaustion."""
        call_times = []

        def timed_upsert(*args, **kwargs):
            call_times.append(time.time())
            time.sleep(0.3)

        mock_exporter.upsert_span = Mock(side_effect=timed_upsert)
        # Very low max_workers to test queueing
        processor = LiveTrackingSpanProcessor(mock_exporter, max_workers=2)

        # Submit 6 tasks
        for i in range(6):
            span = self.create_mock_span({"span_type": "eval", "id": str(i)})
            processor.on_start(span, None)

        # Wait for all to complete
        time.sleep(2)

        # All 6 should complete
        assert len(call_times) == 6

        # With max_workers=2 and 0.3s per task, we should see batching
        # Sort by time to analyze execution pattern
        call_times.sort()
        # First 2 should start quickly, next batch should wait
        assert call_times[1] - call_times[0] < 0.2  # First batch starts together
        assert (
            call_times[3] - call_times[1] > 0.2
        )  # Second batch waits for first to finish

    def test_shutdown_can_be_called_multiple_times(self, mock_exporter):
        """Test that shutdown can be safely called multiple times."""
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        processor.on_start(span, None)
        time.sleep(0.1)

        # Multiple shutdowns should not raise exceptions
        processor.shutdown()
        processor.shutdown()
        processor.shutdown()

    def test_executor_properly_initialized(self, mock_exporter):
        """Test that ThreadPoolExecutor is properly initialized."""
        processor = LiveTrackingSpanProcessor(mock_exporter, max_workers=7)

        assert processor.executor is not None
        assert hasattr(processor.executor, "submit")
        assert hasattr(processor.executor, "shutdown")
        assert processor.executor._max_workers == 7
