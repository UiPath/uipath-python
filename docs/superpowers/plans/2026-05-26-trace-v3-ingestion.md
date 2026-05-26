# Trace V3 Ingestion Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate span ingest from the v2 endpoint (integer enums, `/api/Traces/spans`) to the v3 endpoint (string enums, `/api/Traces/v3/spans`).

**Architecture:** Replace scattered integer constants and `IntEnum` types with `StrEnum` classes whose values match the C# server enum names exactly. `UiPathSpan.to_dict()` then serializes correctly without any custom JSON logic. The URL change is a one-liner in `_build_url()`.

**Tech Stack:** Python 3.11+ `StrEnum`, `pytest`, `pytest-httpx`, `opentelemetry-sdk`

---

## File Map

| File | Change |
|------|--------|
| `packages/uipath-platform/src/uipath/platform/common/_span_utils.py` | Add `SpanStatus`, `SpanSource`, `ExecutionType` StrEnums; change `VerbosityLevel` IntEnum→StrEnum; add int→enum mapping dicts; update `UiPathSpan` field types; update `otel_span_to_uipath_span()` |
| `packages/uipath-platform/src/uipath/platform/common/__init__.py` | Export `SpanStatus`, `SpanSource`, `ExecutionType`, `VerbosityLevel` |
| `packages/uipath/src/uipath/tracing/_otel_exporters.py` | Remove `SpanStatus` int class and inner `Status` class; import `SpanStatus` from `_span_utils`; update `_build_url()`, `_determine_status()`, `upsert_span()` |
| `packages/uipath/src/uipath/tracing/_live_tracking_processor.py` | Update `SpanStatus` import; tighten `status_override` type annotation |
| `packages/uipath/src/uipath/tracing/__init__.py` | Re-export `SpanStatus` from new location |
| `packages/uipath-platform/tests/services/test_span_utils.py` | Update integer enum assertions to string values |
| `packages/uipath/tests/tracing/test_otel_exporters.py` | Update `SpanStatus` import; update URL, status, source assertions to strings |

---

## Task 1: Add StrEnum types to `_span_utils.py`

**Files:**
- Modify: `packages/uipath-platform/src/uipath/platform/common/_span_utils.py:7-39`
- Test: `packages/uipath-platform/tests/services/test_span_utils.py`

- [ ] **Step 1: Write the failing tests**

Add to `packages/uipath-platform/tests/services/test_span_utils.py` after the existing imports:

```python
from uipath.platform.common._span_utils import (
    ExecutionType,
    SpanSource,
    SpanStatus,
    VerbosityLevel,
)


class TestStrEnums:
    def test_span_status_string_values(self):
        assert SpanStatus.UNSET == "Unset"
        assert SpanStatus.OK == "Ok"
        assert SpanStatus.ERROR == "Error"
        assert SpanStatus.RUNNING == "Running"
        assert SpanStatus.RESTRICTED == "Restricted"
        assert SpanStatus.CANCELLED == "Cancelled"

    def test_span_source_string_values(self):
        assert SpanSource.CODED_AGENTS == "CodedAgents"
        assert SpanSource.AGENTS == "Agents"
        assert SpanSource.PROCESS_ORCHESTRATION == "ProcessOrchestration"
        assert SpanSource.API_WORKFLOWS == "ApiWorkflows"
        assert SpanSource.ROBOTS == "Robots"

    def test_verbosity_level_string_values(self):
        assert VerbosityLevel.VERBOSE == "Verbose"
        assert VerbosityLevel.TRACE == "Trace"
        assert VerbosityLevel.INFORMATION == "Information"
        assert VerbosityLevel.WARNING == "Warning"
        assert VerbosityLevel.ERROR == "Error"
        assert VerbosityLevel.CRITICAL == "Critical"
        assert VerbosityLevel.OFF == "Off"

    def test_execution_type_string_values(self):
        assert ExecutionType.DEBUG == "Debug"
        assert ExecutionType.RUNTIME == "Runtime"

    def test_enums_are_strings(self):
        assert isinstance(SpanStatus.OK, str)
        assert isinstance(SpanSource.CODED_AGENTS, str)
        assert isinstance(VerbosityLevel.INFORMATION, str)
        assert isinstance(ExecutionType.RUNTIME, str)
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd packages/uipath-platform && pytest tests/services/test_span_utils.py::TestStrEnums -v
```
Expected: `ImportError` — `SpanStatus`, `SpanSource`, `ExecutionType` not defined yet; `VerbosityLevel` is still `IntEnum`.

