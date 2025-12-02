"""Tests for LangGraphCollapsingSpanProcessor - Phase 2 In-Progress Visibility."""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags

from uipath.tracing._langgraph_processor import (
    AgentExecution,
    LangGraphCollapsingSpanProcessor,
    SyntheticReadableSpan,
)
from uipath.tracing._utils import TraceStatus


class MockSpanProcessor(SpanProcessor):
    """Mock processor that captures emitted spans."""

    def __init__(self):
        self.emitted_spans: List[ReadableSpan] = []
        self.started_spans: List[Any] = []

    def on_start(self, span, parent_context=None):
        self.started_spans.append(span)

    def on_end(self, span: ReadableSpan):
        self.emitted_spans.append(span)

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True

    def get_emitted_dicts(self) -> List[Dict[str, Any]]:
        """Convert emitted spans to dictionaries for easier assertion."""
        result = []
        for span in self.emitted_spans:
            if isinstance(span, SyntheticReadableSpan):
                result.append(span._span_dict)
            else:
                result.append({
                    "name": span.name,
                    "status": 1 if span.status.status_code == StatusCode.OK else 2,
                })
        return result


class MockSpan:
    """Mock Span for on_start testing."""

    def __init__(self, name: str, trace_id: int = 12345, span_id: int = 67890, start_time: int = 1000000000):
        self.name = name
        self._trace_id = trace_id
        self._span_id = span_id
        self.start_time = start_time
        self.end_time = None
        self.attributes = {}
        self.status = Status(StatusCode.OK)
        self.parent = None

    def get_span_context(self):
        return SpanContext(
            trace_id=self._trace_id,
            span_id=self._span_id,
            is_remote=False,
            trace_flags=TraceFlags(0x01),
        )


class MockReadableSpan(ReadableSpan):
    """Mock ReadableSpan for on_end testing."""

    def __init__(
        self,
        name: str,
        trace_id: int = 12345,
        span_id: int = 67890,
        parent_span_id: Optional[int] = None,
        start_time: int = 1000000000,
        end_time: int = 2000000000,
        attributes: Optional[Dict[str, Any]] = None,
        status_code: StatusCode = StatusCode.OK,
    ):
        self._name = name
        self._trace_id = trace_id
        self._span_id = span_id
        self._parent_span_id = parent_span_id
        self._start_time = start_time
        self._end_time = end_time
        self._attributes = attributes or {}
        self._status_code = status_code

    @property
    def name(self) -> str:
        return self._name

    @property
    def start_time(self) -> int:
        return self._start_time

    @property
    def end_time(self) -> int:
        return self._end_time

    @property
    def attributes(self) -> Dict[str, Any]:
        return self._attributes

    @property
    def status(self):
        return Status(self._status_code)

    @property
    def parent(self):
        if self._parent_span_id:
            return SpanContext(
                trace_id=self._trace_id,
                span_id=self._parent_span_id,
                is_remote=False,
                trace_flags=TraceFlags(0x01),
            )
        return None

    @property
    def events(self):
        return []

    @property
    def links(self):
        return []

    @property
    def kind(self):
        return SpanKind.INTERNAL

    @property
    def resource(self):
        from opentelemetry.sdk.resources import Resource
        return Resource.create({})

    @property
    def instrumentation_info(self):
        return None

    @property
    def instrumentation_scope(self):
        from opentelemetry.sdk.util.instrumentation import InstrumentationScope
        return InstrumentationScope(name="test", version="1.0.0")

    def get_span_context(self):
        return SpanContext(
            trace_id=self._trace_id,
            span_id=self._span_id,
            is_remote=False,
            trace_flags=TraceFlags(0x01),
        )


class TestTraceStatus:
    """Tests for TraceStatus constants."""

    def test_trace_status_values(self):
        """Verify TraceStatus values match Temporal backend."""
        assert TraceStatus.UNSET == 0
        assert TraceStatus.OK == 1
        assert TraceStatus.ERROR == 2


