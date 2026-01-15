# Proposal: Interruptible Process Trace Context Preservation

## Problem Statement

When a Python agent suspends via LangGraph's `interrupt()`, two issues occur:

1. **Checkpoint-based execution**: LangGraph uses checkpoints with `thread_id` as cursor. On resume, execution restarts from the beginning of the interrupted node - creating a new trace context.

2. **Process boundary**: Python agent process exits on suspend. On resume, a new process starts with no memory of original trace.

**Result**: LLMOps shows two separate traces with no link between them.

**Goal**: Match C# Agents behavior - suspended spans show as RUNNING, resumed execution links to original trace.

**Reference**: [LangGraph Interrupts Documentation](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/wait-user-input/)

---

## How Does C# Do It?

### Two Upsert Methods

From `Agents/backend/Execution.Shared/Traces/TraceSpan.cs`:

```csharp
// 1. Workflow context - uses Temporal Activity as async boundary
public async Task UpsertWorkflowAsync()
{
    Id = await Workflow.ExecuteActivityAsync(
        (TraceExecutor x) => x.UpsertSpanAsync(payload), options);
}

// 2. Non-workflow context - direct async call
public async Task UpsertAsync(ITraceCreationService service)
{
    Id = await service.UpsertSpanAsync(...);
}
```

### Upsert Decision Matrix

From `ConversationalEngineWorkflow.cs`:

| When | Await? | Why |
|------|--------|-----|
| Before LLM call | Fire-and-forget | Real-time visibility, don't block |
| After success (normal) | Fire-and-forget | Non-critical, performance matters |
| After success (eval) | Await | Evaluators need span data |
| On error | Await | Must record before throwing |
| On suspend | Await | Critical checkpoint, process exiting |

### Status Values

From `llm-observability/StatusEnum.cs`:

| Status | Value | Used For |
|--------|-------|----------|
| Unset | 0 | Default |
| Ok | 1 | Success |
| Error | 2 | Failure |
| **Running** | **3** | **Suspended/waiting** |
| Restricted | 4 | - |
| Cancelled | 5 | - |

**Note**: No dedicated INTERRUPTED status. C# uses `Running` for suspended spans.

### C# Escalation Tool Pattern

From `EscalationToolWorkflow.cs` - the tool span CONTINUES after resume (same span, multiple upserts):

```csharp
var span = SpanInit(payload);
await span.UpsertWorkflowAsync();           // 1. Initial (Running)

// ... create escalation task ...
span.Attributes.TaskId = result.TaskId;
await span.UpsertWorkflowAsync();           // 2. With task details

await Workflow.WaitConditionAsync(...);     // SUSPEND HERE

// ... after resume ...
span.Attributes.Result = outcome.Result;
span.Status = TraceStatus.Ok;
await span.UpsertWorkflowAsync();           // 3. Final (Ok)
```

**Key insight**: Same span object is upserted 3 times. Temporal preserves span in memory across suspend/resume.

---

## Can We Follow Same as C#?

### Differences

| Aspect | C# Agents | Python Agents |
|--------|-----------|---------------|
| Orchestration | Temporal Workflows | LangGraph |
| Async boundary | Temporal Activities | Python async/await |
| Suspend mechanism | `Workflow.WaitConditionAsync` | `GraphInterrupt` |
| Resume trigger | Temporal signal | CLI `--resume` flag |
| State persistence | Temporal (in-memory across suspend) | SQLite (across process restart) |
| Span object | Preserved in memory | Lost on process exit |

### What We Can Replicate

| C# Feature | Python Equivalent |
|------------|-------------------|
| `await span.UpsertWorkflowAsync()` | `exporter.upsert_span()` (sync, blocking) |
| `Running` status for suspend | Same - use `SpanStatus.RUNNING = 3` |
| Trace context preservation | SQLite storage for span data |

**SQLite storage needs more than IDs**: Since upsert overwrites, we must store full span data (TraceId, SpanId, ParentId, Name, StartTime, Attributes) to continue the span on resume. See `llm-observability/Span.cs` for required fields.

### What We Cannot Replicate

- **Temporal's durable execution**: Temporal automatically replays workflow from checkpoint on failure. Python has no equivalent - if process dies mid-execution, state is lost unless explicitly persisted.