- [ ] **Step 3: Replace enum definitions in `_span_utils.py`**

In `packages/uipath-platform/src/uipath/platform/common/_span_utils.py`, make these changes:

Replace line 7:
```python
from enum import IntEnum
```
with:
```python
from enum import IntEnum
from enum import StrEnum
```

Replace lines 18-39 (the `DEFAULT_SOURCE` constant and the three IntEnum classes):
```python
# SourceEnum.CodedAgents = 10 (default for Python SDK / coded agents)
DEFAULT_SOURCE = 10


class AttachmentProvider(IntEnum):
    ORCHESTRATOR = 0


class AttachmentDirection(IntEnum):
    NONE = 0
    IN = 1
    OUT = 2


class VerbosityLevel(IntEnum):
    VERBOSE = 0
    TRACE = 1
    INFORMATION = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    OFF = 6
```
with:
```python
class SpanStatus(StrEnum):
    UNSET = "Unset"
    OK = "Ok"
    ERROR = "Error"
    RUNNING = "Running"
    RESTRICTED = "Restricted"
    CANCELLED = "Cancelled"


class SpanSource(StrEnum):
    AGENTS = "Agents"
    PROCESS_ORCHESTRATION = "ProcessOrchestration"
    API_WORKFLOWS = "ApiWorkflows"
    ROBOTS = "Robots"
    CODED_AGENTS = "CodedAgents"


class VerbosityLevel(StrEnum):
    VERBOSE = "Verbose"
    TRACE = "Trace"
    INFORMATION = "Information"
    WARNING = "Warning"
    ERROR = "Error"
    CRITICAL = "Critical"
    OFF = "Off"


class ExecutionType(StrEnum):
    DEBUG = "Debug"
    RUNTIME = "Runtime"


# Int→StrEnum lookup tables for converting raw OTEL attribute integers
_EXECUTION_TYPE_BY_INT: dict[int, ExecutionType] = {
    0: ExecutionType.DEBUG,
    1: ExecutionType.RUNTIME,
}

_VERBOSITY_LEVEL_BY_INT: dict[int, VerbosityLevel] = {
    0: VerbosityLevel.VERBOSE,
    1: VerbosityLevel.TRACE,
    2: VerbosityLevel.INFORMATION,
    3: VerbosityLevel.WARNING,
    4: VerbosityLevel.ERROR,
    5: VerbosityLevel.CRITICAL,
    6: VerbosityLevel.OFF,
}

_SOURCE_BY_INT: dict[int, SpanSource] = {
    1: SpanSource.AGENTS,
    2: SpanSource.PROCESS_ORCHESTRATION,
    3: SpanSource.API_WORKFLOWS,
    4: SpanSource.ROBOTS,
    10: SpanSource.CODED_AGENTS,
}


class AttachmentProvider(IntEnum):
    ORCHESTRATOR = 0


class AttachmentDirection(IntEnum):
    NONE = 0
    IN = 1
    OUT = 2
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/uipath-platform && pytest tests/services/test_span_utils.py::TestStrEnums -v
```
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/uipath-platform/src/uipath/platform/common/_span_utils.py \
        packages/uipath-platform/tests/services/test_span_utils.py
