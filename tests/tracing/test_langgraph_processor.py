"""Tests for LangGraphCollapsingSpanProcessor."""

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest
from opentelemetry.trace import StatusCode, TraceFlags

from uipath.tracing import LangGraphCollapsingSpanProcessor, SyntheticReadableSpan


class MockSpanContext:
    """Mock SpanContext for testing."""

    def __init__(self, trace_id: int, span_id: int):
        self.trace_id = trace_id
        self.span_id = span_id
        self.trace_flags = TraceFlags(0x01)
        self.is_remote = False


class MockStatus:
    """Mock Status for testing."""

    def __init__(self, code: int):
        self.status_code = MagicMock()
        self.status_code.value = code


class MockSpan:
    """Mock Span for testing (used in on_start)."""

    def __init__(
        self,
        name: str,
        trace_id: int,
        span_id: int,
        start_time: int = 1000000000,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self._trace_id = trace_id
        self._span_id = span_id
        self.start_time = start_time
        self.attributes = attributes or {}

    def get_span_context(self) -> MockSpanContext:
        return MockSpanContext(self._trace_id, self._span_id)


class MockReadableSpan:
    """Mock ReadableSpan for testing (used in on_end)."""

    def __init__(
        self,
        name: str,
        trace_id: int,
        span_id: int,
        parent_span_id: Optional[int] = None,
        start_time: int = 1000000000,
        end_time: int = 2000000000,
        attributes: Optional[Dict[str, Any]] = None,
        status_code: int = 1,  # 1=OK, 2=ERROR
    ):
        self.name = name
        self._trace_id = trace_id
        self._span_id = span_id
        self._parent_span_id = parent_span_id
        self.start_time = start_time
        self.end_time = end_time
        self.attributes = attributes or {}
        self.status = MockStatus(status_code)

    def get_span_context(self) -> MockSpanContext:
        return MockSpanContext(self._trace_id, self._span_id)

    @property
    def parent(self) -> Optional[MockSpanContext]:
        if self._parent_span_id:
            return MockSpanContext(self._trace_id, self._parent_span_id)
        return None


@pytest.fixture
def mock_next_processor():
    """Create a mock next processor."""
    processor = MagicMock()
    processor.on_start = MagicMock()
    processor.on_end = MagicMock()
    processor.shutdown = MagicMock()
    processor.force_flush = MagicMock(return_value=True)
    return processor


@pytest.fixture
def processor(mock_next_processor):
    """Create a LangGraphCollapsingSpanProcessor instance."""
    return LangGraphCollapsingSpanProcessor(
        next_processor=mock_next_processor,
        enable_guardrails=True,
    )


@pytest.fixture
def processor_no_guardrails(mock_next_processor):
    """Create a LangGraphCollapsingSpanProcessor without guardrails."""
    return LangGraphCollapsingSpanProcessor(
        next_processor=mock_next_processor,
        enable_guardrails=False,
    )


class TestLangGraphCollapsingSpanProcessor:
    """Tests for the main processor class."""

    def test_non_langgraph_span_passes_through(self, processor, mock_next_processor):
        """Non-LangGraph spans should pass through unchanged."""
        span = MockReadableSpan(
            name="some_other_span",
            trace_id=123,
            span_id=456,
        )

        processor.on_end(span)

        mock_next_processor.on_end.assert_called_once_with(span)

    def test_langgraph_root_detection_on_start(self, processor, mock_next_processor):
        """LangGraph root span should be detected on start."""
        span = MockSpan(
            name="LangGraph",
            trace_id=123,
            span_id=456,
            start_time=1000000000,
        )

        processor.on_start(span, None)

        # Should create execution context
        trace_id = format(123, "032x")
        assert trace_id in processor.active_executions

        # Should emit running Agent run span
        assert mock_next_processor.on_end.call_count == 1
        emitted_span = mock_next_processor.on_end.call_args[0][0]
        assert isinstance(emitted_span, SyntheticReadableSpan)
        assert emitted_span.name == "Agent run - Agent"

    def test_langgraph_root_creates_agent_run_span(
        self, processor, mock_next_processor
    ):
        """LangGraph root ending should emit Agent run span."""
        trace_id = 123
        langgraph_span_id = 456

        # First, simulate on_start for LangGraph
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
            start_time=1000000000,
        )
        processor.on_start(start_span, None)

        # Clear the call from on_start
        mock_next_processor.on_end.reset_mock()

        # Now simulate on_end for LangGraph
        end_span = MockReadableSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
            start_time=1000000000,
            end_time=2000000000,
            attributes={"output.value": '{"content": "test output"}'},
        )
        processor.on_end(end_span)

        # Should emit: agent pre guardrail, agent pre governance,
        # agent post guardrail, agent post governance, agent run, agent output
        assert mock_next_processor.on_end.call_count >= 5

    def test_node_spans_are_buffered(self, processor, mock_next_processor):
        """LangGraph node spans should be buffered, not emitted."""
        trace_id = 123
        langgraph_span_id = 456

        # Create execution context
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor.on_start(start_span, None)
        mock_next_processor.on_end.reset_mock()

        # Test node spans
        for node_name in ["init", "agent", "route_agent", "terminate"]:
            node_span = MockReadableSpan(
                name=node_name,
                trace_id=trace_id,
                span_id=789 + hash(node_name),
                parent_span_id=langgraph_span_id,
            )
            processor.on_end(node_span)

        # No spans should be emitted for nodes
        assert mock_next_processor.on_end.call_count == 0

    def test_action_prefix_spans_are_buffered(self, processor, mock_next_processor):
        """Spans with action: prefix should be buffered."""
        trace_id = 123
        langgraph_span_id = 456

        # Create execution context
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor.on_start(start_span, None)
        mock_next_processor.on_end.reset_mock()

        action_span = MockReadableSpan(
            name="action:search",
            trace_id=trace_id,
            span_id=789,
            parent_span_id=langgraph_span_id,
        )
        processor.on_end(action_span)

        # Should be buffered, not emitted
        assert mock_next_processor.on_end.call_count == 0

    def test_llm_span_emits_call_tree(self, processor, mock_next_processor):
        """LLM spans should emit LLM call tree immediately."""
        trace_id = 123
        langgraph_span_id = 456

        # Create execution context
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor.on_start(start_span, None)
        mock_next_processor.on_end.reset_mock()

        # Emit LLM span
        llm_span = MockReadableSpan(
            name="UiPathChat",
            trace_id=trace_id,
            span_id=789,
            parent_span_id=langgraph_span_id,
            attributes={"openinference.span.kind": "LLM"},
        )
        processor.on_end(llm_span)

        # With guardrails: LLM call + pre guardrail + pre governance + Model run + post guardrail + post governance = 6
        assert mock_next_processor.on_end.call_count == 6

        # Verify span names
        calls = mock_next_processor.on_end.call_args_list
        span_names = [c[0][0].name for c in calls]
        assert "LLM call" in span_names
        assert "Model run" in span_names
        assert "LLM input guardrail check" in span_names
        assert "LLM output guardrail check" in span_names

    def test_llm_span_without_guardrails(
        self, processor_no_guardrails, mock_next_processor
    ):
        """LLM spans without guardrails should emit only LLM call and Model run."""
        trace_id = 123
        langgraph_span_id = 456

        # Create execution context
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor_no_guardrails.on_start(start_span, None)
        mock_next_processor.on_end.reset_mock()

        # Emit LLM span
        llm_span = MockReadableSpan(
            name="UiPathChat",
            trace_id=trace_id,
            span_id=789,
            parent_span_id=langgraph_span_id,
            attributes={"openinference.span.kind": "LLM"},
        )
        processor_no_guardrails.on_end(llm_span)

        # Without guardrails: LLM call + Model run = 2
        assert mock_next_processor.on_end.call_count == 2

        calls = mock_next_processor.on_end.call_args_list
        span_names = [c[0][0].name for c in calls]
        assert "LLM call" in span_names
        assert "Model run" in span_names
        assert "LLM input guardrail check" not in span_names

    def test_concurrent_executions(self, processor, mock_next_processor):
        """Multiple concurrent LangGraph executions should be tracked separately."""
        # Start first execution
        span1 = MockSpan(
            name="LangGraph",
            trace_id=111,
            span_id=100,
        )
        processor.on_start(span1, None)

        # Start second execution
        span2 = MockSpan(
            name="LangGraph",
            trace_id=222,
            span_id=200,
        )
        processor.on_start(span2, None)

        # Both should have separate contexts
        trace_id_1 = format(111, "032x")
        trace_id_2 = format(222, "032x")
        assert trace_id_1 in processor.active_executions
        assert trace_id_2 in processor.active_executions
        assert (
            processor.active_executions[trace_id_1].synthetic_span_id
            != processor.active_executions[trace_id_2].synthetic_span_id
        )

    def test_error_status_propagates(self, processor, mock_next_processor):
        """Error status should propagate to synthetic spans."""
        trace_id = 123
        langgraph_span_id = 456

        # Create execution context
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor.on_start(start_span, None)
        mock_next_processor.on_end.reset_mock()

        # End with error
        end_span = MockReadableSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
            status_code=2,  # ERROR
        )
        processor.on_end(end_span)

        # Find the Agent run span
        calls = mock_next_processor.on_end.call_args_list
        agent_run_calls = [c for c in calls if c[0][0].name == "Agent run - Agent"]
        assert len(agent_run_calls) > 0

        # At least one should have error status (the final one)
        final_agent_run = agent_run_calls[-1][0][0]
        assert final_agent_run.status.status_code == StatusCode.ERROR

    def test_cleanup_after_langgraph_end(self, processor, mock_next_processor):
        """Active execution should be cleaned up after LangGraph ends."""
        trace_id = 123
        langgraph_span_id = 456

        # Create execution context
        start_span = MockSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor.on_start(start_span, None)

        trace_id_str = format(trace_id, "032x")
        assert trace_id_str in processor.active_executions

        # End LangGraph
        end_span = MockReadableSpan(
            name="LangGraph",
            trace_id=trace_id,
            span_id=langgraph_span_id,
        )
        processor.on_end(end_span)

        # Should be cleaned up
        assert trace_id_str not in processor.active_executions

    def test_shutdown_delegates_to_next(self, processor, mock_next_processor):
        """shutdown() should delegate to next processor."""
        processor.shutdown()
        mock_next_processor.shutdown.assert_called_once()

    def test_force_flush_delegates_to_next(self, processor, mock_next_processor):
        """force_flush() should delegate to next processor."""
        result = processor.force_flush(5000)
        mock_next_processor.force_flush.assert_called_once_with(5000)
        assert result is True