class TestAgentExecution:
    """Tests for AgentExecution dataclass."""

    def test_default_status_is_ok(self):
        """Default status should be OK (1)."""
        execution = AgentExecution(
            trace_id="abc123",
            langgraph_span_id="def456",
            synthetic_span_id="ghi789",
        )
        assert execution.status == TraceStatus.OK

    def test_running_span_emitted_default_false(self):
        """running_span_emitted should default to False."""
        execution = AgentExecution(
            trace_id="abc123",
            langgraph_span_id="def456",
            synthetic_span_id="ghi789",
        )
        assert execution.running_span_emitted is False


class TestLangGraphCollapsingSpanProcessor:
    """Tests for LangGraphCollapsingSpanProcessor."""

    @pytest.fixture
    def mock_next_processor(self):
        return MockSpanProcessor()

    @pytest.fixture
    def processor(self, mock_next_processor):
        return LangGraphCollapsingSpanProcessor(
            next_processor=mock_next_processor,
            enable_guardrails=False,  # Disable for simpler testing
        )

    def test_on_start_emits_in_progress_span(self, processor, mock_next_processor):
        """on_start should emit Agent run span with Status=0 (UNSET)."""
        # Create LangGraph span
        span = MockSpan(name="LangGraph", trace_id=111, span_id=222)

        # Trigger on_start
        processor.on_start(span, parent_context=None)

        # Verify span was emitted
        emitted = mock_next_processor.get_emitted_dicts()
        assert len(emitted) == 1

        agent_run = emitted[0]
        assert agent_run["name"] == "Agent run - Agent"
        assert agent_run["status"] == TraceStatus.UNSET  # 0 = in-progress
        assert agent_run["end_time"] is None  # null = in-progress
        assert agent_run["span_type"] == "agentRun"

    def test_on_end_emits_completed_span(self, processor, mock_next_processor):
        """on_end should emit Agent run span with Status=1 (OK)."""
        # First trigger on_start
        start_span = MockSpan(name="LangGraph", trace_id=111, span_id=222)
        processor.on_start(start_span, parent_context=None)

        # Clear to isolate on_end emissions
        mock_next_processor.emitted_spans.clear()

        # Create completed LangGraph span
        end_span = MockReadableSpan(
            name="LangGraph",
            trace_id=111,
            span_id=222,
            start_time=1000000000,
            end_time=2000000000,
            attributes={"output.value": json.dumps({"content": "test output"})},
        )

        # Trigger on_end
        processor.on_end(end_span)

        # Find the final Agent run span
        emitted = mock_next_processor.get_emitted_dicts()
        agent_runs = [s for s in emitted if s.get("name") == "Agent run - Agent"]

        assert len(agent_runs) >= 1
        final_agent_run = agent_runs[-1]
        assert final_agent_run["status"] == TraceStatus.OK  # 1 = completed
        assert final_agent_run["end_time"] is not None  # end_time set

    def test_same_span_id_for_both_upserts(self, processor, mock_next_processor):
        """Both on_start and on_end should use the same synthetic span ID."""
        # on_start
        start_span = MockSpan(name="LangGraph", trace_id=111, span_id=222)
        processor.on_start(start_span, parent_context=None)

        # Capture the span ID from on_start
        start_emitted = mock_next_processor.get_emitted_dicts()
        start_span_id = start_emitted[0]["id"]

        # Clear and trigger on_end
        mock_next_processor.emitted_spans.clear()

        end_span = MockReadableSpan(
            name="LangGraph",
            trace_id=111,
            span_id=222,
            attributes={"output.value": json.dumps({"content": "test"})},
        )
        processor.on_end(end_span)

        # Find the final Agent run and verify same ID
        end_emitted = mock_next_processor.get_emitted_dicts()
        agent_runs = [s for s in end_emitted if s.get("name") == "Agent run - Agent"]
        assert len(agent_runs) >= 1

        end_span_id = agent_runs[-1]["id"]
        assert start_span_id == end_span_id, "Same SpanId must be used for both upserts"

    def test_error_status_on_error(self, processor, mock_next_processor):
        """Error spans should have Status=2 (ERROR)."""
        # on_start
        start_span = MockSpan(name="LangGraph", trace_id=111, span_id=222)
        processor.on_start(start_span, parent_context=None)

        mock_next_processor.emitted_spans.clear()

        # on_end with error
        end_span = MockReadableSpan(
            name="LangGraph",
            trace_id=111,
            span_id=222,
            status_code=StatusCode.ERROR,
            attributes={},
        )
        processor.on_end(end_span)

        emitted = mock_next_processor.get_emitted_dicts()
        agent_runs = [s for s in emitted if s.get("name") == "Agent run - Agent"]
        assert len(agent_runs) >= 1

        final_agent_run = agent_runs[-1]
        assert final_agent_run["status"] == TraceStatus.ERROR  # 2 = error

    def test_non_langgraph_spans_pass_through(self, processor, mock_next_processor):
        """Non-LangGraph spans should pass through unchanged."""
        span = MockReadableSpan(
            name="CustomSpan",
            trace_id=999,
            span_id=888,
        )

        processor.on_end(span)

        # Span should be passed to next processor
        assert len(mock_next_processor.emitted_spans) == 1
        assert mock_next_processor.emitted_spans[0].name == "CustomSpan"

    def test_node_spans_are_buffered(self, processor, mock_next_processor):
        """LangGraph node spans (init, agent, etc.) should be buffered, not emitted."""
        # First start a LangGraph execution
        start_span = MockSpan(name="LangGraph", trace_id=111, span_id=222)
        processor.on_start(start_span, parent_context=None)

        mock_next_processor.emitted_spans.clear()

        # Send node spans - these should be buffered
        for node_name in ["init", "agent", "route_agent", "terminate"]:
            node_span = MockReadableSpan(
                name=node_name,
                trace_id=111,
                span_id=300 + hash(node_name) % 100,
                parent_span_id=222,
            )
            processor.on_end(node_span)

        # Node spans should NOT be emitted
        emitted = mock_next_processor.get_emitted_dicts()
        node_names = {"init", "agent", "route_agent", "terminate"}
        for span_dict in emitted:
            assert span_dict.get("name") not in node_names, f"Node span {span_dict.get('name')} should be buffered"

    def test_llm_spans_emit_immediately(self, processor, mock_next_processor):
        """LLM spans should emit immediately as 'LLM call' + 'Model run'."""
        # Start LangGraph execution
        start_span = MockSpan(name="LangGraph", trace_id=111, span_id=222)
        processor.on_start(start_span, parent_context=None)

        mock_next_processor.emitted_spans.clear()

        # Send LLM span
        llm_span = MockReadableSpan(
            name="UiPathChat",
            trace_id=111,
            span_id=333,
            parent_span_id=222,
            attributes={"openinference.span.kind": "LLM"},
        )
        processor.on_end(llm_span)

        emitted = mock_next_processor.get_emitted_dicts()
        names = [s.get("name") for s in emitted]

        assert "LLM call" in names, "LLM call wrapper should be emitted"
        assert "Model run" in names, "Model run should be emitted"


