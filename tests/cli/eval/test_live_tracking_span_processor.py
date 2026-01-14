"""Tests for LiveTrackingSpanProcessor in _runtime.py."""

import threading
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span

from uipath._cli._evals._runtime import LiveTrackingSpanProcessor
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
    def processor(self, mock_exporter):
        """Create a LiveTrackingSpanProcessor with mock exporter."""
        return LiveTrackingSpanProcessor(mock_exporter)

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

    def test_on_start_with_eval_span_type(self, processor, mock_exporter):
        """Test on_start is called for eval span type."""
        span = self.create_mock_span({"span_type": "eval"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_evaluator_span_type(self, processor, mock_exporter):
        """Test on_start is called for evaluator span type."""
        span = self.create_mock_span({"span_type": "evaluator"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_evaluation_span_type(self, processor, mock_exporter):
        """Test on_start is called for evaluation span type."""
        span = self.create_mock_span({"span_type": "evaluation"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_eval_set_run_span_type(self, processor, mock_exporter):
        """Test on_start is called for eval_set_run span type."""
        span = self.create_mock_span({"span_type": "eval_set_run"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_eval_output_span_type(self, processor, mock_exporter):
        """Test on_start is called for evalOutput span type."""
        span = self.create_mock_span({"span_type": "evalOutput"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_execution_id(self, processor, mock_exporter):
        """Test on_start is called for span with execution.id."""
        span = self.create_mock_span({"execution.id": "test-exec-id"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_on_start_with_non_eval_span(self, processor, mock_exporter):
        """Test on_start is NOT called for non-eval spans."""
        span = self.create_mock_span({"span_type": "agent"})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_start_with_no_attributes(self, processor, mock_exporter):
        """Test on_start is NOT called when span has no attributes."""
        span = self.create_mock_span(None)

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_start_with_empty_attributes(self, processor, mock_exporter):
        """Test on_start is NOT called when span has empty attributes."""
        span = self.create_mock_span({})

        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_start_exception_handling(self, processor, mock_exporter):
        """Test on_start handles exceptions gracefully."""
        span = self.create_mock_span({"span_type": "eval"})
        mock_exporter.upsert_span.side_effect = Exception("Network error")

        # Should not raise exception
        processor.on_start(span, None)

        mock_exporter.upsert_span.assert_called_once()

    def test_on_end_with_eval_span_type(self, processor, mock_exporter):
        """Test on_end is called for eval span type."""
        span = self.create_mock_readable_span({"span_type": "eval"})

        processor.on_end(span)

        mock_exporter.upsert_span.assert_called_once_with(span)

    def test_on_end_with_evaluator_span_type(self, processor, mock_exporter):
        """Test on_end is called for evaluator span type."""
        span = self.create_mock_readable_span({"span_type": "evaluator"})

        processor.on_end(span)

        mock_exporter.upsert_span.assert_called_once_with(span)

    def test_on_end_with_evaluation_span_type(self, processor, mock_exporter):
        """Test on_end is called for evaluation span type."""
        span = self.create_mock_readable_span({"span_type": "evaluation"})

        processor.on_end(span)

        mock_exporter.upsert_span.assert_called_once_with(span)

    def test_on_end_with_execution_id(self, processor, mock_exporter):
        """Test on_end is called for span with execution.id."""
        span = self.create_mock_readable_span({"execution.id": "test-exec-id"})

        processor.on_end(span)

        mock_exporter.upsert_span.assert_called_once_with(span)

    def test_on_end_with_non_eval_span(self, processor, mock_exporter):
        """Test on_end is NOT called for non-eval spans."""
        span = self.create_mock_readable_span({"span_type": "agent"})

        processor.on_end(span)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_end_with_no_attributes(self, processor, mock_exporter):
        """Test on_end is NOT called when span has no attributes."""
        span = self.create_mock_readable_span(None)

        processor.on_end(span)

        mock_exporter.upsert_span.assert_not_called()

    def test_on_end_exception_handling(self, processor, mock_exporter):
        """Test on_end handles exceptions gracefully."""
        span = self.create_mock_readable_span({"span_type": "eval"})
        mock_exporter.upsert_span.side_effect = Exception("Network error")

        # Should not raise exception
        processor.on_end(span)

        mock_exporter.upsert_span.assert_called_once()

    def test_is_eval_span_with_eval_type(self, processor):
        """Test _is_eval_span returns True for eval span type."""
        span = self.create_mock_span({"span_type": "eval"})
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_evaluator_type(self, processor):
        """Test _is_eval_span returns True for evaluator span type."""
        span = self.create_mock_span({"span_type": "evaluator"})
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_evaluation_type(self, processor):
        """Test _is_eval_span returns True for evaluation span type."""
        span = self.create_mock_span({"span_type": "evaluation"})
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_eval_set_run_type(self, processor):
        """Test _is_eval_span returns True for eval_set_run span type."""
        span = self.create_mock_span({"span_type": "eval_set_run"})
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_eval_output_type(self, processor):
        """Test _is_eval_span returns True for evalOutput span type."""
        span = self.create_mock_span({"span_type": "evalOutput"})
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_execution_id(self, processor):
        """Test _is_eval_span returns True for span with execution.id."""
        span = self.create_mock_span({"execution.id": "test-id"})
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_both_criteria(self, processor):
        """Test _is_eval_span returns True when both criteria match."""
        span = self.create_mock_span(
            {"span_type": "evaluation", "execution.id": "test-id"}
        )
        assert processor._is_eval_span(span) is True

    def test_is_eval_span_with_non_eval_type(self, processor):
        """Test _is_eval_span returns False for non-eval span type."""
        span = self.create_mock_span({"span_type": "agent"})
        assert processor._is_eval_span(span) is False

    def test_is_eval_span_with_no_attributes(self, processor):
        """Test _is_eval_span returns False when span has no attributes."""
        span = self.create_mock_span(None)
        assert processor._is_eval_span(span) is False

    def test_is_eval_span_with_empty_attributes(self, processor):
        """Test _is_eval_span returns False when span has empty attributes."""
        span = self.create_mock_span({})
        assert processor._is_eval_span(span) is False

    def test_shutdown(self, processor):
        """Test shutdown method."""
        # Should not raise exception
        processor.shutdown()

    def test_force_flush(self, processor):
        """Test force_flush method."""
        result = processor.force_flush()
        assert result is True

    def test_force_flush_with_timeout(self, processor):
        """Test force_flush with custom timeout."""
        result = processor.force_flush(timeout_millis=5000)
        assert result is True

    def test_on_start_with_parent_context(self, processor, mock_exporter):
        """Test on_start with parent context."""
        span = self.create_mock_span({"span_type": "eval"})
        parent_context = Mock(spec=context_api.Context)

        processor.on_start(span, parent_context)

        mock_exporter.upsert_span.assert_called_once_with(
            span, status_override=SpanStatus.RUNNING
        )

    def test_processor_handles_all_eval_span_types(self, processor):
        """Test that all eval span types are properly detected."""
        eval_span_types = [
            "eval",
            "evaluator",
            "evaluation",
            "eval_set_run",
            "evalOutput",
        ]

        for span_type in eval_span_types:
            span = self.create_mock_span({"span_type": span_type})
            assert processor._is_eval_span(span) is True, (
                f"Failed for span_type: {span_type}"
            )

    # Tests for non-blocking behavior

    def test_on_start_does_not_block(self, mock_exporter):
        """Test that on_start returns immediately even if upsert is slow."""

        # Create a mock that simulates a slow API call
        def slow_upsert(*args, **kwargs):
            time.sleep(2)

        mock_exporter.upsert_span = Mock(side_effect=slow_upsert)
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        start_time = time.time()
        processor.on_start(span, None)
        elapsed = time.time() - start_time

        # Should return immediately (< 0.1 seconds), not wait for 2 seconds
        assert elapsed < 0.1, f"on_start blocked for {elapsed} seconds"

    def test_on_end_does_not_block(self, mock_exporter):
        """Test that on_end returns immediately even if upsert is slow."""

        # Create a mock that simulates a slow API call
        def slow_upsert(*args, **kwargs):
            time.sleep(2)

        mock_exporter.upsert_span = Mock(side_effect=slow_upsert)
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_readable_span({"span_type": "eval"})

        start_time = time.time()
        processor.on_end(span)
        elapsed = time.time() - start_time

        # Should return immediately (< 0.1 seconds), not wait for 2 seconds
        assert elapsed < 0.1, f"on_end blocked for {elapsed} seconds"

    def test_on_start_uses_daemon_thread(self, mock_exporter):
        """Test that on_start creates daemon threads."""
        created_threads = []

        original_thread_init = threading.Thread.__init__

        def track_thread(self, *args, **kwargs):
            original_thread_init(self, *args, **kwargs)
            created_threads.append(self)

        with patch.object(threading.Thread, "__init__", track_thread):
            processor = LiveTrackingSpanProcessor(mock_exporter)
            span = self.create_mock_span({"span_type": "eval"})
            processor.on_start(span, None)

            # Wait a bit for thread to be created
            time.sleep(0.1)

            # Verify at least one daemon thread was created
            daemon_threads = [t for t in created_threads if t.daemon]
            assert len(daemon_threads) > 0, "No daemon threads were created"

    def test_on_start_auth_error_does_not_block(self, mock_exporter):
        """Test that 401 auth errors don't block execution."""
        # Simulate 401 Unauthorized error
        mock_exporter.upsert_span = Mock(side_effect=Exception("401 Unauthorized"))
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        start_time = time.time()
        processor.on_start(span, None)
        elapsed = time.time() - start_time

        # Should return immediately
        assert elapsed < 0.1, f"on_start blocked on auth error for {elapsed} seconds"

    def test_on_end_auth_error_does_not_block(self, mock_exporter):
        """Test that 401 auth errors don't block execution."""
        # Simulate 401 Unauthorized error
        mock_exporter.upsert_span = Mock(side_effect=Exception("401 Unauthorized"))
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_readable_span({"span_type": "eval"})

        start_time = time.time()
        processor.on_end(span)
        elapsed = time.time() - start_time

        # Should return immediately
        assert elapsed < 0.1, f"on_end blocked on auth error for {elapsed} seconds"

    def test_on_start_network_timeout_does_not_block(self, mock_exporter):
        """Test that network timeouts don't block execution."""

        # Simulate network timeout
        def timeout_upsert(*args, **kwargs):
            time.sleep(10)  # Simulate very slow network
            raise TimeoutError("Network timeout")

        mock_exporter.upsert_span = Mock(side_effect=timeout_upsert)
        processor = LiveTrackingSpanProcessor(mock_exporter)
        span = self.create_mock_span({"span_type": "eval"})

        start_time = time.time()
        processor.on_start(span, None)
        elapsed = time.time() - start_time

        # Should return immediately, not wait for 10 seconds
        assert elapsed < 0.1, f"on_start blocked on timeout for {elapsed} seconds"

    def test_multiple_rapid_calls_do_not_block(self, mock_exporter):
        """Test that multiple rapid on_start calls don't block each other."""
        call_count = []

        def counting_upsert(*args, **kwargs):
            call_count.append(1)
            time.sleep(1)  # Each call takes 1 second

        mock_exporter.upsert_span = Mock(side_effect=counting_upsert)
        processor = LiveTrackingSpanProcessor(mock_exporter)

        start_time = time.time()
        # Make 5 rapid calls
        for i in range(5):
            span = self.create_mock_span({"span_type": "eval", "id": str(i)})
            processor.on_start(span, None)

        elapsed = time.time() - start_time

        # All 5 calls should return immediately (< 0.5 seconds)
        # Not 5+ seconds if they were blocking
        assert elapsed < 0.5, f"Multiple calls took {elapsed} seconds"

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

    def test_processor_with_custom_timeout(self, mock_exporter):
        """Test processor can be initialized with custom timeout."""
        processor = LiveTrackingSpanProcessor(mock_exporter, timeout=10.0)
        assert processor.timeout == 10.0

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
