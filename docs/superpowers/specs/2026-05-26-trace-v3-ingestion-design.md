# Trace V3 Ingestion Migration Design

**Date:** 2026-05-26  
**Branch:** feat/trace-v3-migration  
**Scope:** Ingest only (`POST /api/Traces/v3/spans`). Read-side migration is independent and deferred.

---

## Context

The UiPath LLM Observability backend is introducing V3 span APIs with insert-only (immutable) ingestion semantics. Duplicate records for the same span are merged on read using a fixed precedence rule: terminal status wins, then latest `UpdatedAt`. This eliminates write contention from the old mutable upsert model.

V3 ingest enforces two breaking changes vs V2:
1. **Enum fields must be strings** — `"Ok"` not `1`. Affects: `Status`, `Source`, `VerbosityLevel`, `ExecutionType`.
2. **TraceId/SpanId must be OTEL hex** — 32-char and 16-char respectively. The SDK already produces OTEL hex IDs, so no change needed here.

The Confluence migration guide confirms ingest and read can be migrated independently. V2 read endpoints (`GET /v2/spans`, `GET /v2/spans/otel`) already handle V3-written spans correctly at the storage layer.

---

## What's Not Changing

- ID format: SDK already emits 32-char hex traceIds and 16-char hex spanIds. No change.
- Live tracking: `LiveTrackingSpanProcessor` sends `RUNNING` on span start and `OK`/`ERROR` on span end. With V3 insert-only, each call creates a new record; the server merges on read (terminal status wins). Wire behavior is unchanged.
- Batch strategy: continue grouping spans by `traceId` and posting to the single-trace endpoint. The `/v3/spans/batch` endpoint is not used.
- `AttachmentProvider` / `AttachmentDirection`: server uses flexible enum converters for attachments — integers remain valid. No change.

---

## Architecture

### New Enum Types (`uipath-platform`)

**File:** `packages/uipath-platform/src/uipath/platform/common/_span_utils.py`

Replace `IntEnum`-based types with `StrEnum` (Python 3.11+). Values match C# enum names exactly so they serialize correctly without any custom JSON logic.

```python
class SpanStatus(StrEnum):
    UNSET      = "Unset"
    OK         = "Ok"
    ERROR      = "Error"
    RUNNING    = "Running"
    RESTRICTED = "Restricted"
    CANCELLED  = "Cancelled"

class SpanSource(StrEnum):
    CODED_AGENTS           = "CodedAgents"
    AGENTS                 = "Agents"
    PROCESS_ORCHESTRATION  = "ProcessOrchestration"
    API_WORKFLOWS          = "ApiWorkflows"
    ROBOTS                 = "Robots"
    # extend as needed from server SourceEnum

class VerbosityLevel(StrEnum):   # replaces VerbosityLevel(IntEnum)
    VERBOSE     = "Verbose"
    TRACE       = "Trace"
    INFORMATION = "Information"
    WARNING     = "Warning"
    ERROR       = "Error"
    CRITICAL    = "Critical"
    OFF         = "Off"

class ExecutionType(StrEnum):
    DEBUG   = "Debug"
    RUNTIME = "Runtime"
```

`DEFAULT_SOURCE = 10` constant is removed; `SpanSource.CODED_AGENTS` replaces all usages.

### `UiPathSpan` Dataclass

Field types change from `int`/`Optional[int]` to the new enums. `to_dict()` requires no changes — `StrEnum` values are plain strings and serialize correctly when placed in a dict.

```python
@dataclass
class UiPathSpan:
    # changed fields:
    status: SpanStatus = SpanStatus.OK
    source: SpanSource = SpanSource.CODED_AGENTS
    execution_type: Optional[ExecutionType] = None
    verbosity_level: Optional[VerbosityLevel] = None
    # all other fields unchanged
```

`otel_span_to_uipath_span()` replaces integer literals (`status = 1`, `status = 2`) with `SpanStatus.OK` and `SpanStatus.ERROR`. The `uipath.source` attribute override path changes from `isinstance(uipath_source, int)` to accepting a `str` that maps to a `SpanSource` member.

### `LlmOpsHttpExporter` (`uipath` package)

**File:** `packages/uipath/src/uipath/tracing/_otel_exporters.py`

Changes:
- Remove the `SpanStatus` integer class entirely.
- Import `SpanStatus` from `uipath.platform.common._span_utils`.
- `_build_url()`: `api/Traces/spans` → `api/Traces/v3/spans`.
- `upsert_span(status_override: Optional[SpanStatus] = None)` — type tightens from `Optional[int]`.
- `_determine_status()` return type changes from `int` to `SpanStatus`.
- Inner `Status` class (used for `INTERRUPTED`, `ERROR`, `SUCCESS`) is removed; map `INTERRUPTED` → `SpanStatus.CANCELLED`, `ERROR` → `SpanStatus.ERROR`, `SUCCESS` → `SpanStatus.OK`.

### `LiveTrackingSpanProcessor`

**File:** `packages/uipath/src/uipath/tracing/_live_tracking_processor.py`

Update import: `SpanStatus` comes from `uipath.platform.common._span_utils` instead of `_otel_exporters`. Usage (`SpanStatus.RUNNING`) is unchanged.

---

## Data Flow

```
OTel span (StatusCode.OK / ERROR)
        │
        ▼
otel_span_to_uipath_span()
  status = SpanStatus.OK / SpanStatus.ERROR   ← was int 1/2
  source = SpanSource.CODED_AGENTS            ← was int 10
  verbosity_level = VerbosityLevel.INFORMATION ← was int 2
        │
        ▼
UiPathSpan.to_dict()
  {"Status": "Ok", "Source": "CodedAgents", ...}  ← strings, not ints
        │
        ▼
POST {base_url}/api/Traces/v3/spans?traceId=...&source=CodedAgents
  (was /api/Traces/spans)
```

---

## Files Changed

| File | Change |
|------|--------|
| `packages/uipath-platform/src/uipath/platform/common/_span_utils.py` | Replace `IntEnum` types; add `SpanStatus`, `SpanSource`, `ExecutionType` as `StrEnum`; update `UiPathSpan` field types; update `otel_span_to_uipath_span()` |
| `packages/uipath/src/uipath/tracing/_otel_exporters.py` | Remove `SpanStatus` int class; import from `_span_utils`; update `_build_url()`, `upsert_span()`, `_determine_status()` |
| `packages/uipath/src/uipath/tracing/_live_tracking_processor.py` | Update `SpanStatus` import |
| `packages/uipath/tests/tracing/test_otel_exporters.py` | Update status/source/verbosity assertions from ints to strings; update URL assertions to `v3/spans` |

---

## Error Handling

No new error handling needed. The V3 endpoint returns `400` for malformed IDs or integer enums — these are programming errors (wrong enum values sent), not runtime conditions. Existing retry logic (4 attempts, exponential backoff) handles transient `5xx` responses unchanged.

---

## Testing

- Existing unit tests in `test_otel_exporters.py` updated to assert string enum values and `v3/spans` URL.
- No new test scenarios needed: the V3 format change is purely serialization; logic paths are the same.
- Live tracking test (`upsert_span` with `RUNNING`) updated to assert `"Status": "Running"`.
