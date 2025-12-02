# Phase 0: Prototype & Simulation

**Timeline:** Week 1, Days 1-3
**Goal:** Validate transformation logic with simulated data before touching real system

## Overview

This phase focuses on building a standalone prototype that simulates the exact transformation we need: taking verbose LangGraph OpenTelemetry spans and converting them into the simplified UiPath schema. By working with fixtures first, we can iterate quickly without dependencies on the real system.

## Tasks

### 1. Create Test Fixture with Realistic LangGraph Span Data

**Objective:** Build JSON fixtures simulating raw OpenTelemetry spans from LangGraph

**Implementation:**
- Create `prototype/langgraph_fixture.json` containing realistic span data
- Include all span types observed in production:
  - Parent "LangGraph" span (root of execution)
  - Node spans: "agent", "action", "action:tool_name"
  - LLM spans: "gpt-4o", "gpt-4o-mini", etc.
  - Tool call spans: "search_people_email", "send_email", etc.
- Mirror exact structure from production traces (reference Image #1)

**Example structure:**
```json
{
  "spans": [
    {
      "id": "span-001",
      "trace_id": "trace-abc",
      "name": "LangGraph",
      "parent_id": null,
      "start_time": "2025-01-19T10:00:00.000Z",
      "end_time": "2025-01-19T10:00:45.000Z",
      "status": 1,
      "attributes": {
        "openinference.span.kind": "CHAIN"
      }
    },
    {
      "id": "span-002",
      "trace_id": "trace-abc",
      "name": "agent",
      "parent_id": "span-001",
      "start_time": "2025-01-19T10:00:01.000Z",
      "end_time": "2025-01-19T10:00:05.000Z",
      "status": 1,
      "attributes": {
        "langgraph.node": "agent"
      }
    },
    {
      "id": "span-003",
      "trace_id": "trace-abc",
      "name": "gpt-4o",
      "parent_id": "span-002",
      "start_time": "2025-01-19T10:00:02.000Z",
      "end_time": "2025-01-19T10:00:04.000Z",
      "status": 1,
      "attributes": {
        "llm.model_name": "gpt-4o",
        "openinference.span.kind": "LLM"
      }
    }
  ]
}
```

### 2. Implement Standalone Transformation Module

**Objective:** Create pure Python transformation logic without OTEL dependencies

**Create:** `prototype/span_transformer.py`

**Core functions:**
```python
class SpanTransformer:
    def __init__(self):
        self.buffered_spans = []
        self.synthetic_span_id = None

    def transform(self, input_spans: List[dict]) -> List[dict]:
        """
        Transform LangGraph spans to UiPath schema.

        Input: Raw OTEL spans (20+ spans)
        Output: Simplified UiPath spans (5-6 spans)
        """
        pass

    def _is_langgraph_parent(self, span: dict) -> bool:
        """Check if span is LangGraph root"""
        return span["name"] == "LangGraph"

    def _is_node_span(self, span: dict) -> bool:
        """Check if span should be buffered (agent/action)"""
        return (
            span["name"] in ["agent", "action"] or
            span["name"].startswith("action:") or
            "langgraph.node" in span.get("attributes", {})
        )

    def _is_llm_or_tool_span(self, span: dict) -> bool:
        """Check if span should pass through"""
        kind = span.get("attributes", {}).get("openinference.span.kind")
        return kind in ["LLM", "TOOL"]

    def _create_synthetic_parent(self, langgraph_span: dict, is_final: bool) -> dict:
        """Create 'Agent run - Agent' synthetic span"""
        return {
            "id": self.synthetic_span_id,
            "trace_id": langgraph_span["trace_id"],
            "name": "Agent run - Agent",
            "parent_id": None,
            "start_time": langgraph_span["start_time"],
            "end_time": langgraph_span["end_time"] if is_final else None,
            "status": 1 if is_final else 0,  # 0=running, 1=completed
            "attributes": {
                "openinference.span.kind": "CHAIN",
                "langgraph.simplified": True
            }
        }
```

**Key logic:**
- Input: List of raw OTEL spans (dict format)
- Output: List of UiPath schema spans
- No OpenTelemetry SDK dependencies yet
- Pure data transformation

### 3. Build Buffer/Collapse Logic

**Objective:** Implement the core transformation algorithm

**Algorithm:**
```python
def transform(self, input_spans: List[dict]) -> List[dict]:
    output_spans = []
    langgraph_parent = None

    # Pass 1: Identify LangGraph parent and generate synthetic ID
    for span in input_spans:
        if self._is_langgraph_parent(span):
            langgraph_parent = span
            self.synthetic_span_id = f"synthetic-{uuid.uuid4()}"
            break

    if not langgraph_parent:
        # No LangGraph execution found, pass through all spans
        return input_spans

    # Pass 2: Emit "running" state immediately
    running_span = self._create_synthetic_parent(langgraph_parent, is_final=False)
    output_spans.append(running_span)

    # Pass 3: Process all spans
    for span in input_spans:
        if self._is_langgraph_parent(span):
            # Skip original parent (replaced by synthetic)
            continue
        elif self._is_node_span(span):
            # Buffer (don't emit)
            self.buffered_spans.append(span)
        elif self._is_llm_or_tool_span(span):
            # Pass through, but reparent to synthetic span
            output_span = span.copy()
            output_span["parent_id"] = self.synthetic_span_id
            output_spans.append(output_span)

    # Pass 4: Emit "completed" state
    completed_span = self._create_synthetic_parent(langgraph_parent, is_final=True)
    output_spans.append(completed_span)

    return output_spans
```

**Key behaviors:**
- Identify LangGraph parent by name
- Buffer node spans (agent/action) - don't emit
- Pass through LLM/tool spans immediately
- Reparent LLM/tool spans to synthetic parent
- Create synthetic "Agent run - Agent" parent
- Emit twice: running state (Status=0), completed state (Status=1)

### 4. Validate Output Schema

**Objective:** Ensure output matches UiPath schema from Image #2

**Create:** `prototype/test_transformer.py`

**Test cases:**
```python
import pytest
from span_transformer import SpanTransformer

def test_collapse_20_spans_to_5():
    """Verify 20+ input spans become 5-6 output spans"""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")

    assert len(input_spans) >= 20

    output_spans = transformer.transform(input_spans)

    # Should have: 1 synthetic parent + LLM/tool spans only
    assert len(output_spans) <= 8
    assert output_spans[0]["name"] == "Agent run - Agent"

def test_progressive_states():
    """Verify running → completed state emission"""
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
    """Verify LLM and tool call spans are kept"""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    # Count LLM spans in input
    input_llm_count = sum(1 for s in input_spans
                          if s.get("attributes", {}).get("openinference.span.kind") == "LLM")

    # Count LLM spans in output
    output_llm_count = sum(1 for s in output_spans
                           if s.get("attributes", {}).get("openinference.span.kind") == "LLM")

    assert input_llm_count == output_llm_count

def test_node_spans_buffered():
    """Verify agent/action spans are NOT in output"""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    # Should have NO node spans in output
    node_spans = [s for s in output_spans if s["name"] in ["agent", "action"]]
    assert len(node_spans) == 0

def test_correct_parent_child_hierarchy():
    """Verify LLM/tool spans are children of synthetic parent"""
    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")
    output_spans = transformer.transform(input_spans)

    synthetic_id = output_spans[0]["id"]

    # All LLM/tool spans should have synthetic parent
    for span in output_spans[1:]:
        if span["name"] != "Agent run - Agent":
            assert span["parent_id"] == synthetic_id
```

**Validation criteria:**
- ✅ Input: 20+ spans → Output: 5-6 spans
- ✅ Output has single "Agent run - Agent" parent
- ✅ Output has 2 versions of synthetic span (running + completed)
- ✅ All LLM/tool spans preserved as children
- ✅ Zero node spans (agent/action) in output
- ✅ Correct parent-child hierarchy

### 5. Generate Sample Output

**Create:** `prototype/output_sample.json`

**Expected output matching Image #2:**
```json
{
  "spans": [
    {
      "id": "synthetic-abc-001",
      "trace_id": "trace-abc",
      "name": "Agent run - Agent",
      "parent_id": null,
      "start_time": "2025-01-19T10:00:00.000Z",
      "end_time": null,
      "status": 0,
      "attributes": {
        "openinference.span.kind": "CHAIN",
        "langgraph.simplified": true
      }
    },
    {
      "id": "span-003",
      "trace_id": "trace-abc",
      "name": "gpt-4o",
      "parent_id": "synthetic-abc-001",
      "start_time": "2025-01-19T10:00:02.000Z",
      "end_time": "2025-01-19T10:00:04.000Z",
      "status": 1,
      "attributes": {
        "llm.model_name": "gpt-4o",
        "openinference.span.kind": "LLM"
      }
    },
    {
      "id": "span-007",
      "trace_id": "trace-abc",
      "name": "search_people_email",
      "parent_id": "synthetic-abc-001",
      "start_time": "2025-01-19T10:00:10.000Z",
      "end_time": "2025-01-19T10:00:12.000Z",
      "status": 1,
      "attributes": {
        "openinference.span.kind": "TOOL"
      }
    },
    {
      "id": "synthetic-abc-001",
      "trace_id": "trace-abc",
      "name": "Agent run - Agent",
      "parent_id": null,
      "start_time": "2025-01-19T10:00:00.000Z",
      "end_time": "2025-01-19T10:00:45.000Z",
      "status": 1,
      "attributes": {
        "openinference.span.kind": "CHAIN",
        "langgraph.simplified": true
      }
    }
  ]
}
```

## Success Criteria

- ✅ Transform 20+ spans → 5-6 meaningful spans
- ✅ Output matches exact schema from Image #2
- ✅ Can emit "running" state (Status=0, EndTime=null)
- ✅ Can emit "completed" state (Status=1, EndTime=set)
- ✅ 100% test coverage for transformation logic
- ✅ No dependencies on OpenTelemetry SDK (pure Python)

## Deliverables

1. **`prototype/langgraph_fixture.json`** - Realistic test data with 20+ spans
2. **`prototype/span_transformer.py`** - Core transformation logic
3. **`prototype/test_transformer.py`** - Comprehensive unit tests
4. **`prototype/output_sample.json`** - Expected UiPath schema output
5. **`prototype/README.md`** - Documentation of prototype design

## Timeline

- **Day 1:** Create fixtures and basic transformer structure
- **Day 2:** Implement transformation logic and buffering
- **Day 3:** Write tests, validate output, refine edge cases

## Notes

- This phase has ZERO dependencies on real system
- Can iterate quickly on transformation logic
- Validates the approach before building real integration
- All team members can review/test the transformation independently
- Output from this phase becomes the spec for Phase 1
