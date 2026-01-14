"""Tests for LiveTrackingSpanProcessor in _runtime.py."""

from typing import Any
from unittest.mock import Mock

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
