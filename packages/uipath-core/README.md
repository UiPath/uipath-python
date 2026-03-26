# UiPath Core

[![PyPI - Version](https://img.shields.io/pypi/v/uipath-core)](https://pypi.org/project/uipath-core/)
[![PyPI downloads](https://img.shields.io/pypi/dm/uipath-core.svg)](https://pypi.org/project/uipath-core/)
[![Python versions](https://img.shields.io/pypi/pyversions/uipath-core.svg)](https://pypi.org/project/uipath-core/)

Core abstractions and contracts for the UiPath Python SDK.

## Installation

```bash
pip install uipath-core
```

## Modules

### Errors

Exception hierarchy for UiPath trigger errors with category-based classification.

- **`ErrorCategory`**: Enum: `DEPLOYMENT`, `SYSTEM`, `UNKNOWN`, `USER`
- **`UiPathFaultedTriggerError`**: Base trigger error with category and detail
- **`UiPathPendingTriggerError`**: Pending trigger variant

```python
from uipath.core.errors import ErrorCategory, UiPathFaultedTriggerError
```

### Serialization

JSON serialization utilities for complex Python types. Handles Pydantic models (v1 & v2), dataclasses, enums, datetime/timezone objects, sets, tuples, and named tuples.

- **`serialize_json(obj)`**: Serialize any object to a JSON string
- **`serialize_defaults(obj)`**: Custom `default` handler for `json.dumps()`

```python
from uipath.core.serialization import serialize_json
```

### Tracing

OpenTelemetry integration with UiPath execution tracking. Provides function instrumentation, span lifecycle management, custom exporters, and batch/simple span processors with automatic `execution.id` propagation.

- **`@traced`**: Decorator for sync/async function instrumentation. Supports custom span names, run types, input/output processors, and non-recording spans
- **`UiPathTraceManager`**: Manages `TracerProvider`, span exporters, and processors. Provides `start_execution_span()` context manager and span retrieval by execution ID
- **`UiPathSpanUtils`**: Span registry and parent context management
- **`UiPathTraceSettings`**: Configuration model with optional span filtering

```python
from uipath.core.tracing import traced, UiPathTraceManager

@traced(name="my_operation", run_type="tool")
def do_work(input: str) -> str:
    return process(input)
```

### Guardrails

Deterministic rule-based validation for inputs and outputs. Rules are evaluated pre-execution (input-only) and post-execution (all rules), with flexible field selection using dot-notation paths and array access (`[*]`).

**Rule types:**
- **`WordRule`**: String pattern matching
- **`NumberRule`**: Numeric constraint validation
- **`BooleanRule`**: Boolean assertions
- **`UniversalRule`**: Always-apply constraints

**Field selection:**
- **`AllFieldsSelector`**: Apply to all fields of a given source (input/output)
- **`SpecificFieldsSelector`**: Target specific fields by path

**Service:**
- **`DeterministicGuardrailsService`**: Evaluates guardrail rules against inputs/outputs, returning `GuardrailValidationResult` with pass/fail status and reason

```python
from uipath.core.guardrails import DeterministicGuardrailsService, GuardrailValidationResultType
```

### Chat

Pydantic models for the UiPath conversation event protocol. Defines the streaming event schema between clients and LLM/agent backends.

**Hierarchy:**
```
Conversation → Exchange → Message → Content Parts (with Citations)
                                  → Tool Calls (with Results)
                                  → Interrupts (human-in-the-loop)
```

Supports session capabilities negotiation, async input streams (audio/video), tool call confirmation interrupts, URL and media citations, and inline/external value references.

```python
from uipath.core.chat import UiPathConversationEvent, UiPathSessionStartEvent
```

## Dependencies

| Package | Version |
|---|---|
| `pydantic` | `>=2.12.5, <3` |
| `opentelemetry-sdk` | `>=1.39.0, <2` |
| `opentelemetry-instrumentation` | `>=0.60b0, <1` |


