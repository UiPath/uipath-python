# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the `uipath-core` package.

## Package Purpose

Core abstractions shared across the UiPath Python SDK. This is the lowest-level package — it has no dependency on `uipath` or `uipath-platform`. Depends on OpenTelemetry and Pydantic.

## Development Commands

```bash
cd packages/uipath-core

uv sync --all-extras          # Install dependencies
pytest                        # Run all tests
pytest tests/tracing/         # Run a test subdirectory
pytest tests/tracing/test_traced.py::test_name  # Single test
ruff check .                  # Lint
ruff format --check .         # Format check
mypy src tests                # Type check
```

No justfile exists for this package — run commands directly.

## Modules

### `chat/` — Conversation Protocol Models
Pydantic models for a hierarchical conversation event protocol (sessions, exchanges, messages, tool calls, citations, interrupts, content parts, async streams). ~45 exported classes. This defines the wire format between UI clients and agents/LLMs.

### `tracing/` — OpenTelemetry Instrumentation
- `@traced` decorator — instruments sync/async functions with OpenTelemetry spans. Supports `recording=False` for non-recording spans, custom `input_processor`/`output_processor`, and span context propagation.
- `UiPathTraceManager` — central management of tracer providers, span processors, and exporters.
- `UiPathSpanUtils` — span registry and utilities.
- `UiPathTraceSettings` — settings with optional `span_filter` callable.

### `guardrails/` — Deterministic Validation Rules
Rule engine for validating input/output data with `WordRule`, `NumberRule`, `BooleanRule`, `UniversalRule`. `DeterministicGuardrailsService` evaluates rules pre- and post-execution (skipping output-dependent rules during pre-execution).

### `serialization/` — JSON Serialization
`serialize_json()`, `serialize_object()`, `serialize_defaults()` — handles Pydantic v1/v2, dataclasses, enums, datetime, namedtuples, sets.

### `events/` — Event Bus
`EventBus` — simple async pub/sub with `subscribe()`, `unsubscribe()`, `publish()`.

### `feature_flags/` — Feature Flag Registry
`FeatureFlags` singleton. Sources: programmatic config (takes precedence) + `UIPATH_FEATURE_*` env vars. Supports structured types via JSON parsing.

### `errors/` — Exception Types
`UiPathFaultedTriggerError`, `UiPathPendingTriggerError`, `ErrorCategory` enum (DEPLOYMENT, SYSTEM, UNKNOWN, USER).

### `triggers/` — Resume Trigger Models
`UiPathResumeTrigger`, `UiPathApiTrigger`, and trigger type/name enums. Pydantic models with camelCase aliases.

## Test Structure

Tests mirror the module structure under `tests/`. The `tracing/` subdirectory has the most tests (8 files covering decorator behavior, span nesting, registry, filtering, serialization, external integration).

### Key Test Fixture

`conftest.py` provides a session-scoped `span_capture` fixture using `InMemorySpanExporter`. An autouse fixture `clear_spans_between_tests` resets it before each test. Use `span_capture.get_spans()` to assert on traced function behavior.