class TestSyntheticReadableSpan:
    """Tests for the SyntheticReadableSpan class."""

    def test_basic_creation(self):
        """Test basic span creation."""
        span_dict = {
            "id": "abc123",
            "trace_id": "def456" + "0" * 26,
            "parent_id": None,
            "name": "Test Span",
            "start_time": 1000000000,
            "end_time": 2000000000,
            "status": 1,
            "attributes": {"key": "value"},
        }

        span = SyntheticReadableSpan(span_dict)

        assert span.name == "Test Span"
        assert span.start_time == 1000000000
        assert span.end_time == 2000000000
        assert span.attributes == {"key": "value"}
        assert span.parent is None

    def test_with_parent(self):
        """Test span with parent."""
        parent_id_hex = "abcdef1234567890"  # Valid 16-char hex string
        span_dict = {
            "id": "abc123" + "0" * 10,  # 16-char hex
            "trace_id": "def456" + "0" * 26,  # 32-char hex
            "parent_id": parent_id_hex,
            "name": "Child Span",
            "start_time": 1000000000,
            "end_time": 2000000000,
            "status": 1,
        }

        span = SyntheticReadableSpan(span_dict)

        assert span.parent is not None
        assert span.parent.span_id == int(parent_id_hex, 16)

    def test_error_status(self):
        """Test span with error status."""
        span_dict = {
            "id": "abc123",
            "trace_id": "def456" + "0" * 26,
            "name": "Error Span",
            "status": 2,  # ERROR
        }

        span = SyntheticReadableSpan(span_dict)

        assert span.status.status_code == StatusCode.ERROR

    def test_ok_status(self):
        """Test span with OK status."""
        span_dict = {
            "id": "abc123",
            "trace_id": "def456" + "0" * 26,
            "name": "OK Span",
            "status": 1,  # OK
        }

        span = SyntheticReadableSpan(span_dict)

        assert span.status.status_code == StatusCode.OK

    def test_to_json(self):
        """Test JSON serialization."""
        span_dict = {
            "id": "abc123",
            "trace_id": "def456" + "0" * 26,
            "name": "Test Span",
            "attributes": {"key": "value"},
        }

        span = SyntheticReadableSpan(span_dict)
        json_str = span.to_json()

        parsed = json.loads(json_str)
        assert parsed["name"] == "Test Span"
        assert parsed["attributes"]["key"] == "value"

    def test_span_context(self):
        """Test span context creation."""
        span_dict = {
            "id": "abcdef1234567890",
            "trace_id": "12345678901234567890123456789012",
            "name": "Test Span",
        }

        span = SyntheticReadableSpan(span_dict)
        context = span.get_span_context()

        assert context.trace_id == int("12345678901234567890123456789012", 16)
        assert context.span_id == int("abcdef1234567890", 16)
        assert context.is_remote is False


