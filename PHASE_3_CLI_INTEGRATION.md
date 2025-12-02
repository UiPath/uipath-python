# Phase 3: CLI Integration

**Timeline:** Week 2, Days 3-4
**Goal:** Integrate processor into uipath-langchain CLI

## Overview

Integrates LangGraphCollapsingSpanProcessor into the uipath-langchain CLI instrumentation pipeline, with feature flag control for gradual rollout.

## Prerequisites

- ✅ Phase 2 completed
- ✅ Processor validated with real agent
- ✅ Edge cases handled

## Tasks

### 1. Add Feature Flag

**Objective:** Environment variable to enable/disable processor

**Implementation options:**

**Option A: Environment Variable (Simple)**
```python
import os

def _should_enable_langgraph_simplification() -> bool:
    """Check if LangGraph simplification should be enabled."""
    return os.getenv("UIPATH_LANGGRAPH_SIMPLIFY", "false").lower() == "true"
```

**Option B: Feature Flag API (Production)**
```python
from uipath.feature_flags import FeatureFlagClient

def _should_enable_langgraph_simplification(org_id: str) -> bool:
    """Check feature flag via API."""
    client = FeatureFlagClient()
    return client.is_enabled("langgraph-simplification", org_id)
```

**For Phase 3, use Option A (env var).**

### 2. Wire into Instrumentation Pipeline

**Modify:** `src/uipath_langchain/_cli/cli_run.py` (or equivalent instrumentation setup file)

**Current structure** (approximate):
```python
def create_instrumentation(runtime_factory):
    """Setup OpenTelemetry instrumentation."""

    # Create tracer provider
    provider = TracerProvider(resource=Resource.create({...}))

    # Create exporter
    exporter = LlmOpsHttpExporter(
        endpoint=config.llmops_endpoint,
        api_key=config.api_key
    )

    # Add span processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set global provider
    trace.set_tracer_provider(provider)

    # Instrument libraries
    LangChainInstrumentor().instrument()
```

**Modified structure** (with LangGraph processor):
```python
from uipath.tracing._langgraph_processor import LangGraphCollapsingSpanProcessor

def create_instrumentation(runtime_factory):
    """Setup OpenTelemetry instrumentation."""

    # Create tracer provider
    provider = TracerProvider(resource=Resource.create({...}))

    # Create exporter
    exporter = LlmOpsHttpExporter(
        endpoint=config.llmops_endpoint,
        api_key=config.api_key
    )

    # Chain processors based on feature flag
    if _should_enable_langgraph_simplification():
        # LangGraph processor → Batch processor → Exporter
        batch_processor = BatchSpanProcessor(exporter)
        langgraph_processor = LangGraphCollapsingSpanProcessor(
            next_processor=batch_processor
        )
        provider.add_span_processor(langgraph_processor)
        print("✨ LangGraph span simplification enabled")
    else:
        # Default: Batch processor → Exporter
        batch_processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(batch_processor)

    # Set global provider
    trace.set_tracer_provider(provider)

    # Instrument libraries
    LangChainInstrumentor().instrument()

def _should_enable_langgraph_simplification() -> bool:
    """
    Check if LangGraph simplification should be enabled.

    Controlled by UIPATH_LANGGRAPH_SIMPLIFY environment variable.
    """
    enabled = os.getenv("UIPATH_LANGGRAPH_SIMPLIFY", "false").lower() == "true"
    return enabled
```

**Key points:**
- LangGraphCollapsingProcessor inserted BEFORE BatchSpanProcessor
- Feature flag checked once at startup
- Default: disabled (safe rollout)
- Logging to indicate when enabled

### 3. Integration Tests

**Create:** `tests/cli/test_langgraph_simplification_integration.py`

```python
import os
import pytest
import subprocess
import json
from pathlib import Path

@pytest.fixture
def sample_agent_script(tmp_path):
    """Create sample agent script for testing."""
    script = tmp_path / "test_agent.py"
    script.write_text("""
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def add(a: int, b: int) -> int:
    return a + b

llm = ChatOpenAI(model="gpt-4o-mini")
agent = create_react_agent(llm, [add])
result = agent.invoke({"messages": [("user", "What is 5 + 3?")]})
print(result["messages"][-1].content)
""")
    return script

def test_simplification_enabled(sample_agent_script, tmp_path):
    """Test CLI with simplification enabled."""

    # Set environment variable
    env = os.environ.copy()
    env["UIPATH_LANGGRAPH_SIMPLIFY"] = "true"
    env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    # Run CLI
    result = subprocess.run(
        ["uipath", "run", str(sample_agent_script)],
        env=env,
        capture_output=True,
        text=True
    )

    # Check that simplification message printed
    assert "LangGraph span simplification enabled" in result.stdout or result.stderr

    # TODO: Capture and validate exported spans
    # This requires mocking the exporter or capturing HTTP requests

def test_simplification_disabled(sample_agent_script):
    """Test CLI with simplification disabled (default)."""

    env = os.environ.copy()
    env["UIPATH_LANGGRAPH_SIMPLIFY"] = "false"
    env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

    result = subprocess.run(
        ["uipath", "run", str(sample_agent_script)],
        env=env,
        capture_output=True,
        text=True
    )

    # Should NOT see simplification message
    assert "LangGraph span simplification enabled" not in result.stdout
    assert "LangGraph span simplification enabled" not in result.stderr

def test_feature_flag_toggle():
    """Test feature flag function."""
    from uipath_langchain._cli.cli_run import _should_enable_langgraph_simplification

    # Test enabled
    os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "true"
    assert _should_enable_langgraph_simplification() is True

    # Test disabled
    os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "false"
    assert _should_enable_langgraph_simplification() is False

    # Test default (not set)
    if "UIPATH_LANGGRAPH_SIMPLIFY" in os.environ:
        del os.environ["UIPATH_LANGGRAPH_SIMPLIFY"]
    assert _should_enable_langgraph_simplification() is False

    # Test case insensitive
    os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "TRUE"
    assert _should_enable_langgraph_simplification() is True

    os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "True"
    assert _should_enable_langgraph_simplification() is True
```

