# Plan: LangGraph to NotLangGraph Span Transformation

## Summary

Transform verbose LangGraph OpenInference spans into simplified UiPath-native "NotLangGraph" schema by:
1. Replacing root `LangGraph` span with `Agent run - Agent` parent
2. Filtering out intermediate LangGraph node spans (`init`, `agent`, `route_agent`, `terminate`)
3. Converting LLM spans (`UiPathChat`) to UiPath `LLM call` + `Model run` structure
4. Adding guardrail wrapper spans for governance

## Real Data Analysis

### Source: LangGraph.json (8 spans)
```
LangGraph (root, SpanType: CHAIN)
├── init (SpanType: CHAIN) - langgraph_step: 1
├── agent (SpanType: AGENT) - langgraph_step: 2
│   ├── UiPathChat (SpanType: completion, openinference.span.kind: LLM)
│   └── route_agent (SpanType: AGENT)
├── agent (SpanType: AGENT) - langgraph_step: 3
│   ├── UiPathChat (SpanType: completion, openinference.span.kind: LLM)
│   └── route_agent (SpanType: AGENT)
└── terminate (SpanType: CHAIN) - langgraph_step: 4
```

### Target: NOTLangGraph.json (12 spans)
```
Agent run - Agent (root, SpanType: agentRun)
├── Agent input guardrail check (SpanType: agentPreGuardrails)
│   └── Pre-execution governance (SpanType: preGovernance)
├── LLM call (SpanType: completion)
│   ├── LLM input guardrail check (SpanType: llmPreGuardrails)
│   │   └── Pre-execution governance (SpanType: preGovernance)
│   ├── Model run (SpanType: completion) - actual LLM invocation
│   └── LLM output guardrail check (SpanType: llmPostGuardrails)
│       └── Post-execution governance (SpanType: postGovernance)
├── Agent output guardrail check (SpanType: agentPostGuardrails)
│   └── Post-execution governance (SpanType: postGovernance)
└── Agent output (SpanType: agentOutput)
```

## Key Schema Differences

| Field | LangGraph | NOTLangGraph |
|-------|-----------|--------------|
| Id format | UUID string | `00000000-0000-0000-XXXX-XXXXXXXXXXXX` |
| Root span name | `LangGraph` | `Agent run - Agent` |
| Root SpanType | `CHAIN` | `agentRun` |
| LLM SpanType | `completion` | `completion` (but with `LLM call` wrapper) |
| Attributes | OpenInference JSON | UiPath-specific JSON with `type` field |
| Has guardrails | No | Yes (pre/post for agent and LLM) |
| Has governance | No | Yes (policy checks) |

## Transformation Rules

### 1. Root Span Transformation
**Input:** `Name: "LangGraph"`, `SpanType: "CHAIN"`
**Output:** `Name: "Agent run - Agent"`, `SpanType: "agentRun"`

Attributes transformation:
```json
// Input (LangGraph)
{
  "openinference.span.kind": "CHAIN",
  "output.value": "...",
  "session.id": "..."
}

// Output (NOTLangGraph)
{
  "type": "agentRun",
  "agentId": "<extract-from-context>",
  "agentName": "Agent",
  "systemPrompt": "<extract-from-messages>",
  "userPrompt": "<extract-from-messages>",
  "input": {},
  "output": {"content": "<final-output>"}
}
```

### 2. LLM Span Transformation
**Input:** `Name: "UiPathChat"`, `SpanType: "completion"`, `openinference.span.kind: "LLM"`
**Output:** Wrapped structure:

```
LLM call (parent, SpanType: completion)
├── LLM input guardrail check (if guardrails enabled)
│   └── Pre-execution governance
├── Model run (SpanType: completion) - the actual UiPathChat data
└── LLM output guardrail check (if guardrails enabled)
    └── Post-execution governance
```

### 3. Spans to DROP (buffer/filter)
- `init` - LangGraph initialization node
- `agent` - LangGraph agent node wrapper
- `route_agent` - LangGraph routing function
- `terminate` - LangGraph termination node

### 4. Spans to ADD (synthetic)
- `Agent input guardrail check` + `Pre-execution governance`
- `LLM input guardrail check` + `Pre-execution governance`
- `LLM output guardrail check` + `Post-execution governance`
- `Agent output guardrail check` + `Post-execution governance`
- `Agent output`

## Implementation Plan

### Step 1: Create Schema Converter
**File:** `src/uipath/tracing/_langgraph_converter.py`

```python
class LangGraphToUiPathConverter:
    """Converts LangGraph spans to UiPath-native schema."""

    def convert(self, langgraph_spans: List[dict]) -> List[dict]:
        """
        1. Find LangGraph root → create Agent run span
        2. Find UiPathChat spans → create LLM call + Model run
        3. Add guardrail spans if governance enabled
        4. Filter out LangGraph node spans
        5. Reparent all spans to new hierarchy
        """
        pass

    def _create_agent_run_span(self, langgraph_root: dict) -> dict:
        """Transform LangGraph root to Agent run - Agent."""
        pass

    def _create_llm_call_span(self, uipath_chat: dict) -> dict:
        """Transform UiPathChat to LLM call wrapper."""
        pass

    def _create_model_run_span(self, uipath_chat: dict) -> dict:
        """Extract Model run from UiPathChat attributes."""
        pass

    def _create_guardrail_spans(self, parent_id: str, span_type: str) -> List[dict]:
        """Create guardrail + governance spans if enabled."""
        pass
```