class TestSyntheticReadableSpan:
    """Tests for SyntheticReadableSpan helper class."""

    def test_creates_span_from_dict(self):
        """SyntheticReadableSpan should correctly wrap a dictionary."""
        span_dict = {
            "id": "0123456789abcdef",  # Valid 16-char hex
            "trace_id": "0123456789abcdef0123456789abcdef",  # Valid 32-char hex
            "parent_id": "fedcba9876543210",  # Valid 16-char hex
            "name": "Test Span",
            "start_time": 1000,
            "end_time": 2000,
            "status": 1,
            "attributes": {"key": "value"},
        }

        span = SyntheticReadableSpan(span_dict)

        assert span.name == "Test Span"
        assert span.start_time == 1000
        assert span.end_time == 2000
        assert span.attributes == {"key": "value"}
        assert span.status.status_code == StatusCode.OK

    def test_error_status(self):
        """SyntheticReadableSpan should handle error status."""
        span_dict = {
            "id": "0123456789abcdef",  # Valid 16-char hex
            "trace_id": "0123456789abcdef0123456789abcdef",  # Valid 32-char hex
            "name": "Error Span",
            "status": 2,  # ERROR
        }

        span = SyntheticReadableSpan(span_dict)
        assert span.status.status_code == StatusCode.ERROR