- **True fire-and-forget**: Temporal Activity Workers run in separate thread pool, so `_ = UpsertWorkflowAsync()` doesn't block workflow. In Python, we'd need explicit queue+thread (like OTel's [BatchSpanProcessor](https://github.com/open-telemetry/opentelemetry-python/blob/main/opentelemetry-sdk/src/opentelemetry/sdk/trace/export/__init__.py)).

---

## Should We Do That?

**Yes**, with simplifications:

1. **Use sync `upsert_span()`** - Process is exiting anyway on suspend, blocking 50-200ms is acceptable. Existing sync method works fine - no need for async version.

2. **SQLite for trace context** - Already used for resume triggers. Store full span data for continuation.

3. **Skip queue+thread for now** - Not needed for suspend-only. If we need real-time updates from sync callbacks later, we can follow OTel's BatchSpanProcessor pattern.

---

## Example: Escalation Tool

### Before (Current Behavior)

```
Agent Run #1 (trace_id: abc-123)
├── LLM Call (decides to escalate)
├── Tool: escalation_tool
│   └── raises GraphInterrupt
└── [Agent span ends - status unknown]
    [Tool span ends - status unknown]

--- Process exits, LangGraph checkpoint saved ---

Agent Run #2 (trace_id: xyz-789)  ← NEW TRACE
├── [Resumes from node start per LangGraph behavior]
├── LLM Call
└── Agent completes
```

**LLMOps shows**: Two separate traces, no link between them.

### After (Expected Behavior)

**Continue same spans (like C#)**

```
Agent Run (trace_id: abc-123)
├── LLM Call
├── Tool: escalation_tool
│   ├── [Upsert: RUNNING status, saved to SQLite]
│   │
│   │   --- Process exits ---
│   │
│   ├── [Resume: Load from SQLite, upsert continuation]
│   └── [Upsert: OK status with result]
└── Agent completes [OK status]
```



---

## Changes Needed

### uipath-python

| Change | Description |
|--------|-------------|
| None | Existing sync `upsert_span()` works |
| (Future) Add async version | If we need non-blocking upserts |

### uipath-langchain-python

**Storage approach**: [PR #372](https://github.com/UiPath/uipath-langchain-python/pull/372) already adds generic key-value storage:

| Already Available | Description |
|-------------------|-------------|
| `set_value(runtime_id, namespace, key, value)` | Generic key-value persist |
| `get_value(runtime_id, namespace, key)` | Generic key-value retrieve |
| `__uipath_runtime_kv` table | Schema: `(runtime_id, namespace, key, value, timestamp)` |

**Our trace context storage**:
```python
# Usage
storage.set_value(
    runtime_id="agent-123",
    namespace="trace_context",
    key="agent_span",
    value={
        "trace_id": "abc-123-...",
        "span_id": "def-456-...",
        "parent_span_id": None,
        "name": "agent.json",
        "start_time": "2024-01-15T10:30:00Z",
        "attributes": {
            "agentId": "agent-123",
            "systemPrompt": "...",
            "userPrompt": "..."
        }
    }
)
```

| Change Needed | Description |
|---------------|-------------|
| None in uipath-langchain-python | Use existing `set_value`/`get_value` with namespace=`trace_context` |

### uipath-agents-python

**Piggyback opportunity**: Runtime wrapping order is `UiPathResumableRuntime` → `TelemetryRuntimeWrapper` → `AgentsLangGraphRuntime`. The span is still open when result returns to TelemetryRuntimeWrapper (before `finally` cleanup). We can detect SUSPENDED there.

| Change | Description |
|--------|-------------|
| Modify `TelemetryRuntimeWrapper.execute()` | Check `result.status == SUSPENDED` before span closes |
| Upsert agent span with RUNNING | Call `upsert_span()` with current span data |
| Save trace context to SQLite | Via storage (passed from factory) |
| Restore trace context on resume | Load from SQLite, restore span as parent |


---

**Error during resume**: Use try/catch pattern like C#:
   ```python
   try:
       result = await delegate.execute(...)
   except Exception as ex:
       # Upsert span with ERROR status before re-raising
       upsert_span(agent_span, status=SpanStatus.ERROR, error=str(ex))
       raise
   ```
   From `EscalationToolWorkflow.cs:123-126`: `span.SetError(ex, Workflow.UtcNow)` then `await span.UpsertWorkflowAsync()`

## Open Questions

1. **Multiple suspensions**: If agent suspends multiple times, do we overwrite trace context or keep history?

2. **Cleanup**: When should we delete trace context from SQLite? After successful completion?