### Step 2: Span Detection Patterns

**LangGraph spans to DROP:**
```python
LANGGRAPH_NODE_NAMES = {"init", "agent", "route_agent", "terminate"}

def _is_langgraph_node(span: dict) -> bool:
    name = span.get("Name", "")
    attrs = span.get("Attributes", "{}")

    # Check name patterns
    if name in LANGGRAPH_NODE_NAMES:
        return True

    # Check for langgraph metadata
    if "langgraph_node" in attrs or "langgraph_step" in attrs:
        return True

    return False
```

**LLM spans to CONVERT:**
```python
def _is_llm_span(span: dict) -> bool:
    return (
        span.get("SpanType") == "completion" and
        "openinference.span.kind" in span.get("Attributes", "") and
        '"LLM"' in span.get("Attributes", "")
    )
```

### Step 3: Integration with SpanProcessor

**File:** `src/uipath/tracing/_langgraph_processor.py`

```python
class LangGraphCollapsingSpanProcessor(SpanProcessor):
    def __init__(self, next_processor: SpanProcessor, enable_guardrails: bool = True):
        self.next_processor = next_processor
        self.enable_guardrails = enable_guardrails
        self.converter = LangGraphToUiPathConverter()
        self.span_buffer: Dict[str, List[dict]] = {}  # trace_id -> spans

    def on_end(self, span: ReadableSpan):
        trace_id = format(span.get_span_context().trace_id, '032x')

        # Buffer span
        if trace_id not in self.span_buffer:
            self.span_buffer[trace_id] = []
        self.span_buffer[trace_id].append(self._span_to_dict(span))

        # If LangGraph root completed, convert and emit
        if span.name == "LangGraph" and span.end_time:
            converted = self.converter.convert(
                self.span_buffer[trace_id],
                enable_guardrails=self.enable_guardrails
            )
            for out_span in converted:
                self._emit_span(out_span)
            del self.span_buffer[trace_id]
```

### Step 4: Attribute Transformation

**LangGraph Attributes → UiPath Attributes:**

```python
def _transform_attributes(self, langgraph_attrs: dict, span_type: str) -> str:
    """Convert OpenInference attributes to UiPath format."""

    if span_type == "agentRun":
        return json.dumps({
            "type": "agentRun",
            "agentId": self._extract_agent_id(langgraph_attrs),
            "agentName": "Agent",
            "systemPrompt": self._extract_system_prompt(langgraph_attrs),
            "userPrompt": self._extract_user_prompt(langgraph_attrs),
            "input": {},
            "output": self._extract_output(langgraph_attrs),
            "error": None
        })

    elif span_type == "completion":
        return json.dumps({
            "type": "completion",
            "model": langgraph_attrs.get("llm.model_name"),
            "settings": {
                "maxTokens": langgraph_attrs.get("settings", {}).get("maxTokens"),
                "temperature": langgraph_attrs.get("settings", {}).get("temperature")
            },
            "usage": {
                "completionTokens": langgraph_attrs.get("usage", {}).get("completionTokens"),
                "promptTokens": langgraph_attrs.get("usage", {}).get("promptTokens"),
                "totalTokens": langgraph_attrs.get("usage", {}).get("totalTokens")
            },
            "error": None
        })
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/uipath/tracing/_langgraph_converter.py` | CREATE - Schema conversion logic |
| `src/uipath/tracing/_langgraph_processor.py` | CREATE - SpanProcessor wrapper |
| `src/uipath/tracing/__init__.py` | MODIFY - Export new classes |
| `src/uipath/_cli/_runtime/_contracts.py` | MODIFY - Wire processor into pipeline |
| `tests/test_langgraph_converter.py` | CREATE - Unit tests |

## Feature Flag Configuration

```bash
UIPATH_LANGGRAPH_SIMPLIFY=true      # Enable transformation
UIPATH_LANGGRAPH_GUARDRAILS=true    # Add guardrail spans (default: true)
```

## Transformation Summary

| LangGraph Input | NotLangGraph Output |
|-----------------|---------------------|
| `LangGraph` (root) | `Agent run - Agent` |
| `init` | DROPPED |
| `agent` | DROPPED |
| `UiPathChat` | `LLM call` → `Model run` |
| `route_agent` | DROPPED |
| `terminate` | DROPPED |
| N/A | `Agent input guardrail check` (added) |
| N/A | `LLM input guardrail check` (added) |
| N/A | `LLM output guardrail check` (added) |
| N/A | `Agent output guardrail check` (added) |
| N/A | `Agent output` (added) |
| N/A | `Pre/Post-execution governance` (added) |

## Edge Cases

1. **Multiple LLM calls** - Each `UiPathChat` becomes its own `LLM call` subtree
2. **No guardrails configured** - Skip guardrail span creation
3. **Error in LangGraph** - Propagate error status to `Agent run` span
4. **Nested LangGraph** - Only transform root-level LangGraph spans
5. **Non-LangGraph traces** - Pass through unchanged
