# LangGraph to UiPath Schema Transformation - Visual Comparison

## Overview

This document shows the before/after transformation of the trace structure from Image #1.

## Transformation Summary

**Input:** 23 spans → **Output:** 15 spans
**Reduction:** 8 spans removed (34.8%)
**Preservation:** 100% of LLM and tool spans maintained

---

## Input Structure (23 Spans)

```
LangGraph (root)                                    [4.36s]
├── GET                                             [96ms]   ← TOOL
├── POST                                            [4.22s]  ← TOOL
├── processes_invoke                                [0ms]
├── POST                                            [411ms]  ← TOOL
├── GET                                             [187ms]  ← TOOL
│
├── LangGraph (nested #1)                           [1.65s]
│   ├── GET                                         [80ms]   ← TOOL
│   ├── POST                                        [154ms]  ← TOOL
│   ├── processes_invoke                            [0ms]
│   ├── POST                                        [308ms]  ← TOOL
│   └── GET                                         [196ms]  ← TOOL
│
├── LangGraph (nested #2)                           [1.33s]
│   ├── A_Plus_B                                    [3ms]
│   │   └── A_Plus_B (tool)                        [1ms]    ← TOOL
│   │
│   ├── agent                                       [1.32s]  ⚠️ NODE
│   │   ├── UiPathChat (gpt-4.1-2025-04-14)       [1.23s]  ← LLM
│   │   └── route_agent                            [1ms]
│   │
│   └── A_Plus_B                                    [5ms]
│       └── A_Plus_B (tool)                        [2ms]    ← TOOL
│
├── GET                                             [80ms]   ← TOOL
├── POST                                            [1.23s]  ← TOOL
└── processes_invoke                                [1ms]
```

**Span Types in Input:**
- 🔵 3 LangGraph spans (1 root + 2 nested)
- ⚠️ 1 agent node
- 🔧 6 function calls (processes_invoke, route_agent, A_Plus_B nodes)
- 🤖 1 LLM span (UiPathChat)
- 🛠️ 12 tool spans (GET, POST, A_Plus_B tools)

---

## Output Structure (15 Spans)

```
Agent run - Agent (synthetic, running)              [Status: 0, EndTime: null]
├── GET                                             [96ms]   ← TOOL (reparented)
├── POST                                            [4.22s]  ← TOOL (reparented)
├── POST                                            [411ms]  ← TOOL (reparented)
├── GET                                             [187ms]  ← TOOL (reparented)
├── GET                                             [80ms]   ← TOOL (reparented)
├── POST                                            [154ms]  ← TOOL (reparented)
├── POST                                            [308ms]  ← TOOL (reparented)
├── GET                                             [196ms]  ← TOOL (reparented)
├── A_Plus_B (tool)                                [1ms]    ← TOOL (reparented)
├── UiPathChat (gpt-4.1-2025-04-14)               [1.23s]  ← LLM (reparented)
├── A_Plus_B (tool)                                [2ms]    ← TOOL (reparented)
├── GET                                             [80ms]   ← TOOL (reparented)
├── POST                                            [1.23s]  ← TOOL (reparented)
└── Agent run - Agent (synthetic, completed)        [Status: 1, EndTime: 2025-01-19T14:30:10.000Z]
```

**Span Types in Output:**
- ✨ 2 synthetic parent spans (running + completed states)
- 🤖 1 LLM span (preserved, reparented)
- 🛠️ 12 tool spans (preserved, reparented)

---

## What Happened?

### ❌ Buffered (Not Emitted)

These spans are **removed** from the output:

1. **3 LangGraph spans** → Replaced by 1 synthetic "Agent run - Agent" parent
2. **1 agent node** → Buffered (not emitted)
3. **6 function calls** → Buffered (processes_invoke, route_agent, A_Plus_B nodes)

**Total buffered:** 10 spans

### ✅ Passed Through (Emitted)

These spans are **preserved** and reparented to synthetic parent:

1. **1 LLM span** → UiPathChat (gpt-4.1-2025-04-14)
2. **12 tool spans** → All GET, POST, and A_Plus_B tool calls

**Total preserved:** 13 spans

### ✨ Created (Synthetic)

1. **Agent run - Agent (running)** → Status=0, EndTime=null
2. **Agent run - Agent (completed)** → Status=1, EndTime=set

**Total created:** 2 spans (but same ID, emitted twice for progressive state)

---

## Key Transformations

### 1. LangGraph Parents → Synthetic Parent

**Before:**
```json
{
  "name": "LangGraph",
  "id": "span-langgraph-001",
  "parent_id": null,
  "status": 1,
  "attributes": {
    "openinference.span.kind": "CHAIN"
  }
}
```

**After (Running State):**
```json
{
  "name": "Agent run - Agent",
  "id": "synthetic-abc-123",
  "parent_id": null,
  "status": 0,
  "end_time": null,
  "attributes": {
    "openinference.span.kind": "CHAIN",
    "langgraph.simplified": true
  }
}
```

**After (Completed State):**
```json
{
  "name": "Agent run - Agent",
  "id": "synthetic-abc-123",
  "parent_id": null,
  "status": 1,
  "end_time": "2025-01-19T14:30:10.000Z",
  "attributes": {
    "openinference.span.kind": "CHAIN",
    "langgraph.simplified": true
  }
}
```

### 2. LLM Span Reparenting

**Before:**
```json
{
  "id": "span-uipath-chat-001",
  "name": "UiPathChat",
  "parent_id": "span-agent-001",  ← Child of agent node
  "attributes": {
    "llm.model_name": "gpt-4.1-2025-04-14",
    "openinference.span.kind": "LLM"
  }
}
```

**After:**
```json
{
  "id": "span-uipath-chat-001",
  "name": "UiPathChat",
  "parent_id": "synthetic-abc-123",  ← Reparented to synthetic
  "attributes": {
    "llm.model_name": "gpt-4.1-2025-04-14",
    "openinference.span.kind": "LLM"
  }
}
```

### 3. Tool Span Reparenting

**Before:**
```json
{
  "id": "span-get-001",
  "name": "GET",
  "parent_id": "span-langgraph-001",  ← Child of LangGraph
  "attributes": {
    "http.method": "GET",
    "openinference.span.kind": "TOOL"
  }
}
```

**After:**
```json
{
  "id": "span-get-001",
  "name": "GET",
  "parent_id": "synthetic-abc-123",  ← Reparented to synthetic
  "attributes": {
    "http.method": "GET",
    "openinference.span.kind": "TOOL"
  }
}
```

---

## Benefits

### 1. Reduced Noise (34.8% fewer spans)
- Eliminated 3 nested LangGraph spans
- Removed 1 agent node span
- Removed 6 internal function call spans

### 2. Preserved Critical Data (100%)
- All LLM spans intact (model calls, timings)
- All tool spans intact (API calls, executions)

### 3. Simplified Hierarchy
- Single synthetic parent instead of nested LangGraph hierarchy
- Flat structure: parent → LLM/tool children
- Easy to visualize in UI

### 4. Progressive State Tracking
- Running state shows execution in progress
- Completed state shows final result
- UI can update smoothly as execution proceeds

---

## Files Generated

1. **`transformation_input.json`** - Original 23 spans from Image #1
2. **`transformation_output.json`** - Simplified 15 spans
3. **`transformation_visualization.json`** - Statistics and metrics
4. **`TRANSFORMATION_COMPARISON.md`** - This document

---

## Next Steps

This prototype validates the transformation works correctly. Next phase will:
1. Integrate with OpenTelemetry SpanProcessor
2. Handle real-time span processing
3. Export to OTLP backend
4. Test with live LangGraph executions
