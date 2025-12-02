"""Tests for LangGraphCollapsingSpanProcessor - Phase 2/3 In-Progress Visibility + Extract Fields."""

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
    _parse_json,
    extract_fields,
    SPAN_TYPE_MAP,
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


# =============================================================================
# Phase 3 Tests: Extract Fields
# =============================================================================


class TestParseJson:
    """Tests for _parse_json helper function."""

    def test_parse_valid_json_string(self):
        """Should parse valid JSON string to dict."""
        result = _parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_dict_passthrough(self):
        """Should return dict as-is."""
        input_dict = {"key": "value"}
        result = _parse_json(input_dict)
        assert result == input_dict

    def test_parse_empty_string(self):
        """Should return empty dict for empty string."""
        assert _parse_json("") == {}

    def test_parse_none(self):
        """Should return empty dict for None."""
        assert _parse_json(None) == {}

    def test_parse_invalid_json(self):
        """Should return empty dict for invalid JSON."""
        assert _parse_json("not valid json") == {}

    def test_parse_nested_json(self):
        """Should parse nested JSON correctly."""
        nested = '{"messages": [{"role": "user", "content": "Hello"}]}'
        result = _parse_json(nested)
        assert result == {"messages": [{"role": "user", "content": "Hello"}]}


class TestExtractFields:
    """Tests for extract_fields function - Phase 3 optimization."""

    def test_extract_system_and_user_prompts(self):
        """Should extract systemPrompt and userPrompt from messages."""
        attrs = {
            "input.value": json.dumps({
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "What is the date?"}
                ]
            }),
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["systemPrompt"] == "You are a helpful assistant"
        assert result["userPrompt"] == "What is the date?"
        assert result["type"] == "completion"

    def test_extract_output_content(self):
        """Should extract output.content from output.value."""
        attrs = {
            "output.value": json.dumps({
                "content": "The current date is November 27, 2025."
            }),
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["output"] == {"content": "The current date is November 27, 2025."}

    def test_extract_output_from_messages(self):
        """Should extract output from last assistant message if no content field."""
        attrs = {
            "output.value": json.dumps({
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"}
                ]
            }),
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["output"] == {"content": "Hi there!"}

    def test_span_type_mapping(self):
        """Should map openinference.span.kind to UiPath span types."""
        test_cases = [
            ("CHAIN", "agentRun"),
            ("LLM", "completion"),
            ("TOOL", "toolCall"),
            ("UNKNOWN", "agentRun"),  # Default fallback
        ]

        for otel_kind, expected_type in test_cases:
            attrs = {"openinference.span.kind": otel_kind}
            result = extract_fields(attrs)
            assert result["type"] == expected_type, f"Failed for {otel_kind}"

    def test_preserve_model_name(self):
        """Should preserve llm.model_name as model."""
        attrs = {
            "llm.model_name": "gpt-4o-mini",
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["model"] == "gpt-4o-mini"

    def test_preserve_token_counts(self):
        """Should preserve token counts in usage object."""
        attrs = {
            "llm.token_count.prompt": 150,
            "llm.token_count.completion": 50,
            "llm.token_count.total": 200,
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["usage"] == {
            "promptTokens": 150,
            "completionTokens": 50,
            "totalTokens": 200,
        }

    def test_preserve_error_info(self):
        """Should preserve error information."""
        attrs = {
            "error": "Connection timeout",
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["error"] == "Connection timeout"

    def test_preserve_exception_message(self):
        """Should preserve exception.message as error."""
        attrs = {
            "exception.message": "Rate limit exceeded",
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["error"] == "Rate limit exceeded"

    def test_preserve_invocation_parameters(self):
        """Should preserve llm.invocation_parameters."""
        attrs = {
            "llm.invocation_parameters": json.dumps({
                "temperature": 0.7,
                "max_tokens": 1000
            }),
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["invocationParameters"] == {
            "temperature": 0.7,
            "max_tokens": 1000
        }

    def test_drops_verbose_input_output_values(self):
        """Should NOT include raw input.value/output.value in result."""
        attrs = {
            "input.value": json.dumps({
                "messages": [{"role": "system", "content": "test"}]
            }),
            "output.value": json.dumps({
                "messages": [{"role": "assistant", "content": "response"}],
                "content": "response"
            }),
            "input.mime_type": "application/json",
            "output.mime_type": "application/json",
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        # Verbose fields should NOT be in result
        assert "input.value" not in result
        assert "output.value" not in result
        assert "input.mime_type" not in result
        assert "output.mime_type" not in result

        # Extracted fields should be present
        assert "systemPrompt" in result
        assert "output" in result

    def test_handles_human_type_messages(self):
        """Should handle 'human' as user role (LangGraph format)."""
        attrs = {
            "input.value": json.dumps({
                "messages": [
                    {"type": "system", "content": "System prompt"},
                    {"type": "human", "content": "User question"}
                ]
            }),
            "openinference.span.kind": "LLM"
        }

        result = extract_fields(attrs)

        assert result["systemPrompt"] == "System prompt"
        assert result["userPrompt"] == "User question"

    def test_empty_attributes(self):
        """Should handle empty attributes gracefully."""
        result = extract_fields({})

        assert result["type"] == "agentRun"  # Default
        assert "systemPrompt" not in result
        assert "userPrompt" not in result
        assert "output" not in result

    def test_full_realistic_llm_span(self):
        """Test with realistic LLM span attributes."""
        attrs = {
            "input.value": json.dumps({
                "messages": [
                    {"role": "system", "content": "You are an advanced automatic agent."},
                    {"role": "user", "content": "What is the current date?"}
                ]
            }),
            "output.value": json.dumps({
                "messages": [
                    {"role": "system", "content": "You are an advanced..."},
                    {"role": "user", "content": "What is..."},
                    {"role": "assistant", "content": "The current date is November 27, 2025."}
                ],
                "content": "The current date is November 27, 2025."
            }),
            "input.mime_type": "application/json",
            "output.mime_type": "application/json",
            "openinference.span.kind": "LLM",
            "llm.model_name": "gpt-4o-mini-2024-07-18",
            "llm.token_count.prompt": 245,
            "llm.token_count.completion": 12,
            "llm.token_count.total": 257,
            "llm.invocation_parameters": json.dumps({"temperature": 0, "max_tokens": 4096}),
            "metadata": json.dumps({"thread_id": "default", "langgraph_step": 1}),
        }

        result = extract_fields(attrs)

        # Verify extracted fields
        assert result["type"] == "completion"
        assert result["systemPrompt"] == "You are an advanced automatic agent."
        assert result["userPrompt"] == "What is the current date?"
        assert result["output"] == {"content": "The current date is November 27, 2025."}
        assert result["model"] == "gpt-4o-mini-2024-07-18"
        assert result["usage"] == {"promptTokens": 245, "completionTokens": 12, "totalTokens": 257}
        assert result["invocationParameters"] == {"temperature": 0, "max_tokens": 4096}

        # Verify dropped fields
        assert "input.value" not in result
        assert "output.value" not in result
        assert "input.mime_type" not in result
        assert "output.mime_type" not in result
        assert "metadata" not in result


class TestPhase3Integration:
    """Integration tests for Phase 3 extract_fields in processor."""

    @pytest.fixture
    def mock_next_processor(self):
        return MockSpanProcessor()

    @pytest.fixture
    def processor(self, mock_next_processor):
        return LangGraphCollapsingSpanProcessor(
            next_processor=mock_next_processor,
            enable_guardrails=False,
        )

    def test_llm_span_uses_extract_fields(self, processor, mock_next_processor):
        """LLM spans should use extract_fields for compact attributes."""
        # Start LangGraph execution
        start_span = MockSpan(name="LangGraph", trace_id=111, span_id=222)
        processor.on_start(start_span, parent_context=None)

        mock_next_processor.emitted_spans.clear()

        # Send LLM span with verbose attributes
        llm_span = MockReadableSpan(
            name="UiPathChat",
            trace_id=111,
            span_id=333,
            parent_span_id=222,
            attributes={
                "openinference.span.kind": "LLM",
                "input.value": json.dumps({
                    "messages": [
                        {"role": "system", "content": "You are helpful"},
                        {"role": "user", "content": "Hello"}
                    ]
                }),
                "output.value": json.dumps({
                    "content": "Hi there!"
                }),
                "llm.model_name": "gpt-4o-mini",
                "llm.token_count.prompt": 100,
                "llm.token_count.completion": 10,
                "llm.token_count.total": 110,
            },
        )
        processor.on_end(llm_span)

        # Find Model run span
        emitted = mock_next_processor.get_emitted_dicts()
        model_runs = [s for s in emitted if s.get("name") == "Model run"]
        assert len(model_runs) == 1

        model_run_attrs = model_runs[0]["attributes"]

        # Verify extract_fields was applied
        assert model_run_attrs["type"] == "completion"
        assert model_run_attrs.get("systemPrompt") == "You are helpful"
        assert model_run_attrs.get("userPrompt") == "Hello"
        assert model_run_attrs.get("output") == {"content": "Hi there!"}
        assert model_run_attrs.get("model") == "gpt-4o-mini"
        assert model_run_attrs.get("usage") == {"promptTokens": 100, "completionTokens": 10, "totalTokens": 110}

        # Verify verbose fields are NOT present
        assert "input.value" not in model_run_attrs
        assert "output.value" not in model_run_attrs
        assert "input.mime_type" not in model_run_attrs
        assert "output.mime_type" not in model_run_attrs
