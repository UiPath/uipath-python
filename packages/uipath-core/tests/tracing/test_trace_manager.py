"""Tests for UiPathTraceManager"""

from unittest.mock import MagicMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor

from uipath.core.tracing.trace_manager import (
    UiPathTraceManager,
    _DelegatingSpanProcessor,
)


@pytest.fixture(autouse=True)
def _reset_delegating_singleton():
    """Reset the singleton between tests so each test starts clean."""
    _DelegatingSpanProcessor._instance = None
    yield
    _DelegatingSpanProcessor._instance = None


@pytest.mark.asyncio
async def test_multiple_factories_same_executor():
    """Test two factories using same executor, verify spans are captured correctly."""
    trace_manager = UiPathTraceManager()

    # Create span
    tracer = trace.get_tracer("uipath-runtime")
    with trace_manager.start_execution_span("root-span", "test"):
        with tracer.start_as_current_span(
            "custom-child-span", attributes={"operation": "child", "step": "1"}
        ):
            pass

    spans = trace_manager.get_execution_spans("test")
    assert len(spans) == 2

    assert spans[0].name == "custom-child-span"
    assert spans[0].attributes == {
        "operation": "child",
        "step": "1",
        "execution.id": "test",
    }

    assert spans[1].name == "root-span"
    assert spans[1].attributes == {"execution.id": "test"}


class TestDelegatingSpanProcessor:
    """Tests for _DelegatingSpanProcessor."""

    def test_add_and_clear(self) -> None:
        dp = _DelegatingSpanProcessor()
        p1 = MagicMock(spec=SpanProcessor)
        p2 = MagicMock(spec=SpanProcessor)

        dp.add(p1)
        dp.add(p2)
        assert len(dp._processors) == 2

        removed = dp.clear()
        assert removed == [p1, p2]
        assert dp._processors == []

    def test_delegates_on_start_and_on_end(self) -> None:
        dp = _DelegatingSpanProcessor()
        p1 = MagicMock(spec=SpanProcessor)
        p2 = MagicMock(spec=SpanProcessor)
        dp.add(p1)
        dp.add(p2)

        mock_span = MagicMock()
        dp.on_start(mock_span, parent_context=None)
        p1.on_start.assert_called_once_with(mock_span, None)
        p2.on_start.assert_called_once_with(mock_span, None)

        mock_readable_span = MagicMock()
        dp.on_end(mock_readable_span)
        p1.on_end.assert_called_once_with(mock_readable_span)
        p2.on_end.assert_called_once_with(mock_readable_span)

    def test_clear_stops_delegation(self) -> None:
        dp = _DelegatingSpanProcessor()
        p1 = MagicMock(spec=SpanProcessor)
        dp.add(p1)
        dp.clear()

        mock_span = MagicMock()
        dp.on_start(mock_span, parent_context=None)
        dp.on_end(mock_span)
        p1.on_start.assert_not_called()
        p1.on_end.assert_not_called()

    def test_get_instance_returns_singleton(self) -> None:
        provider = MagicMock()
        inst1 = _DelegatingSpanProcessor.get_instance(provider)
        inst2 = _DelegatingSpanProcessor.get_instance(provider)
        assert inst1 is inst2
        provider.add_span_processor.assert_called_once_with(inst1)

    def test_force_flush_delegates(self) -> None:
        dp = _DelegatingSpanProcessor()
        p1 = MagicMock(spec=SpanProcessor)
        dp.add(p1)

        result = dp.force_flush(timeout_millis=5000)
        assert result is True
        p1.force_flush.assert_called_once_with(5000)

    def test_force_flush_returns_false_on_child_failure(self) -> None:
        dp = _DelegatingSpanProcessor()
        p1 = MagicMock(spec=SpanProcessor)
        p2 = MagicMock(spec=SpanProcessor)
        p1.force_flush.return_value = True
        p2.force_flush.return_value = False
        dp.add(p1)
        dp.add(p2)

        assert dp.force_flush(timeout_millis=5000) is False

    def test_shutdown_delegates_to_children(self) -> None:
        dp = _DelegatingSpanProcessor()
        p1 = MagicMock(spec=SpanProcessor)
        p2 = MagicMock(spec=SpanProcessor)
        dp.add(p1)
        dp.add(p2)
        dp.shutdown()
        p1.shutdown.assert_called_once()
        p2.shutdown.assert_called_once()
        assert len(dp._processors) == 2


class TestTraceManagerShutdown:
    """Tests for the multi-job accumulation fix."""

    def test_shutdown_clears_processors(self) -> None:
        tm = UiPathTraceManager()
        p1 = MagicMock(spec=SpanProcessor)
        tm.add_span_processor(p1)

        tm.shutdown()

        assert tm.tracer_span_processors == []
        assert tm._delegating._processors == []
        p1.force_flush.assert_called_once()
        p1.shutdown.assert_called_once()

    def test_successive_managers_do_not_accumulate(self) -> None:
        """Simulates multiple jobs on the same pod.

        Each job creates a new UiPathTraceManager and adds a processor.
        After shutdown, the next job's processors should not stack with
        the previous ones.
        """
        processor_counts: list[int] = []

        for _ in range(5):
            tm = UiPathTraceManager()
            mock_processor = MagicMock(spec=SpanProcessor)
            tm.add_span_processor(mock_processor)

            # Count processors visible to the delegator (minus the batch
            # processor added by __init__ for execution_span_exporter)
            processor_counts.append(len(tm._delegating._processors))
            tm.shutdown()

        # Every job should see the same number of processors (2: the
        # execution batch processor from __init__ + the one we added),
        # NOT a linearly growing count.
        assert all(c == processor_counts[0] for c in processor_counts), (
            f"Processor counts should be constant across jobs, got: {processor_counts}"
        )

    def test_shutdown_tolerates_processor_error(self) -> None:
        tm = UiPathTraceManager()
        bad_processor = MagicMock(spec=SpanProcessor)
        bad_processor.force_flush.side_effect = RuntimeError("flush failed")
        tm.add_span_processor(bad_processor)

        # Should not raise
        tm.shutdown()
        assert tm.tracer_span_processors == []
        assert tm._delegating._processors == []

    def test_spans_not_sent_to_old_processors_after_shutdown(self) -> None:
        """After shutdown, old processors must not receive new span events."""
        tm1 = UiPathTraceManager()
        old_processor = MagicMock(spec=SpanProcessor)
        tm1.add_span_processor(old_processor)
        tm1.shutdown()

        # Simulate next job
        tm2 = UiPathTraceManager()
        new_processor = MagicMock(spec=SpanProcessor)
        tm2.add_span_processor(new_processor)

        mock_span = MagicMock()
        tm2._delegating.on_start(mock_span, parent_context=None)

        new_processor.on_start.assert_called_once()
        old_processor.on_start.assert_not_called()

        tm2.shutdown()
