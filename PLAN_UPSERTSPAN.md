# Implementation Plan: UpsertSpan Method for LLM Export Flow

## Overview

Add an `upsert_span` method to the LLM Export flow that allows upserting (insert or update) individual spans to the UiPath LLM Ops backend. This method will be designed to be easily consumable by the `uipath-agents-python` repository.

## API Endpoint Analysis

Based on the existing codebase:
- **Current batch export**: `POST /llmopstenant_/api/Traces/spans?traceId={trace_id}&source=Robots`
- **Proposed upsert endpoint**: `PUT /llmopstenant_/api/Traces/upsertSpan` (single span upsert)

The upsert operation semantically means: "Create if not exists, update if exists" - which aligns with PUT semantics.

## Implementation Details

### 1. Add `upsert_span` Method to `LlmOpsHttpExporter`

**Location**: `src/uipath/tracing/_otel_exporters.py`

```python
def upsert_span(
    self,
    span: ReadableSpan | UiPathSpan | Dict[str, Any],
    trace_id: Optional[str] = None,
) -> bool:
    """Upsert a single span to UiPath LLM Ops.

    This method creates a new span if it doesn't exist, or updates it if it does.
    Designed for use by external consumers like uipath-agents-python.

    Args:
        span: The span to upsert. Can be:
            - OpenTelemetry ReadableSpan
            - UiPathSpan dataclass
            - Dictionary with span data (must have Id and TraceId)
        trace_id: Optional trace ID override. If not provided, uses the span's trace ID
                  or falls back to UIPATH_TRACE_ID environment variable.

    Returns:
        True if the upsert was successful, False otherwise.
    """
```

### 2. Add Async Variant `upsert_span_async`

For async contexts (common in agent frameworks):

```python
async def upsert_span_async(
    self,
    span: ReadableSpan | UiPathSpan | Dict[str, Any],
    trace_id: Optional[str] = None,
) -> bool:
    """Async version of upsert_span for use in async contexts."""
```

### 3. Request Payload Format

Based on the existing `UiPathSpan.to_dict()` format, the upsert request will use:

```json
{
  "Id": "uuid4-string",
  "TraceId": "uuid4-string",
  "ParentId": "uuid4-string | null",
  "Name": "span-name",
  "StartTime": "ISO8601-timestamp",
  "EndTime": "ISO8601-timestamp",
  "Attributes": "json-string",
  "Status": 1,
  "CreatedAt": "ISO8601-timestamp",
  "UpdatedAt": "ISO8601-timestamp",
  "OrganizationId": "string",
  "TenantId": "string",
  "FolderKey": "string",
  "SpanType": "string",
  "ProcessKey": "string",
  "JobKey": "string",
  "ReferenceId": "string"
}
```

### 4. Input Flexibility

The method will accept multiple input types for maximum flexibility:

1. **OpenTelemetry ReadableSpan**: Converted via `_SpanUtils.otel_span_to_uipath_span()`
2. **UiPathSpan dataclass**: Converted via `to_dict()`
3. **Dict[str, Any]**: Used directly (validated for required fields)

### 5. Export from `__init__.py`

Update `src/uipath/tracing/__init__.py` to expose the method:

```python
from ._otel_exporters import (
    JsonLinesFileExporter,
    LlmOpsHttpExporter,
)
from ._utils import UiPathSpan  # Also export UiPathSpan for external use

__all__ = [
    "traced",
    "LlmOpsHttpExporter",
    "JsonLinesFileExporter",
    "UiPathSpan",
]
```

## Usage Examples

### Example 1: Basic Usage with Dictionary
```python
from uipath.tracing import LlmOpsHttpExporter

exporter = LlmOpsHttpExporter()
success = exporter.upsert_span({
    "Id": "550e8400-e29b-41d4-a716-446655440000",
    "TraceId": "550e8400-e29b-41d4-a716-446655440001",
    "Name": "my_operation",
    "Attributes": '{"key": "value"}',
    "Status": 1,
    "StartTime": "2024-01-01T00:00:00Z",
    "EndTime": "2024-01-01T00:00:01Z",
})
```

### Example 2: Using UiPathSpan
```python
from uipath.tracing import LlmOpsHttpExporter, UiPathSpan
import uuid

exporter = LlmOpsHttpExporter()
span = UiPathSpan(
    id=uuid.uuid4(),
    trace_id=uuid.uuid4(),
    name="agent_step",
    attributes={"step": "reasoning"},
)
success = exporter.upsert_span(span)
```

### Example 3: Async Usage
```python
from uipath.tracing import LlmOpsHttpExporter

async def track_agent_step():
    exporter = LlmOpsHttpExporter()
    success = await exporter.upsert_span_async({
        "Id": "...",
        "TraceId": "...",
        "Name": "agent_step",
        # ...
    })
```

### Example 4: From uipath-agents-python
```python
# In uipath-agents-python repo
from uipath.tracing import LlmOpsHttpExporter, UiPathSpan

class AgentTracer:
    def __init__(self):
        self.exporter = LlmOpsHttpExporter()

    async def record_step(self, step_name: str, attributes: dict):
        span = UiPathSpan(
            id=uuid.uuid4(),
            trace_id=self.current_trace_id,
            parent_id=self.current_span_id,
            name=step_name,
            attributes=attributes,
        )
        await self.exporter.upsert_span_async(span)
```

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/uipath/tracing/_otel_exporters.py` | Modify | Add `upsert_span()` and `upsert_span_async()` methods |
| `src/uipath/tracing/__init__.py` | Modify | Export `UiPathSpan` |
| `tests/tracing/test_otel_exporters.py` | Modify | Add tests for new methods |

## API Endpoint Details (Inferred)

Since the LLM-observability repo is not publicly accessible, the endpoint is inferred based on:
- Existing pattern: `/llmopstenant_/api/Traces/spans` for batch
- RESTful convention: `/llmopstenant_/api/Traces/upsertSpan` for upsert

The endpoint will:
- Accept PUT request with single span payload
- Return 200 on success (create or update)
- Use same authentication (Bearer token from `UIPATH_ACCESS_TOKEN`)

## Error Handling

The method will:
1. Validate required fields (Id, TraceId, Name)
2. Use retry logic (same as `_send_with_retries`)
3. Log warnings on failure
4. Return boolean success status (not raise exceptions for network errors)

## Dependencies

No new dependencies required. Uses existing:
- `httpx` for HTTP client
- `uuid` for ID generation
- `json` for serialization