class TestNodeDetection:
    """Tests for node span detection."""

    @pytest.fixture
    def processor(self, mock_next_processor):
        return LangGraphCollapsingSpanProcessor(mock_next_processor)

    def test_explicit_node_names(self, processor):
        """Test detection of explicit node names."""
        for name in ["init", "agent", "action", "route_agent", "terminate"]:
            span = MockReadableSpan(name=name, trace_id=123, span_id=456)
            assert processor._is_node_span(span) is True

    def test_action_prefix(self, processor):
        """Test detection of action: prefix."""
        span = MockReadableSpan(name="action:search_web", trace_id=123, span_id=456)
        assert processor._is_node_span(span) is True

    def test_langgraph_metadata(self, processor):
        """Test detection via langgraph_node in metadata."""
        span = MockReadableSpan(
            name="custom_node",
            trace_id=123,
            span_id=456,
            attributes={"metadata": json.dumps({"langgraph_node": "custom_node"})},
        )
        assert processor._is_node_span(span) is True

    def test_non_node_span(self, processor):
        """Test that regular spans are not detected as nodes."""
        span = MockReadableSpan(name="UiPathChat", trace_id=123, span_id=456)
        assert processor._is_node_span(span) is False


class TestLLMDetection:
    """Tests for LLM span detection."""

    @pytest.fixture
    def processor(self, mock_next_processor):
        return LangGraphCollapsingSpanProcessor(mock_next_processor)

    def test_llm_span_kind(self, processor):
        """Test detection of LLM spans via openinference.span.kind."""
        span = MockReadableSpan(
            name="UiPathChat",
            trace_id=123,
            span_id=456,
            attributes={"openinference.span.kind": "LLM"},
        )
        assert processor._is_llm_span(span) is True

    def test_non_llm_span(self, processor):
        """Test that non-LLM spans are not detected as LLM."""
        span = MockReadableSpan(
            name="some_tool",
            trace_id=123,
            span_id=456,
            attributes={"openinference.span.kind": "TOOL"},
        )
        assert processor._is_llm_span(span) is False

    def test_no_attributes(self, processor):
        """Test span with no attributes."""
        span = MockReadableSpan(
            name="UiPathChat",
            trace_id=123,
            span_id=456,
            attributes=None,
        )
        assert processor._is_llm_span(span) is False
