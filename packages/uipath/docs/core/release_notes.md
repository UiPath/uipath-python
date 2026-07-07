---
title: Release Notes
---

# Release Notes

A catalog of the releases most relevant to UiPath Python SDK users (breaking changes and notable updates). Full details live in each GitHub release, linked below.

## `uipath` (SDK & CLI)

| Release | Date | What's relevant | Notes |
|---------|------|-----------------|-------|
| [v2.12.0](https://github.com/UiPath/uipath-python/releases/tag/v2.12.0) | 2026-06-30 | Eval framework: `AgentExecution` → `WorkloadExecution`; fields `agent_trace`/`agent_output` → `workload_trace`/`workload_output`; `evaluate()`/`validate_and_evaluate_criteria()` keyword `agent_execution` → `workload_execution` | 🚨 Breaking — see [migration](#migration-v2120-eval-workloadexecution-rename) |
| [v2.10.0](https://github.com/UiPath/uipath-python/releases/tag/v2.10.0) | 2026-02-27 | Coded function schema `type` changed from `"agent"` to `"function"` | 🚨 Breaking |
| [v2.9.0](https://github.com/UiPath/uipath-python/releases/tag/v2.9.0) | 2026-02-23 | `platform` extracted to `uipath-platform`, context grounding contract changes, `uipath dev` defaults to `web` | 🚨 Breaking |
| [v2.2.0](https://github.com/UiPath/uipath-python/releases/tag/v2.2.0) | 2025-11-26 | Python 3.11+ required, `UiPath` import moved to `uipath.platform`, configuration architecture redesign | 🚨 Breaking |

## `uipath-langchain`

| Release | Date | What's relevant | Notes |
|---------|------|-----------------|-------|
| [v0.10.0](https://github.com/UiPath/uipath-langchain-python/releases/tag/v0.10.0) | 2026-04-23 | Transport/auth split into new `uipath-llm-client` and `uipath-langchain-client` packages (legacy preserved) | Non-breaking |

## `uipath-runtime`

| Release | Date | What's relevant | Notes |
|---------|------|-----------------|-------|
| [v0.3.0](https://github.com/UiPath/uipath-runtime-python/releases/tag/v0.3.0) | 2025-12-18 | `UiPathDebugBridgeProtocol` renamed to `UiPathDebugProtocol` | 🚨 Breaking (protocol implementers only) |

## Migration: v2.12.0 (eval `WorkloadExecution` rename)

The eval framework's central execution type and its keyword parameters were renamed to
unified-evals terminology. The value passed to every evaluator represents *a workload
execution* (agent, process/orchestration, case management, …), not specifically an agent.

These are breaking changes for code that uses the affected public names. Update as follows:

| Before | After |
|--------|-------|
| `from uipath.eval.models import AgentExecution` | `from uipath.eval.models import WorkloadExecution` |
| `WorkloadExecution(agent_trace=...)` | `WorkloadExecution(workload_trace=...)` |
| `WorkloadExecution(agent_output=...)` | `WorkloadExecution(workload_output=...)` |
| `execution.agent_trace` / `execution.agent_output` | `execution.workload_trace` / `execution.workload_output` |
| `evaluator.evaluate(agent_execution=...)` | `evaluator.evaluate(workload_execution=...)` |
| `evaluator.validate_and_evaluate_criteria(agent_execution=...)` | `evaluator.validate_and_evaluate_criteria(workload_execution=...)` |

What still works:

- **`AgentExecution` (the class name)** is soft-deprecated: importing it still resolves to
  `WorkloadExecution` and emits a `DeprecationWarning` (removed in **uipath 3.0**). Note the
  *fields* are not aliased — constructing `AgentExecution(agent_output=..., agent_trace=...)`
  now raises a `ValidationError`; rename the fields as above.
- **Custom evaluators that override `evaluate` / `validate_and_evaluate_criteria` with the old
  `agent_execution` parameter name** keep running, because the runtime dispatches positionally.
  Only *callers* passing `agent_execution=` by keyword are affected.

Unchanged (intentionally): the `WorkloadExecution.agent_input` and
`expected_agent_behavior` fields, and the `agent_output` / `agent_execution_time` fields on
`EvalRunUpdatedEvent` and `StudioWebProgressItem` (the latter a Studio Web wire contract).
