# Phase 0: LangGraph Span Transformation Prototype

## Overview

This prototype validates the core transformation logic for converting verbose LangGraph OpenTelemetry spans into a simplified UiPath schema. It operates on JSON fixtures without any OpenTelemetry SDK dependencies.

## Problem Statement

LangGraph generates 20+ spans per agent execution:
- Parent "LangGraph" span
- Multiple "agent" node spans
- Multiple "action" and "action:*" node spans
- LLM spans (gpt-4o, gpt-4o-mini, etc.)
- Tool call spans (search_people_email, send_email, etc.)
- Various internal/metadata spans

**Goal:** Transform to 5-6 meaningful spans:
- Single synthetic "Agent run - Agent" parent (emitted twice: running + completed)
- LLM spans only
- Tool call spans only

## Transformation Algorithm

### Input Processing

1. **Identify LangGraph Parent**
   - Find span with `name == "LangGraph"`
   - Generate synthetic span ID
   - Extract timing information

2. **Classify Spans**
   - **Buffered (not emitted):** agent, action, action:*, spans with `langgraph.node` attribute
   - **Pass-through (emitted):** Spans with `openinference.span.kind` = "LLM" or "TOOL"
   - **Replaced:** Original LangGraph parent → synthetic "Agent run - Agent"

3. **Emit Progressive States**
   - **Running state** (Status=0, EndTime=null)
   - **LLM/Tool spans** (reparented to synthetic span)
   - **Completed state** (Status=1, EndTime=set)

## Files

### `langgraph_fixture.json`
Realistic test data with 21 spans simulating production LangGraph traces:
- 1 LangGraph parent
- 3 agent node spans
- 2 action node spans
- 2 action:* prefixed spans
- 4 LLM spans (gpt-4o, gpt-4o-mini)
- 2 tool spans
- 7 other internal/metadata spans

### `span_transformer.py`
Core transformation logic (pure Python, no OTEL dependencies):

**Key methods:**
- `transform()` - Main entry point, orchestrates 4-pass algorithm
- `_is_langgraph_parent()` - Identifies root span
- `_is_node_span()` - Detects spans to buffer
- `_is_llm_or_tool_span()` - Detects spans to emit
- `_create_synthetic_parent()` - Generates "Agent run - Agent" span

### `test_transformer.py`
Comprehensive test suite validating:
- ✅ 20+ spans collapse to ~8 spans
- ✅ Progressive state emission (running → completed)
- ✅ All LLM/tool spans preserved
- ✅ Zero node spans in output
- ✅ Correct parent-child hierarchy
- ✅ Timing consistency
- ✅ Trace ID preservation
- ✅ Passthrough behavior when no LangGraph parent

### `output_sample.json`
Expected transformation output showing:
- Synthetic parent (running state)
- 4 LLM spans (reparented)
- 2 tool spans (reparented)
- Synthetic parent (completed state)

Total: 8 spans (down from 21)

## Running Tests

```bash
cd prototype
python -m pytest test_transformer.py -v
```

## Success Criteria

- ✅ Transform 20+ spans → 5-8 meaningful spans
- ✅ Output matches UiPath schema
- ✅ Emit "running" state (Status=0, EndTime=null)
- ✅ Emit "completed" state (Status=1, EndTime=set)
- ✅ 100% test coverage
- ✅ Zero OpenTelemetry SDK dependencies

## Key Behaviors

### Span Buffering
Node spans are **buffered** (not emitted):
- `name == "agent"`
- `name == "action"`
- `name.startswith("action:")`
- `attributes["langgraph.node"]` exists

### Span Pass-Through
LLM/tool spans are **emitted** with reparenting:
- `attributes["openinference.span.kind"] == "LLM"`
- `attributes["openinference.span.kind"] == "TOOL"`
- Parent ID changed to synthetic span

### Synthetic Parent
New "Agent run - Agent" span:
- Replaces original LangGraph parent
- Emitted **twice** (running + completed states)
- All LLM/tool spans become children
- Attributes: `openinference.span.kind=CHAIN`, `langgraph.simplified=true`

## Next Steps

This prototype provides the foundation for Phase 1, where we'll:
1. Integrate with OpenTelemetry SpanProcessor
2. Handle real ReadableSpan objects
3. Export to OTLP backend
4. Test with live LangGraph executions
