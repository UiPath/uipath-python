# Conversational Agent Licensing - Implementation Plan

## 1. Background & Problem Statement

Today, licensing for conversational agents is handled **server-side** in the Agents backend (C#/.NET). The `ConversationalEngineWorkflow` checks the `EnableConversationalLicensing` feature flag and calls `ValidateCanConsumeAsyncNew()` before each user exchange, using the `ConversationalAgents.Playground` or `ConversationalAgents.Execution` operation codes.

However, the **Python runtime** (used for coded conversational agents) does **not** perform any conversational-specific licensing checks. It only calls a generic `register_licensing_async()` once at agent startup, hitting the `/agenthub_/llm/api/execution-cost-tmp` endpoint. This is a fire-and-forget registration — it does not validate whether the tenant/user actually has available units, and it does not use conversational-specific operation codes.

**Goal**: Add proper licensing enforcement for conversational agents in the Python runtime so that:
1. Before execution starts, the runtime checks if the tenant has available conversational agent units
2. If no units are available, execution is rejected with a clear error
3. After execution, consumption is registered with the correct conversational operation code
4. The behavior is gated behind the existing `EnableConversationalLicensing` feature flag

---

## 2. Architecture Overview

### 2.1 Current Runtime Wrapper Chain (Python)

The Python runtime uses a **composition/wrapper pattern** where each layer adds a specific responsibility. The chain is assembled in `AgentsRuntimeFactory._create_runtime()`:

```
[Outermost — returned to caller]
  InstrumentedRuntime           →  Tracing, telemetry, span management
    UiPathResumableRuntime      →  Suspend/resume, trigger persistence
      AgentsLangGraphRuntime    →  Core LangGraph execution
[Innermost — actual agent logic]
```

At the CLI level, additional wrappers may be added on top:
- `UiPathDebugRuntime` (for `uipath run --debug`)
- `UiPathChatRuntime` (for `uipath run --chat`)
- `UiPathExecutionRuntime` (for evals)

All wrappers implement `UiPathRuntimeProtocol` and follow the same pattern:

```python
class SomeRuntime:
    def __init__(self, delegate: UiPathRuntimeProtocol, ...):
        self.delegate = delegate

    async def execute(self, input, options) -> UiPathRuntimeResult:
        # pre-processing
        result = await self.delegate.execute(input, options)
        # post-processing
        return result

    async def stream(self, input, options) -> AsyncGenerator:
        # pre-processing
        async for event in self.delegate.stream(input, options):
            yield event
        # post-processing
```

### 2.2 Current Licensing Flow (Python)

In `AgentsRuntimeFactory._create_runtime()` (line ~373 of `factory.py`):

```python
if not self.context.resume:
    from uipath_agents._services import register_licensing_async
    await register_licensing_async(agent_definition, job_key=UiPathConfig.job_key)
```

This is called **after** the runtime stack is built, **before** the runtime is returned. It is:
- A one-time fire-and-forget POST to `/agenthub_/llm/api/execution-cost-tmp`
- Not conversational-aware (no special operation code)
- Silent on failure (catches all exceptions)
- Does NOT validate availability — only registers consumption

### 2.3 Server-Side Licensing (Agents Backend - C#)

The Agents backend has a mature licensing system:

- **Feature Flag**: `EnableConversationalLicensing` (default: `false`)
- **Validation**: `LicensingExecutor.ValidateCanConsumeAsyncNew()` → calls License Accountant `CanConsumeAsync()`
- **Consumption**: `LicensingExecutor.RegisterConsumptionAsyncNew()` → calls License Accountant `RegisterConsumptionAsync()`
- **Operation Codes**: `ConversationalAgents.Playground` and `ConversationalAgents.Execution` (defined in `LicensingOperationCodes.cs`)
- **License Accountant API**: External service at `/{organizationId}/lease_/` that manages unit quotas

### 2.4 How Conversational Agents Are Identified

| Layer | Mechanism |
|-------|-----------|
| **agent.json** | `metadata.isConversational: true` |
| **Python AgentDefinition** | `agent_definition.is_conversational` property |
| **Python Factory** | Already checks `agent_definition.is_conversational` to augment input schema |
| **Agents Backend** | `AgentMetadata.IsConversational` field on `AgentDefinition` record |
| **AgentHubService** | Determined by route (`/a2a/...` = conversational) |

---

## 3. Proposed Design

### 3.1 New Runtime Wrapper: `ConversationalLicensingRuntime`

Create a new runtime wrapper that:
1. **Before execution**: Calls the License Accountant API to validate that the tenant has available conversational agent units
2. **After execution**: Registers consumption with the correct conversational operation code and token usage metadata
3. **On validation failure**: Raises a structured error that prevents execution

### 3.2 Where It Sits in the Chain

```
[Outermost — returned to caller]
  ConversationalLicensingRuntime  →  NEW: License check + consumption registration
    InstrumentedRuntime           →  Tracing, telemetry, span management
      UiPathResumableRuntime      →  Suspend/resume, trigger persistence
        AgentsLangGraphRuntime    →  Core LangGraph execution
[Innermost — actual agent logic]
```

**Why outside InstrumentedRuntime?**
- If a license check fails, we don't want an orphaned telemetry span
- Keeps traces clean — only successful (or in-progress) executions get traced
- The licensing wrapper is a guard, not part of the execution itself

**Why not inside?**
- If you want observability into license failures (e.g., to know how often users are getting blocked), you'd put it inside. This is a tradeoff to discuss. For now, outside is cleaner.

### 3.3 Conditional Wrapping

The wrapper is **only applied when all of these are true**:
1. `agent_definition.is_conversational == True`
2. The `EnableConversationalLicensing` feature flag is enabled (fetched from the feature flags API)
3. Not a resume execution (`self.context.resume == False`) — on resume, the license was already validated at the start of the conversation

---

## 4. Implementation Details

### Part 1: Add a License Validation Service (Python)

**Repo**: `uipath-agents-python`
**File**: `src/uipath_agents/_services/licensing_service.py` (extend existing file)

Currently, this file only has `register_consumption_async()` which POSTs to `/agenthub_/llm/api/execution-cost-tmp`. We need to add:

#### 1a. `validate_can_consume_async()` Method

A new method on `LicensingService` that calls the License Accountant API to check quota availability.

**What it does:**
- Makes an HTTP request to the License Accountant service to check if the tenant/user has available units for the `ConversationalAgents.Execution` (or `ConversationalAgents.Playground`) operation
- Returns `True` if units are available, `False` if not
- Raises on network/unexpected errors

**API to call:**
- The License Accountant API is at `/{organizationId}/lease_/` (same service used by the C# backend)
- The specific endpoint and payload should match what `LicensingClient.CanConsumeAsync()` uses in the C# backend (at `/home/user/repos/Agents/backend/External.Clients/Licensing/LicensingClient.cs`)
- The C# backend uses the `UiPath.LicenseAccountant.Client` NuGet package, which wraps the REST API. The Python side needs to call the same REST endpoint directly.

**Key parameters:**
- `organization_id`: From `UIPATH_ORGANIZATION_ID` env var (available via `UiPathConfig.organization_id`)
- `operation_code`: `"ConversationalAgents.Execution"` or `"ConversationalAgents.Playground"` depending on source
- Authentication: Bearer token from `UIPATH_ACCESS_TOKEN`

**Determining the source (Playground vs Execution):**
- If `UIPATH_JOB_KEY` is set → the agent is running as an Orchestrator job → source is `"Execution"` → operation code is `"ConversationalAgents.Execution"`
- If `UIPATH_JOB_KEY` is NOT set → the agent is running locally or in playground → source is `"Playground"` → operation code is `"ConversationalAgents.Playground"`

#### 1b. `register_conversational_consumption_async()` Method

A new method to register consumption with conversational-specific operation codes.

**What it does:**
- After successful execution, registers the consumption (token usage, LLM calls) with the License Accountant
- Uses `ConversationalAgents.Execution` or `ConversationalAgents.Playground` operation code
- Passes metadata: model name, input/output tokens, LLM call count

**Note:** This replaces the generic `register_licensing_async()` call for conversational agents. Non-conversational agents continue using the existing flow.

---

### Part 2: Add Feature Flag Check (Python)

**Repo**: `uipath-agents-python`
**File**: `src/uipath_agents/_config/feature_flags.py` (extend existing file)

The feature flags infrastructure already exists. The `get_flags()` function calls `/agentsruntime_/api/featureFlags` to fetch flag values.

#### What to do:

Add a helper function:

```python
async def is_conversational_licensing_enabled() -> bool:
    """Check if the EnableConversationalLicensing feature flag is enabled."""
    flags = await get_flags(["EnableConversationalLicensing"])
    return flags.get("EnableConversationalLicensing", False)
```

This follows the same pattern used for other feature flags in the codebase.

---

### Part 3: Add Error Code and Exception (Python)

**Repo**: `uipath-runtime-python`
**File**: `src/uipath/runtime/errors/codes.py`

Add a new error code to the `UiPathErrorCode` enum:

```python
class UiPathErrorCode(str, Enum):
    # ... existing codes ...
    LICENSE_NOT_AVAILABLE = "LICENSE_NOT_AVAILABLE"
```

**File**: `src/uipath/runtime/errors/exception.py` (or create a new convenience class)

The existing `UiPathRuntimeError` class can be used directly:

```python
raise UiPathRuntimeError(
    code=UiPathErrorCode.LICENSE_NOT_AVAILABLE,
    title="License not available",
    detail="Your action could not be completed. You've used all your units for this period. Please contact your organization admin to get more units.",
    category=UiPathErrorCategory.DEPLOYMENT,
    include_traceback=False,
)
```

**Why `DEPLOYMENT` category?** This is consistent with how the C# error codes classify licensing issues — they're configuration/deployment-level problems, not user logic errors or system failures.

**What happens when this error is raised:**
1. The runtime context manager (`UiPathRuntimeContext.__exit__`) catches it
2. It writes a result file with `status: "faulted"` and the structured error
3. The orchestrator/caller reads this and surfaces the error to the user

---

### Part 4: Create the `ConversationalLicensingRuntime` Wrapper (Python)

**Repo**: `uipath-agents-python`
**New File**: `src/uipath_agents/_licensing/conversational_licensing_runtime.py`

This is the core new component. It follows the exact same wrapper pattern as `InstrumentedRuntime`, `UiPathResumableRuntime`, `UiPathDebugRuntime`, etc.

#### Class Structure:

```python
class ConversationalLicensingRuntime:
    """Runtime wrapper that enforces licensing for conversational agents.

    Validates that the tenant has available conversational agent units
    before allowing execution to proceed. Only wraps conversational agents
    when the EnableConversationalLicensing feature flag is enabled.
    """

    def __init__(
        self,
        delegate: UiPathRuntimeProtocol,
        licensing_service: LicensingService,
        operation_code: str,
    ):
        self.delegate = delegate
        self._licensing_service = licensing_service
        self._operation_code = operation_code
```

#### `execute()` method:

```
1. Call licensing_service.validate_can_consume_async(operation_code)
2. If NOT available → raise UiPathRuntimeError(LICENSE_NOT_AVAILABLE)
3. result = await self.delegate.execute(input, options)
4. If result.status == SUCCESSFUL:
      Call licensing_service.register_conversational_consumption_async(...)
5. Return result
```

#### `stream()` method:

```
1. Call licensing_service.validate_can_consume_async(operation_code)
2. If NOT available → raise UiPathRuntimeError(LICENSE_NOT_AVAILABLE)
3. Yield all events from self.delegate.stream(input, options)
4. After stream completes, if final result was SUCCESSFUL:
      Call licensing_service.register_conversational_consumption_async(...)
```

#### `get_schema()` method:

```
Pass-through to self.delegate.get_schema()
```

#### `dispose()` method:

```
Pass-through to self.delegate.dispose()
```

#### Error handling:

- License validation failure → raise `UiPathRuntimeError` → execution does NOT proceed
- License validation network error → **log warning and allow execution** (fail-open, consistent with existing `register_licensing_async` behavior that silently catches exceptions). This is a design decision — we don't want licensing service downtime to block all agent executions. Discuss with team whether fail-open or fail-closed is desired.
- Consumption registration failure → **log warning, don't fail execution** (already-completed work shouldn't be lost due to billing errors)

---

### Part 5: Wire It Into the Factory (Python)

**Repo**: `uipath-agents-python`
**File**: `src/uipath_agents/_cli/runtime/factory.py`

Modify the `_create_runtime()` method to conditionally wrap with the licensing runtime.

#### Current code (simplified):

```python
async def _create_runtime(self, ...):
    # ... build base_runtime, resumable_runtime ...

    instrumented_runtime = InstrumentedRuntime(resumable_runtime, ...)

    if not self.context.resume:
        await register_licensing_async(agent_definition, job_key=...)

    return instrumented_runtime
```

#### New code (simplified):

```python
async def _create_runtime(self, ...):
    # ... build base_runtime, resumable_runtime ...

    instrumented_runtime = InstrumentedRuntime(resumable_runtime, ...)

    # Existing generic licensing registration (for non-conversational)
    if not self.context.resume:
        await register_licensing_async(agent_definition, job_key=...)

    # NEW: Wrap with conversational licensing if applicable
    if (
        agent_definition
        and agent_definition.is_conversational
        and not self.context.resume
    ):
        if await is_conversational_licensing_enabled():
            operation_code = _get_conversational_operation_code()
            licensing_service = _create_licensing_service()
            return ConversationalLicensingRuntime(
                delegate=instrumented_runtime,
                licensing_service=licensing_service,
                operation_code=operation_code,
            )

    return instrumented_runtime
```

#### Helper: `_get_conversational_operation_code()`

```python
def _get_conversational_operation_code() -> str:
    if UiPathConfig.job_key:
        return "ConversationalAgents.Execution"
    else:
        return "ConversationalAgents.Playground"
```

---

### Part 6: Handling Resume Scenarios

When a conversational agent is **resumed** (e.g., after a human-in-the-loop interrupt), the licensing wrapper should NOT re-validate. The license was already checked when the conversation started.

This is handled by the condition `not self.context.resume` in Part 5 — when resuming, the factory returns `InstrumentedRuntime` directly without the licensing wrapper.

However, for **long-running conversational agents** where the user sends multiple messages in a conversation (each message is a new execution of the runtime), the license should be checked on each new message. This is the same behavior as the C# backend, which calls `ValidateCanConsumeAsyncNew()` at the start of each exchange.

**The key distinction:**
- **Resume** (same execution, continuing after interrupt) → No re-check
- **New message** (new execution in same conversation) → Check again

The Python runtime handles these differently:
- Resume: `self.context.resume == True`, options.resume == True
- New message: A completely new `execute()` call with `self.context.resume == False`

So the wrapper naturally handles this correctly — it checks on every `execute()` / `stream()` call, and the factory only skips wrapping on resume.

---

## 5. Repository & File Summary

### Changes by Repository

#### `uipath-runtime-python` (1 file changed)

| File | Change |
|------|--------|
| `src/uipath/runtime/errors/codes.py` | Add `LICENSE_NOT_AVAILABLE` error code |

#### `uipath-agents-python` (4 files changed, 1 file created)

| File | Change |
|------|--------|
| `src/uipath_agents/_services/licensing_service.py` | Add `validate_can_consume_async()` and `register_conversational_consumption_async()` methods |
| `src/uipath_agents/_config/feature_flags.py` | Add `is_conversational_licensing_enabled()` helper |
| `src/uipath_agents/_licensing/conversational_licensing_runtime.py` | **NEW** — The `ConversationalLicensingRuntime` wrapper class |
| `src/uipath_agents/_cli/runtime/factory.py` | Wire up conditional wrapping in `_create_runtime()` |

#### `Agents` and `AgentHubService` (no changes expected)

The server-side licensing infrastructure already exists and already has the correct operation codes (`ConversationalAgents.Playground`, `ConversationalAgents.Execution`). No changes needed unless we need to expose additional API endpoints for the Python runtime to call.

---

## 6. Testing Strategy

### Unit Tests

| Test | Location | What it validates |
|------|----------|-------------------|
| `test_licensing_wrapper_blocks_when_no_units` | `uipath-agents-python/tests/unit/` | License check returns false → execution is blocked with `LICENSE_NOT_AVAILABLE` error |
| `test_licensing_wrapper_allows_when_units_available` | `uipath-agents-python/tests/unit/` | License check returns true → execution proceeds normally |
| `test_licensing_wrapper_not_applied_to_non_conversational` | `uipath-agents-python/tests/unit/` | Non-conversational agents don't get the wrapper |
| `test_licensing_wrapper_not_applied_when_flag_disabled` | `uipath-agents-python/tests/unit/` | Feature flag off → no wrapper even for conversational agents |
| `test_licensing_wrapper_not_applied_on_resume` | `uipath-agents-python/tests/unit/` | Resume execution → no wrapper |
| `test_licensing_wrapper_registers_consumption_on_success` | `uipath-agents-python/tests/unit/` | After successful execution, consumption is registered |
| `test_licensing_wrapper_no_consumption_on_failure` | `uipath-agents-python/tests/unit/` | Failed execution → no consumption registered |
| `test_licensing_fail_open_on_network_error` | `uipath-agents-python/tests/unit/` | License service unreachable → execution proceeds (fail-open) |
| `test_operation_code_playground_vs_execution` | `uipath-agents-python/tests/unit/` | Correct operation code based on presence of `UIPATH_JOB_KEY` |

### Integration Tests

- Test with a real (or mocked) License Accountant service
- Verify end-to-end flow: feature flag check → license validation → execution → consumption registration
- Verify error propagation: license denied → structured error in result file

---

## 7. Open Questions & Design Decisions

### Q1: Fail-Open vs Fail-Closed?

**Current behavior for existing licensing**: Fail-open (silently catch exceptions, never block execution).

**Recommendation**: Start with fail-open for consistency. If the licensing service is down, agents should still run. Log a warning so ops teams can detect issues.

**Alternative**: Fail-closed (block execution if licensing service is unreachable). More secure but risks availability issues.

### Q2: Should the wrapper go outside or inside InstrumentedRuntime?

**Current plan**: Outside (license check fails → no telemetry span created).

**Alternative**: Inside (license failures appear in telemetry, useful for dashboards/monitoring).

**Recommendation**: Outside for now. We can add a separate telemetry event for license failures if needed, without creating a full execution span.

### Q3: Which License Accountant API endpoint to call?

The C# backend uses the `UiPath.LicenseAccountant.Client` NuGet package. The Python side needs to call the raw REST API directly. We need to verify the exact endpoints:
- **CanConsume**: Likely `GET /{orgId}/lease_/api/account/{orgId}/usage` with operation code filter
- **RegisterConsumption**: Likely `POST /{orgId}/lease_/api/account/{orgId}/usage-event/ingest`

**Action**: Inspect the `UiPath.LicenseAccountant.Client` NuGet package or the C# client code to determine exact REST endpoints and payloads.

### Q4: Should consumption registration be synchronous or async (background)?

The C# backend uses **Temporal workflows** for async consumption registration to avoid blocking execution. The Python runtime doesn't have Temporal.

**Recommendation**: Make the consumption registration call after execution completes. If it fails, log a warning but don't fail the execution. The HTTP call should be fast enough (< 1 second) to not noticeably impact latency.

### Q5: Per-message vs per-conversation licensing?

The C# backend checks licensing **per user message** (each exchange in a conversation). The Python runtime should match this behavior.

Since each user message in a conversational agent is a separate `execute()` call to the runtime, the wrapper naturally checks on each call. No special handling needed.

---

## 8. Rollout Plan

1. **Phase 1**: Implement behind feature flag (flag defaults to `false`)
   - Deploy the code to all environments
   - No behavioral change until flag is enabled

2. **Phase 2**: Enable in staging/test environments
   - Verify license checks work correctly
   - Verify fail-open behavior on service errors
   - Verify consumption tracking accuracy

3. **Phase 3**: Gradual rollout to production
   - Enable per-tenant using LaunchDarkly segmentation
   - Monitor for false rejections or missing consumption records

4. **Phase 4**: Enable globally
   - Set `EnableConversationalLicensing` default to `true`
   - Monitor dashboards for any issues

---

## 9. Dependency Diagram

```
                    +--------------------------+
                    |   License Accountant     |
                    |   (External Service)     |
                    |   /{orgId}/lease_/       |
                    +-----------+--------------+
                                ^
                                | HTTP (validate + register)
                                |
+------------------+    +-------+----------------+    +------------------+
| Feature Flags    |    | ConversationalLicensing|    | InstrumentedRuntime|
| Service          |--->| Runtime (NEW)          |--->| (existing)        |
| /agentsruntime_/ |    |                        |    |                   |
+------------------+    +------------------------+    +------------------+
        ^                                                      |
        |                                               delegates to
        |                                                      v
   fetched once                                     +------------------+
   at factory time                                  | ResumableRuntime |
                                                    +------------------+
                                                           |
                                                    delegates to
                                                           v
                                                    +------------------+
                                                    | LangGraphRuntime |
                                                    +------------------+
```
