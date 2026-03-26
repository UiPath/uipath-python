"""Tests for Simulate Input span attributes."""

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_httpx import HTTPXMock

from uipath.core.tracing import UiPathTraceManager
from uipath.eval.mocks._cache_manager import CacheManager
from uipath.eval.mocks._input_mocker import generate_llm_input
from uipath.eval.mocks._mocker import UiPathInputMockingError
from uipath.eval.mocks._types import InputMockingStrategy, ModelSettings


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_simulate_input_span_attributes(httpx_mock: HTTPXMock, monkeypatch):
    """Test that Simulate Input span has correct attributes."""
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    # Set up span exporter to capture spans
    span_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(span_exporter)

    # Initialize trace manager with our exporter
    trace_manager = UiPathTraceManager()
    trace_manager.add_span_processor(span_processor)

    try:
        # Mock HTTP responses
        httpx_mock.add_response(
            url="https://example.com/agenthub_/llm/api/capabilities",
            status_code=200,
            json={},
        )
        httpx_mock.add_response(
            url="https://example.com/orchestrator_/llm/api/capabilities",
            status_code=200,
            json={},
        )
        httpx_mock.add_response(
            url="https://example.com/llm/api/chat/completions"
            "?api-version=2024-08-01-preview",
            status_code=200,
            json={
                "role": "assistant",
                "id": "response-id",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini-2024-07-18",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"name": "Alice", "greeting_style": "formal"}',
                            "tool_calls": None,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
            },
        )

        # Create input mocking strategy
        mocking_strategy = InputMockingStrategy(
            prompt="Generate a formal greeting for Alice",
            model=ModelSettings(
                model="gpt-4o-mini-2024-07-18",
                temperature=0.0,
                maxTokens=150,
            ),
        )

        input_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "greeting_style": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        }

        # Call generate_llm_input
        result = await generate_llm_input(
            mocking_strategy,
            input_schema,
            expected_behavior="Generate a formal greeting",
            expected_output={"message": "Good day, Alice."},
        )

        # Verify the result
        assert result == {"name": "Alice", "greeting_style": "formal"}

        # Get captured spans
        spans: list[ReadableSpan] = list(span_exporter.get_finished_spans())

        # Find the "Simulate Input" span
        simulate_input_spans = [s for s in spans if s.name == "Simulate Input"]
        assert len(simulate_input_spans) == 1, (
            f"Expected exactly one 'Simulate Input' span, "
            f"found {len(simulate_input_spans)}"
        )

        simulate_span = simulate_input_spans[0]

        # Verify span attributes match agents repo pattern
        assert simulate_span.attributes is not None

        # Check required custom attributes
        assert simulate_span.attributes.get("span_type") == "simulatedInput", (
            "span_type should be 'simulatedInput'"
        )
        assert simulate_span.attributes.get("type") == "simulatedInput", (
            "type should be 'simulatedInput'"
        )
        assert simulate_span.attributes.get("uipath.custom_instrumentation") is True, (
            "uipath.custom_instrumentation should be True"
        )

        # Check standard @traced attributes
        assert simulate_span.attributes.get("input.mime_type") == "application/json"
        assert "input.value" in simulate_span.attributes

        # Verify input.value contains the function parameters
        input_value = simulate_span.attributes.get("input.value")
        assert input_value is not None
        assert isinstance(input_value, str)
        assert "mocking_strategy" in input_value
        assert "input_schema" in input_value
        assert "expected_behavior" in input_value
        assert "expected_output" in input_value

        # Check output attributes
        assert simulate_span.attributes.get("output.mime_type") == "application/json"
        assert "output.value" in simulate_span.attributes

        # Verify output contains the generated input
        output_value = simulate_span.attributes.get("output.value")
        assert output_value is not None
        assert isinstance(output_value, str)
        assert '"name": "Alice"' in output_value
        assert '"greeting_style": "formal"' in output_value

    finally:
        # Clean up trace manager
        trace_manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_simulate_input_span_on_error(httpx_mock: HTTPXMock, monkeypatch):
    """Test that Simulate Input span attributes are set even when function fails."""
    monkeypatch.setenv("UIPATH_URL", "https://example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(CacheManager, "get", lambda *args, **kwargs: None)
    monkeypatch.setattr(CacheManager, "set", lambda *args, **kwargs: None)

    # Set up span exporter
    span_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(span_exporter)
    trace_manager = UiPathTraceManager()
    trace_manager.add_span_processor(span_processor)

    try:
        # Mock HTTP responses - return invalid JSON to trigger error
        httpx_mock.add_response(
            url="https://example.com/agenthub_/llm/api/capabilities",
            status_code=200,
            json={},
        )
        httpx_mock.add_response(
            url="https://example.com/orchestrator_/llm/api/capabilities",
            status_code=200,
            json={},
        )
        httpx_mock.add_response(
            url="https://example.com/llm/api/chat/completions"
            "?api-version=2024-08-01-preview",
            status_code=200,
            json={
                "role": "assistant",
                "id": "response-id",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini-2024-07-18",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "invalid json{{{",  # Invalid JSON
                            "tool_calls": None,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                },
            },
        )

        mocking_strategy = InputMockingStrategy(
            prompt="Generate input",
            model=ModelSettings(model="gpt-4o-mini-2024-07-18"),
        )

        input_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }

        # Call should fail due to invalid JSON
        with pytest.raises(UiPathInputMockingError):
            await generate_llm_input(
                mocking_strategy,
                input_schema,
                expected_behavior="Test",
                expected_output={},
            )

        # Get captured spans
        spans: list[ReadableSpan] = list(span_exporter.get_finished_spans())

        # Find the "Simulate Input" span
        simulate_input_spans = [s for s in spans if s.name == "Simulate Input"]
        assert len(simulate_input_spans) == 1

        simulate_span = simulate_input_spans[0]

        # Custom attributes should still be present (set at function start)
        assert simulate_span.attributes is not None
        assert simulate_span.attributes.get("span_type") == "simulatedInput"
        assert simulate_span.attributes.get("type") == "simulatedInput"
        assert simulate_span.attributes.get("uipath.custom_instrumentation") is True

        # Input attributes should be present (set before execution)
        assert simulate_span.attributes.get("input.mime_type") == "application/json"
        assert "input.value" in simulate_span.attributes

        # Output attributes will NOT be present (error occurred before output)
        # The span should have error status instead
        assert simulate_span.status.status_code.name == "ERROR"

    finally:
        trace_manager.shutdown()
