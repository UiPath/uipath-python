import json
from pathlib import Path

import pytest
from span_transformer import SpanTransformer


def load_fixture(filename: str):
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, "r") as f:
        data = json.load(f)
    return data["spans"]


def test_collapse_20_spans_to_5():
    """Verify 20+ input spans become 5-6 output spans."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")

    assert len(input_spans) >= 20

    output_spans = transformer.transform(input_spans)

    # Should have: 1 synthetic parent (running) + LLM/tool spans + 1 synthetic parent (completed)
    assert len(output_spans) <= 8
    assert output_spans[0]["name"] == "Agent run - Agent"


def test_progressive_states():
    """Verify running → completed state emission."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    # Find the two versions of synthetic span
    synthetic_spans = [s for s in output_spans if s["name"] == "Agent run - Agent"]
    assert len(synthetic_spans) == 2

    running_span = synthetic_spans[0]
    completed_span = synthetic_spans[1]

    assert running_span["status"] == 0
    assert running_span["end_time"] is None

    assert completed_span["status"] == 1
    assert completed_span["end_time"] is not None


def test_llm_tool_spans_preserved():
    """Verify LLM and tool call spans are kept."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    # Count LLM spans in input
    input_llm_count = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )

    # Count LLM spans in output
    output_llm_count = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )

    assert input_llm_count == output_llm_count

    # Count tool spans in input
    input_tool_count = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )

    # Count tool spans in output
    output_tool_count = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )

    assert input_tool_count == output_tool_count


def test_node_spans_buffered():
    """Verify agent/action spans are NOT in output."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    # Should have NO node spans in output
    node_spans = [s for s in output_spans if s["name"] in ["agent", "action"]]
    assert len(node_spans) == 0

    # Should also have no action:* spans
    action_prefixed_spans = [s for s in output_spans if s["name"].startswith("action:")]
    assert len(action_prefixed_spans) == 0


def test_correct_parent_child_hierarchy():
    """Verify LLM/tool spans are children of synthetic parent."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    synthetic_id = output_spans[0]["id"]

    # All LLM/tool spans should have synthetic parent
    for span in output_spans[1:]:
        if span["name"] != "Agent run - Agent":
            assert span["parent_id"] == synthetic_id


def test_no_langgraph_passthrough():
    """Verify behavior when no LangGraph parent exists."""
    transformer = SpanTransformer()

    # Create spans without LangGraph parent
    input_spans = [
        {
            "id": "span-001",
            "trace_id": "trace-xyz",
            "name": "some_function",
            "parent_id": None,
            "start_time": "2025-01-19T10:00:00.000Z",
            "end_time": "2025-01-19T10:00:05.000Z",
            "status": 1,
            "attributes": {},
        }
    ]

    output_spans = transformer.transform(input_spans)

    # Should pass through unchanged
    assert output_spans == input_spans


def test_synthetic_span_attributes():
    """Verify synthetic span has correct attributes."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    synthetic_span = output_spans[0]

    assert synthetic_span["attributes"]["openinference.span.kind"] == "CHAIN"
    assert synthetic_span["attributes"]["langgraph.simplified"] is True


def test_trace_id_preserved():
    """Verify all spans maintain the same trace_id."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    original_trace_id = input_spans[0]["trace_id"]

    for span in output_spans:
        assert span["trace_id"] == original_trace_id


def test_timing_consistency():
    """Verify synthetic span timing matches LangGraph parent."""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    langgraph_parent = next(s for s in input_spans if s["name"] == "LangGraph")
    synthetic_spans = [s for s in output_spans if s["name"] == "Agent run - Agent"]

    running_span = synthetic_spans[0]
    completed_span = synthetic_spans[1]

    # Both should have same start time as LangGraph parent
    assert running_span["start_time"] == langgraph_parent["start_time"]
    assert completed_span["start_time"] == langgraph_parent["start_time"]

    # Completed should have same end time as LangGraph parent
    assert completed_span["end_time"] == langgraph_parent["end_time"]


def test_guardrail_pattern_transformation():
    """Verify guardrail pattern matches Image #2 output structure."""
    transformer = SpanTransformer()
    input_spans = load_fixture("guardrail_pattern_fixture.json")

    # Verify input structure
    assert len(input_spans) == 15

    # Count input types
    input_guardrails = sum(1 for s in input_spans if "guardrail" in s["name"].lower())
    input_llm = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )
    input_tools = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )

    assert input_guardrails == 2  # input and output guardrails
    assert input_llm == 2  # 2 LLM calls
    assert input_tools == 9  # GET/POST for guardrails, LLM calls, and tool call

    # Run transformation
    output_spans = transformer.transform(input_spans)

    # Verify output structure matches Image #2
    # Expected: synthetic parent (running + completed) + 2 LLM + 9 tools = 13 spans
    assert len(output_spans) == 13

    # Verify synthetic parent exists
    synthetic_spans = [s for s in output_spans if s["name"] == "Agent run - Agent"]
    assert len(synthetic_spans) == 2

    # Verify all LLM spans preserved
    output_llm = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )
    assert output_llm == input_llm

    # Verify all tool spans preserved (including GET/POST from guardrails)
    output_tools = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )
    assert output_tools == input_tools

    # Verify guardrail wrapper spans are buffered (not in output)
    output_guardrail_wrappers = [
        s for s in output_spans if "guardrail check" in s["name"].lower()
    ]
    assert len(output_guardrail_wrappers) == 0

    # Verify Tool call wrapper is buffered
    output_tool_call_wrappers = [
        s for s in output_spans if s["name"] == "Tool call - A_Plus_B"
    ]
    assert len(output_tool_call_wrappers) == 0

    # Verify Agent output node is buffered
    output_agent_output = [s for s in output_spans if s["name"] == "Agent output"]
    assert len(output_agent_output) == 0

    # Verify all preserved spans are reparented to synthetic
    synthetic_id = output_spans[0]["id"]
    for span in output_spans[1:]:
        if span["name"] != "Agent run - Agent":
            assert span["parent_id"] == synthetic_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
