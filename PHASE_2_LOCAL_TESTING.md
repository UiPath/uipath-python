# Phase 2: Local Testing with Real Agent

**Timeline:** Week 2, Days 1-2
**Goal:** Test processor with actual LangGraph execution

## Overview

Validates SpanProcessor works correctly with real LangGraph agent, not just mocks. Creates test agent, runs locally, captures exported spans, verifies transformation matches prototype output.

## Prerequisites

- ✅ Phase 1 completed
- ✅ LangGraphCollapsingSpanProcessor implemented
- ✅ Unit tests passing (90%+ coverage)

## Tasks

### 1. Create Test Agent Script

**Objective:** Simple ReAct agent with 2-3 tools for testing

**Create:** `tests/integration/test_real_agent.py`

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from uipath.tracing._langgraph_processor import LangGraphCollapsingSpanProcessor
from openinference.instrumentation.langchain import LangChainInstrumentor
import json

# Define test tools
@tool
def search_people_email(name: str) -> str:
    """Search for person's email by name."""
    return f"{name.lower().replace(' ', '.')}@example.com"

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send email to recipient."""
    return f"Email sent to {to} with subject '{subject}'"

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

def setup_instrumentation():
    """Setup OTEL instrumentation with LangGraphCollapsingSpanProcessor."""

    # Create tracer provider
    provider = TracerProvider()

    # Capture spans to memory for validation
    captured_spans = []

    class CapturingExporter:
        """Custom exporter that captures spans for testing."""
        def export(self, spans):
            for span in spans:
                if isinstance(span, dict):
                    captured_spans.append(span)
                else:
                    # Convert ReadableSpan to dict
                    captured_spans.append({
                        "name": span.name,
                        "trace_id": format(span.get_span_context().trace_id, '032x'),
                        "span_id": format(span.get_span_context().span_id, '016x'),
                        "start_time": span.start_time,
                        "end_time": span.end_time,
                        "attributes": dict(span.attributes) if span.attributes else {}
                    })
            return 0  # Success

        def shutdown(self):
            pass

    capturing_exporter = CapturingExporter()

    # Add LangGraphCollapsingProcessor
    processor = LangGraphCollapsingSpanProcessor(
        next_processor=BatchSpanProcessor(capturing_exporter)
    )

    provider.add_span_processor(processor)

    # Instrument LangChain
    LangChainInstrumentor().instrument(tracer_provider=provider)

    return captured_spans

def test_agent_with_processor():
    """Test LangGraph agent with span processor."""

    # Setup instrumentation
    captured_spans = setup_instrumentation()

    # Create LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Create tools
    tools = [search_people_email, send_email, get_weather]

    # Create agent
    agent = create_react_agent(llm, tools)

    # Run agent
    result = agent.invoke({
        "messages": [("user", "Find John Doe's email and send him a message about the weather in San Francisco")]
    })

    # Force flush to ensure all spans captured
    # (In real usage, this happens automatically)

    # Analyze captured spans
    print(f"\nCaptured {len(captured_spans)} spans:")

    # Save to file for inspection
    with open("tests/integration/captured_spans.json", "w") as f:
        json.dump(captured_spans, f, indent=2, default=str)

    # Validations
    synthetic_spans = [s for s in captured_spans if s["name"] == "Agent run - Agent"]
    node_spans = [s for s in captured_spans if s["name"] in ["agent", "action"]]
    llm_spans = [s for s in captured_spans
                 if s.get("attributes", {}).get("openinference.span.kind") == "LLM"]
    tool_spans = [s for s in captured_spans
                  if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"]

    print(f"  Synthetic 'Agent run - Agent' spans: {len(synthetic_spans)}")
    print(f"  Node spans (should be 0): {len(node_spans)}")
    print(f"  LLM spans: {len(llm_spans)}")
    print(f"  Tool spans: {len(tool_spans)}")

    # Assertions
    assert len(synthetic_spans) == 2, "Should have 2 synthetic spans (running + completed)"
    assert len(node_spans) == 0, "Should have 0 node spans (all buffered)"
    assert len(llm_spans) > 0, "Should have LLM spans"
    assert len(tool_spans) > 0, "Should have tool spans"

    # Check synthetic span states
    running_span = [s for s in synthetic_spans if s.get("status") == 0]
    completed_span = [s for s in synthetic_spans if s.get("status") == 1]

    assert len(running_span) == 1, "Should have 1 running state"
    assert len(completed_span) == 1, "Should have 1 completed state"
    assert running_span[0]["end_time"] is None, "Running span should have no end_time"
    assert completed_span[0]["end_time"] is not None, "Completed span should have end_time"

    print("\n✅ All validations passed!")
    print(f"\nAgent result: {result['messages'][-1].content}")

if __name__ == "__main__":
    test_agent_with_processor()
```

**Run:**
```bash
export OPENAI_API_KEY="your-key"
python tests/integration/test_real_agent.py
```

### 2. Validate Transformation

**Objective:** Compare exported spans to prototype output

**Create:** `tests/integration/validate_spans.py`

```python
import json

def validate_span_transformation(captured_spans_file: str):
    """Validate captured spans match expected transformation."""

    with open(captured_spans_file) as f:
        spans = json.load(f)

    print(f"Analyzing {len(spans)} captured spans...")

    # Group by type
    synthetic = [s for s in spans if s["name"] == "Agent run - Agent"]
    nodes = [s for s in spans if s["name"] in ["agent", "action"] or s["name"].startswith("action:")]
    llms = [s for s in spans if s.get("attributes", {}).get("openinference.span.kind") == "LLM"]
    tools = [s for s in spans if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"]

    print("\n📊 Span Breakdown:")
    print(f"  Synthetic parent: {len(synthetic)}")
    print(f"  Node spans (buffered): {len(nodes)}")
    print(f"  LLM spans: {len(llms)}")
    print(f"  Tool spans: {len(tools)}")

    # Validate transformation
    checks = []

    # Check 1: Exactly 2 synthetic spans
    checks.append(("2 synthetic spans (running + completed)", len(synthetic) == 2))

    # Check 2: No node spans in output
    checks.append(("0 node spans in output", len(nodes) == 0))

    # Check 3: Synthetic spans have correct states
    if len(synthetic) == 2:
        running = [s for s in synthetic if s.get("status") == 0]
        completed = [s for s in synthetic if s.get("status") == 1]
        checks.append(("1 running state", len(running) == 1))
        checks.append(("1 completed state", len(completed) == 1))

        if running:
            checks.append(("Running has no end_time", running[0]["end_time"] is None))
        if completed:
            checks.append(("Completed has end_time", completed[0]["end_time"] is not None))

    # Check 4: LLM/tool spans preserved
    checks.append(("LLM spans preserved", len(llms) > 0))
    checks.append(("Tool spans preserved", len(tools) > 0))

    # Check 5: Total span count reduced
    # Original would have ~20+ spans, we should have < 10
    checks.append(("Span count reduced", len(spans) < 10))

    # Print results
    print("\n✅ Validation Results:")
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")

    all_passed = all(passed for _, passed in checks)

    if all_passed:
        print("\n🎉 All validations passed! Transformation working correctly.")
    else:
        print("\n⚠️ Some validations failed. Review spans.")

    return all_passed

if __name__ == "__main__":
    validate_span_transformation("tests/integration/captured_spans.json")
```

**Run:**
```bash
python tests/integration/validate_spans.py
```

### 3. Debug and Refine

**Objective:** Fix edge cases found during testing

**Common issues to watch for:**

1. **Orphaned node spans** (node span arrives before LangGraph parent)
   - Solution: Buffer temporarily, associate when parent arrives

2. **Nested LangGraph invocations** (agent calls another agent)
   - Solution: Track by trace_id, handle nested executions

3. **Missing attributes** on synthetic span
   - Solution: Copy all relevant attributes from original parent

4. **Timing issues** (running state emitted after completion)
   - Solution: Ensure order of emission is correct

5. **Memory leaks** from unbounded buffer
   - Solution: Add max buffer size, cleanup old executions

**Create:** `tests/integration/edge_cases_test.py`

```python
import pytest
from tests.integration.test_real_agent import setup_instrumentation, create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def simple_tool(x: int) -> int:
    """Simple tool for testing."""
    return x * 2

def test_empty_agent_run():
    """Test agent that completes without calling tools."""
    captured_spans = setup_instrumentation()

    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(llm, [simple_tool])

    result = agent.invoke({"messages": [("user", "Just say hello")]})

    # Should still have synthetic spans even without tool calls
    synthetic = [s for s in captured_spans if s["name"] == "Agent run - Agent"]
    assert len(synthetic) == 2

def test_multiple_sequential_runs():
    """Test multiple agent runs in sequence."""
    captured_spans = setup_instrumentation()

    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(llm, [simple_tool])

    # Run 1
    agent.invoke({"messages": [("user", "Calculate 5 * 2")]})

    # Run 2
    agent.invoke({"messages": [("user", "Calculate 10 * 2")]})

    # Should have 4 synthetic spans (2 per run)
    synthetic = [s for s in captured_spans if s["name"] == "Agent run - Agent"]
    assert len(synthetic) == 4

def test_agent_with_error():
    """Test agent that encounters error."""
    captured_spans = setup_instrumentation()

    @tool
    def failing_tool(x: int) -> int:
        """Tool that always fails."""
        raise ValueError("Intentional error")

    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(llm, [failing_tool])

    try:
        agent.invoke({"messages": [("user", "Use the failing tool")]})
    except Exception:
        pass  # Expected

    # Should still emit completed state (with error status)
    synthetic = [s for s in captured_spans if s["name"] == "Agent run - Agent"]
    completed = [s for s in synthetic if s.get("status") in [1, 2]]
    assert len(completed) >= 1
```

**Run:**
```bash
pytest tests/integration/edge_cases_test.py -v
```

## Success Criteria

- ✅ Real LangGraph agent runs successfully
- ✅ Processor correctly transforms spans
- ✅ Node spans are buffered (not in output)
- ✅ LLM/tool spans preserved
- ✅ Synthetic span emitted with both states
- ✅ Total span count reduced by 60%+
- ✅ Edge cases handled correctly
- ✅ No errors or crashes

## Deliverables

1. `tests/integration/test_real_agent.py` - Test agent with processor
2. `tests/integration/validate_spans.py` - Validation script
3. `tests/integration/edge_cases_test.py` - Edge case tests
4. `tests/integration/captured_spans.json` - Sample output
5. Test results documentation

## Timeline

- **Day 1 AM:** Create test agent script
- **Day 1 PM:** Run agent, capture spans, initial validation
- **Day 2 AM:** Write validation script, edge case tests
- **Day 2 PM:** Debug issues, refine processor

## Debugging Tips

**Enable verbose logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("uipath.tracing._langgraph_processor")
logger.setLevel(logging.DEBUG)
```

**Print spans as they're processed:**
```python
def on_end(self, span: ReadableSpan):
    print(f"Processing span: {span.name}, trace: {trace_id}")
    # ... rest of logic
```

**Compare before/after:**
```bash
# Run without processor
python test_agent_baseline.py > baseline_spans.json

# Run with processor
python test_real_agent.py > processed_spans.json

# Diff
diff baseline_spans.json processed_spans.json
```