git commit -m "feat(tracing): add SpanStatus, SpanSource, ExecutionType, VerbosityLevel StrEnums"
```

---

## Task 2: Update `UiPathSpan` dataclass and `otel_span_to_uipath_span()`

**Files:**
- Modify: `packages/uipath-platform/src/uipath/platform/common/_span_utils.py:58-360`
- Test: `packages/uipath-platform/tests/services/test_span_utils.py`

- [ ] **Step 1: Write the failing tests**

Add to `packages/uipath-platform/tests/services/test_span_utils.py`:

```python
class TestUiPathSpanDictUsesStrings:
    def test_default_status_is_ok_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
        )
        d = span.to_dict()
        assert d["Status"] == "Ok"

    def test_default_source_is_coded_agents_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
        )
        d = span.to_dict()
        assert d["Source"] == "CodedAgents"

    def test_verbosity_level_serializes_as_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
            verbosity_level=VerbosityLevel.OFF,
        )
        d = span.to_dict()
        assert d["VerbosityLevel"] == "Off"

    def test_execution_type_serializes_as_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
            execution_type=ExecutionType.RUNTIME,
        )
        d = span.to_dict()
        assert d["ExecutionType"] == "Runtime"


class TestOtelSpanConversionUsesStrEnums:
    def _make_mock_span(self, status_code=StatusCode.OK, attributes=None):
        from datetime import datetime
        from unittest.mock import Mock
        from opentelemetry.trace import SpanContext

        mock_span = Mock()
        mock_context = SpanContext(
            trace_id=0x123456789ABCDEF0123456789ABCDEF0,
            span_id=0x0123456789ABCDEF,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = status_code
        mock_span.status.description = None
        mock_span.attributes = attributes or {}
        mock_span.events = []
        mock_span.links = []
        now_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = now_ns
        mock_span.end_time = now_ns + 1_000_000
        return mock_span

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_ok_status_maps_to_str_enum(self):
        span = _SpanUtils.otel_span_to_uipath_span(self._make_mock_span())
        assert span.status == SpanStatus.OK
        assert span.to_dict()["Status"] == "Ok"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_error_status_maps_to_str_enum(self):
        mock_span = self._make_mock_span(status_code=StatusCode.ERROR)
        mock_span.status.description = "something went wrong"
        span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert span.status == SpanStatus.ERROR
        assert span.to_dict()["Status"] == "Error"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_default_source_is_coded_agents(self):
        span = _SpanUtils.otel_span_to_uipath_span(self._make_mock_span())
        assert span.source == SpanSource.CODED_AGENTS
        assert span.to_dict()["Source"] == "CodedAgents"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_execution_type_int_maps_to_str_enum(self):
        mock_span = self._make_mock_span(attributes={"executionType": 1})
        span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert span.execution_type == ExecutionType.RUNTIME
        assert span.to_dict()["ExecutionType"] == "Runtime"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_verbosity_level_int_maps_to_str_enum(self):
        mock_span = self._make_mock_span(attributes={"verbosityLevel": 6})
        span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert span.verbosity_level == VerbosityLevel.OFF
        assert span.to_dict()["VerbosityLevel"] == "Off"
```

Also update the existing `ATTRIBUTE_FIELD_MAP` in `TestOTelToUiPathSpan` — replace the `executionType` and `verbosityLevel` entries:

```python
ATTRIBUTE_FIELD_MAP = [
    ("executionType", "execution_type", "ExecutionType", ExecutionType.RUNTIME),  # was 1
    ("agentVersion", "agent_version", "AgentVersion", "1.2.3"),
    ("agentId", "reference_id", "ReferenceId", "ref-abc"),
    ("verbosityLevel", "verbosity_level", "VerbosityLevel", VerbosityLevel.OFF),  # was 6
]
```

And update the attribute values passed in `test_attributes_map_to_top_level_fields` — the mock attributes dict must pass integers that get converted (since OTEL attributes are ints). The test helper sets `attrs = {otel_attr: value for otel_attr, _, _, value in self.ATTRIBUTE_FIELD_MAP}` so it passes `{"executionType": ExecutionType.RUNTIME}`. But OTEL sends ints — update the map to pass the int that maps to each enum:

```python
ATTRIBUTE_FIELD_MAP = [
    # (otel_attr, span_field, top_level_key, otel_int_or_str, expected_enum_or_str)
    ("executionType", "execution_type", "ExecutionType", 1, ExecutionType.RUNTIME),
    ("agentVersion", "agent_version", "AgentVersion", "1.2.3", "1.2.3"),
    ("agentId", "reference_id", "ReferenceId", "ref-abc", "ref-abc"),
    ("verbosityLevel", "verbosity_level", "VerbosityLevel", 6, VerbosityLevel.OFF),
]
```

And update `test_attributes_map_to_top_level_fields` to use the new 5-tuple:

```python
@patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
def test_attributes_map_to_top_level_fields(self) -> None:
    attrs = {
        otel_attr: otel_val for otel_attr, _, _, otel_val, _ in self.ATTRIBUTE_FIELD_MAP
    }

    # ... (same mock setup) ...

    uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
    span_dict = uipath_span.to_dict()

    for _, span_field, top_level_key, _, expected in self.ATTRIBUTE_FIELD_MAP:
        assert getattr(uipath_span, span_field) == expected, span_field
        assert span_dict[top_level_key] == expected, top_level_key
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd packages/uipath-platform && pytest tests/services/test_span_utils.py -v 2>&1 | tail -20
```
Expected: Multiple failures — `UiPathSpan.status` defaults to `1` (int) not `"Ok"`, `executionType` and `verbosityLevel` still passed through as raw ints.

- [ ] **Step 3: Update `UiPathSpan` field types**

In `packages/uipath-platform/src/uipath/platform/common/_span_utils.py`, update the `UiPathSpan` dataclass. Search for each field by its current content:

Replace:
```python
    status: int = 1
```
with:
```python
    status: SpanStatus = SpanStatus.OK
```

Replace:
```python
    source: int = DEFAULT_SOURCE
```
with:
```python
    source: SpanSource = SpanSource.CODED_AGENTS
```

Replace:
```python
    execution_type: Optional[int] = None
```
with:
```python
    execution_type: Optional[ExecutionType] = None
```

Replace:
```python
    verbosity_level: Optional[int] = None
```
with:
```python
    verbosity_level: Optional[VerbosityLevel] = None
```

- [ ] **Step 4: Update `otel_span_to_uipath_span()` to use enum members**

In `_span_utils.py`, find the status mapping block (around line 230-234 after insertions):

Replace:
```python
        # Map status
        status = 1  # Default to OK
        if otel_span.status.status_code == StatusCode.ERROR:
            status = 2  # Error
            attributes_dict["error"] = otel_span.status.description
```
with:
```python
        # Map status
        status = SpanStatus.OK
        if otel_span.status.status_code == StatusCode.ERROR:
            status = SpanStatus.ERROR
            attributes_dict["error"] = otel_span.status.description
```

Find the source/execution_type/verbosity_level block (around line 297-309 after insertions):

Replace:
```python
        # Top-level fields for internal tracing schema
        execution_type = attributes_dict.get("executionType")
        agent_version = attributes_dict.get("agentVersion")
        reference_id = (
            env.get("UIPATH_AGENT_ID")
            or attributes_dict.get("agentId")
            or attributes_dict.get("referenceId")
        )
        verbosity_level = attributes_dict.get("verbosityLevel")

        # Source: override via uipath.source attribute, else DEFAULT_SOURCE
        uipath_source = attributes_dict.get("uipath.source")
        source = uipath_source if isinstance(uipath_source, int) else DEFAULT_SOURCE
```
with:
```python
        # Top-level fields for internal tracing schema
        execution_type_raw = attributes_dict.get("executionType")
        execution_type: Optional[ExecutionType] = (
            _EXECUTION_TYPE_BY_INT.get(execution_type_raw)
            if isinstance(execution_type_raw, int)
            else None
        )
        agent_version = attributes_dict.get("agentVersion")
        reference_id = (
            env.get("UIPATH_AGENT_ID")
            or attributes_dict.get("agentId")
            or attributes_dict.get("referenceId")
        )
        verbosity_level_raw = attributes_dict.get("verbosityLevel")
        verbosity_level: Optional[VerbosityLevel] = (
            _VERBOSITY_LEVEL_BY_INT.get(verbosity_level_raw)
            if isinstance(verbosity_level_raw, int)
            else None
        )

        # Source: override via uipath.source attribute, else CodedAgents
        uipath_source_raw = attributes_dict.get("uipath.source")
        source: SpanSource = (
            _SOURCE_BY_INT.get(uipath_source_raw, SpanSource.CODED_AGENTS)
            if isinstance(uipath_source_raw, int)
            else SpanSource.CODED_AGENTS
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd packages/uipath-platform && pytest tests/services/test_span_utils.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/uipath-platform/src/uipath/platform/common/_span_utils.py \
        packages/uipath-platform/tests/services/test_span_utils.py
git commit -m "feat(tracing): update UiPathSpan fields and otel conversion to use StrEnum types"
```

---

## Task 3: Export new enum types from `uipath.platform.common`

**Files:**
- Modify: `packages/uipath-platform/src/uipath/platform/common/__init__.py`

- [ ] **Step 1: Update the import line in `__init__.py`**

In `packages/uipath-platform/src/uipath/platform/common/__init__.py`, find:
```python
from ._span_utils import UiPathSpan, _SpanUtils
```
Replace with:
```python
from ._span_utils import (
    ExecutionType,
    SpanSource,
    SpanStatus,
    UiPathSpan,
    VerbosityLevel,
    _SpanUtils,
)
```

Then add the new names to `__all__`:
```python
    "ExecutionType",
    "SpanSource",
    "SpanStatus",
    "VerbosityLevel",
```

- [ ] **Step 2: Verify import works**

```bash
cd packages/uipath-platform && python -c "from uipath.platform.common import SpanStatus, SpanSource, ExecutionType, VerbosityLevel; print(SpanStatus.OK)"
```
Expected output: `Ok`

- [ ] **Step 3: Commit**

```bash
git add packages/uipath-platform/src/uipath/platform/common/__init__.py
git commit -m "feat(tracing): export SpanStatus, SpanSource, ExecutionType, VerbosityLevel from platform.common"
```

---

## Task 4: Update `LlmOpsHttpExporter` — remove int class, fix URL, fix types

**Files:**
- Modify: `packages/uipath/src/uipath/tracing/_otel_exporters.py`
- Test: `packages/uipath/tests/tracing/test_otel_exporters.py`

- [ ] **Step 1: Write the failing tests**

In `packages/uipath/tests/tracing/test_otel_exporters.py`, update the import at the top of the file:

```python
from uipath.platform.common._span_utils import SpanStatus  # new location
from uipath.tracing._otel_exporters import LlmOpsHttpExporter  # SpanStatus removed from here
```

Add these new test cases after the existing `test_send_with_retries_success` test:

```python
def test_build_url_uses_v3_endpoint(mock_env_vars):
    """_build_url must point to /api/Traces/v3/spans, not /api/Traces/spans."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
    span_list = [{"TraceId": "ab" * 16}]
    url = exporter._build_url(span_list)
    assert "/api/Traces/v3/spans" in url
    assert "/api/Traces/spans" not in url.replace("/v3/", "/")


def test_determine_status_ok_returns_string(mock_env_vars):
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
    assert exporter._determine_status(None) == "Ok"
    assert exporter._determine_status(None) == SpanStatus.OK


def test_determine_status_error_returns_string(mock_env_vars):
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
    assert exporter._determine_status("some error") == "Error"
    assert exporter._determine_status("some error") == SpanStatus.ERROR


def test_determine_status_graph_interrupt_returns_cancelled(mock_env_vars):
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
    assert exporter._determine_status("GraphInterrupt()") == "Cancelled"
    assert exporter._determine_status("GraphInterrupt()") == SpanStatus.CANCELLED
```

Also update the existing `exporter` fixture mock URL to use `v3/spans`:

```python
@pytest.fixture
def exporter(mock_env_vars):
    """Create an exporter instance for testing."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
        exporter._build_url = MagicMock(
            return_value="https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/v3/spans?traceId=test-trace-id&source=CodedAgents"
        )
        yield exporter
```

And update `test_export_success` to assert the v3 URL:
```python
        exporter.http_client.post.assert_called_once_with(
            "https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/v3/spans?traceId=test-trace-id&source=CodedAgents",
            json=[{"span": "data", "TraceId": "test-trace-id"}],
        )
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd packages/uipath && pytest tests/tracing/test_otel_exporters.py::test_build_url_uses_v3_endpoint tests/tracing/test_otel_exporters.py::test_determine_status_ok_returns_string tests/tracing/test_otel_exporters.py::test_determine_status_error_returns_string tests/tracing/test_otel_exporters.py::test_determine_status_graph_interrupt_returns_cancelled -v
```
Expected: `ImportError` (SpanStatus no longer in `_otel_exporters`) and assertion failures.

- [ ] **Step 3: Update `_otel_exporters.py`**

In `packages/uipath/src/uipath/tracing/_otel_exporters.py`:

Add to the imports block at the top:
```python
from uipath.platform.common._span_utils import SpanStatus
```

Delete the entire `SpanStatus` class (lines 27-35):
```python
class SpanStatus:
    """Span status values matching LLMOps StatusEnum."""

    UNSET = 0
    OK = 1
    ERROR = 2
    RUNNING = 3
    RESTRICTED = 4
    CANCELLED = 5
```

Delete the inner `Status` class inside `LlmOpsHttpExporter` (lines 109-112):
```python
    class Status:
        SUCCESS = 1
        ERROR = 2
        INTERRUPTED = 3
```

Update `_determine_status` return type and body:
```python
    def _determine_status(self, error: Optional[Any]) -> SpanStatus:
        if error:
            if isinstance(error, str) and error.startswith("GraphInterrupt("):
                return SpanStatus.CANCELLED
            return SpanStatus.ERROR
        return SpanStatus.OK
```

Update `_build_url`:
```python
    def _build_url(self, span_list: list[Dict[str, Any]]) -> str:
        """Construct the URL for the API request."""
        trace_id = str(span_list[0]["TraceId"])
        return f"{self.base_url}/api/Traces/v3/spans?traceId={trace_id}&source=CodedAgents"
```

Update `upsert_span` signature:
```python
    def upsert_span(
        self,
        span: ReadableSpan,
        status_override: Optional[SpanStatus] = None,
    ) -> SpanExportResult:
```

Also update the debug log message in `export()`:
```python
        logger.debug(
            f"Exporting {len(spans)} spans to {self.base_url}/api/Traces/v3/spans"
        )
```

- [ ] **Step 4: Run all exporter tests**

```bash
cd packages/uipath && pytest tests/tracing/test_otel_exporters.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/uipath/src/uipath/tracing/_otel_exporters.py \
        packages/uipath/tests/tracing/test_otel_exporters.py
git commit -m "feat(tracing): migrate LlmOpsHttpExporter to v3 ingest endpoint with string enums"
```

---

## Task 5: Update `LiveTrackingSpanProcessor` and `uipath.tracing` re-exports

**Files:**
- Modify: `packages/uipath/src/uipath/tracing/_live_tracking_processor.py`
- Modify: `packages/uipath/src/uipath/tracing/__init__.py`
- Test: `packages/uipath/tests/cli/eval/test_live_tracking_span_processor.py`

- [ ] **Step 1: Update `_live_tracking_processor.py`**

In `packages/uipath/src/uipath/tracing/_live_tracking_processor.py`, replace:
```python
from uipath.tracing._otel_exporters import LlmOpsHttpExporter, SpanStatus
```
with:
```python
from uipath.platform.common._span_utils import SpanStatus
from uipath.tracing._otel_exporters import LlmOpsHttpExporter
```

Update `_upsert_span_async` type annotation:
```python
    def _upsert_span_async(
        self, span: Span | ReadableSpan, status_override: SpanStatus | None = None
    ) -> None:
```

- [ ] **Step 2: Update `uipath.tracing.__init__.py` re-export**

In `packages/uipath/src/uipath/tracing/__init__.py`, `SpanStatus` is currently imported from `._otel_exporters`. Move it to the existing `_span_utils` import block.

Replace:
```python
from uipath.platform.common._span_utils import (
    AttachmentDirection,
    AttachmentProvider,
    SpanAttachment,
    VerbosityLevel,
)

from ._live_tracking_processor import LiveTrackingSpanProcessor
from ._otel_exporters import (  # noqa: D104
    JsonLinesFileExporter,
    LlmOpsHttpExporter,
    SpanStatus,
)
```
with:
```python
from uipath.platform.common._span_utils import (
    AttachmentDirection,
    AttachmentProvider,
    SpanAttachment,
    SpanStatus,
    VerbosityLevel,
)

from ._live_tracking_processor import LiveTrackingSpanProcessor
from ._otel_exporters import (  # noqa: D104
    JsonLinesFileExporter,
    LlmOpsHttpExporter,
)
```

`SpanStatus` stays in `__all__` — no change needed there.

- [ ] **Step 3: Run live tracking tests**

```bash
cd packages/uipath && pytest tests/cli/eval/test_live_tracking_span_processor.py -v
```
Expected: All tests PASS (they import `SpanStatus` from `uipath.tracing` which still re-exports it).

- [ ] **Step 4: Run full test suite for both packages**

```bash
cd packages/uipath-platform && pytest -x -q
cd packages/uipath && pytest -x -q
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/uipath/src/uipath/tracing/_live_tracking_processor.py \
        packages/uipath/src/uipath/tracing/__init__.py
git commit -m "feat(tracing): update LiveTrackingSpanProcessor to use SpanStatus from platform.common"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run linter and type checker**

```bash
cd packages/uipath-platform && ruff check . && ruff format --check . && mypy src tests
cd packages/uipath && ruff check . && ruff format --check . && mypy src tests
```
Expected: No errors. If ruff flags the unused `IntEnum` import after removing `VerbosityLevel(IntEnum)`, remove it.

- [ ] **Step 2: Verify enum values in full export path with an integration-style test**

Add this one-time verification test to `packages/uipath/tests/tracing/test_otel_exporters.py` (run it, then you can keep or delete it):

```python
def test_full_export_sends_string_enums_to_v3_url(mock_env_vars):
    """Integration-style: verify the full export pipeline sends string enums to v3 URL."""
    import json
    from unittest.mock import MagicMock, patch
    from opentelemetry.sdk.trace.export import SpanExportResult

    with patch("uipath.tracing._otel_exporters.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        exporter = LlmOpsHttpExporter()

        # Create a minimal real OTel span
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            readable_spans = []

        # Use mock span instead for simplicity
        mock_uipath_span_dict = {
            "TraceId": "ab" * 16,
            "Id": "cd" * 8,
            "Status": "Ok",
            "Source": "CodedAgents",
            "Attributes": "{}",
        }
        mock_uipath_span = MagicMock()
        mock_uipath_span.to_dict.return_value = mock_uipath_span_dict
        mock_readable = MagicMock()

        with patch("uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span", return_value=mock_uipath_span):
            result = exporter.export([mock_readable])

        assert result == SpanExportResult.SUCCESS
        call_args = mock_client.post.call_args
        url = call_args.args[0]
        payload = call_args.kwargs["json"]

        assert "/api/Traces/v3/spans" in url
        assert payload[0]["Status"] == "Ok"
        assert payload[0]["Source"] == "CodedAgents"
```

Run:
```bash
cd packages/uipath && pytest tests/tracing/test_otel_exporters.py::test_full_export_sends_string_enums_to_v3_url -v
```
Expected: PASS.

- [ ] **Step 3: Final commit**

```bash
git add -p  # stage any remaining changes
git commit -m "feat(tracing): complete v3 ingest migration — string enums, /api/Traces/v3/spans"
```