**Run:**
```bash
pytest tests/cli/test_langgraph_simplification_integration.py -v
```

### 4. Update Documentation

**Create:** `docs/LANGGRAPH_SIMPLIFICATION.md`

```markdown
# LangGraph Span Simplification

## Overview

The LangGraph span simplification feature reduces verbose LangGraph execution traces by collapsing internal node spans into a single "Agent run - Agent" parent span.

## Before and After

**Before (20+ spans):**
```
LangGraph
├── agent
├── action:tool1
├── tool1
├── agent
├── gpt-4o
├── agent
└── ... (15+ more)
```

**After (5-6 spans):**
```
Agent run - Agent
├── gpt-4o
├── tool1
└── gpt-4o
```

## Enabling the Feature

### Environment Variable

```bash
export UIPATH_LANGGRAPH_SIMPLIFY=true
uipath run your_agent.py
```

### In Code

```python
import os
os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "true"

# Then run your agent normally
```

## How It Works

1. **Intercepts spans** before export via SpanProcessor
2. **Buffers node spans** (agent/action) - not exported
3. **Passes through** LLM and tool call spans
4. **Creates synthetic parent** "Agent run - Agent"
5. **Emits progressive states:**
   - Running state: Status=0, EndTime=null
   - Completed state: Status=1, EndTime=set

## Benefits

- **Reduced noise:** 60%+ fewer spans
- **Better UX:** Single parent span instead of 20+ nodes
- **Progressive updates:** See "running" state in real-time
- **No code changes:** Works with existing agents

## Compatibility

- ✅ Works with `create_react_agent`
- ✅ Works with custom LangGraph agents
- ✅ Preserves all LLM and tool call spans
- ✅ Backward compatible (disabled by default)

## Troubleshooting

**Feature not working:**
- Check env var is set: `echo $UIPATH_LANGGRAPH_SIMPLIFY`
- Check logs for "LangGraph span simplification enabled"

**Spans still verbose:**
- Feature only affects LangGraph executions
- Other frameworks (LangChain, etc.) unaffected

**Missing spans:**
- LLM and tool spans should be preserved
- If missing, file a bug report
```

## Success Criteria

- ✅ Feature flag correctly enables/disables processor
- ✅ Real agent execution produces simplified traces
- ✅ LLM/tool call spans preserved
- ✅ Node spans collapsed
- ✅ Integration tests pass
- ✅ Documentation complete
- ✅ Backward compatible (default disabled)

## Deliverables

1. Modified `cli_run.py` with processor integration
2. `tests/cli/test_langgraph_simplification_integration.py`
3. `docs/LANGGRAPH_SIMPLIFICATION.md`
4. Updated CLI help text (optional)

## Timeline

- **Day 3 AM:** Implement feature flag check
- **Day 3 PM:** Wire processor into CLI pipeline
- **Day 4 AM:** Write integration tests
- **Day 4 PM:** Write documentation, test end-to-end

## Testing Checklist

- [ ] Feature flag toggles processor on/off
- [ ] Processor chained correctly with BatchSpanProcessor
- [ ] Real agent run with flag=true produces simplified spans
- [ ] Real agent run with flag=false produces normal spans
- [ ] No errors or crashes in either mode
- [ ] Documentation clear and accurate

## Usage Examples

**Example 1: Enable for single run**
```bash
UIPATH_LANGGRAPH_SIMPLIFY=true uipath run my_agent.py
```

**Example 2: Enable globally**
```bash
echo 'export UIPATH_LANGGRAPH_SIMPLIFY=true' >> ~/.zshrc
source ~/.zshrc
uipath run my_agent.py
```

**Example 3: Enable in Python**
```python
import os
os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "true"

from langgraph.prebuilt import create_react_agent
# ... rest of code
```

## Next Steps

After Phase 3:
- Phase 4: Backend API updates for span upserts
- Phase 5: UI real-time updates
- Phase 6: Production rollout with LaunchDarkly
