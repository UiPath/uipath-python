# Agent Interrupt, Suspend & Resume Architecture

## Overview

This document explains how the interrupt/suspend/resume pattern works across the UiPath agent system, focusing on the **correct separation of concerns** between `uipath-langchain-python` (framework-specific) and `uipath-python` (framework-agnostic).

## Architecture Principles

### 1. Framework Abstraction Boundary

```
┌─────────────────────────────────────────────────────────────┐
│ uipath-langchain-python (Framework-Specific)                │
│                                                               │
│ - UiPathLangGraphRuntime                                     │
│ - Knows about LangGraph's interrupt() and StateSnapshot     │
│ - Detects __interrupt__ fields                              │
│ - Converts LangGraph Interrupt objects to UiPath triggers   │
└─────────────────────────┬───────────────────────────────────┘
                          │ UiPathRuntimeResult
                          │ (with UiPathResumeTrigger)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ uipath-python (Framework-Agnostic)                          │
│                                                               │
│ - UiPathResumableRuntime                                     │
│ - UiPathResumeTrigger (abstract trigger model)              │
│ - Trigger lifecycle management                              │
│ - Storage layer                                             │
│ - MUST NOT know about LangGraph specifics                   │
└─────────────────────────────────────────────────────────────┘
```

**Key principle:** LangGraph concepts (like `__interrupt__`, `Interrupt` objects, `StateSnapshot`) must **NEVER** leak into `uipath-python`. The framework-agnostic layer should only work with abstracted `UiPathResumeTrigger` objects.

## Information Flow

### Correct Flow (Current Design)

```
1. User Code (LangGraph Agent)
   ↓ calls interrupt()

2. LangGraph Framework
   ↓ creates StateSnapshot with interrupts

3. UiPathLangGraphRuntime (uipath-langchain-python)
   - Detects interrupts via StateSnapshot
   - Extracts Interrupt objects
   - Converts to UiPathResumeTrigger
   ↓ returns UiPathRuntimeResult(status=SUSPENDED, triggers=[...])

4. UiPathResumableRuntime (uipath-python)
   - Receives abstract triggers
   - Manages trigger lifecycle
   - Stores triggers
   - Calls TriggerManager.create_trigger()
   ↓ returns result to caller

5. Resume Flow
   - UiPathResumableRuntime calls TriggerManager.read_trigger()
   - Gets trigger data
   - Passes to base runtime (UiPathLangGraphRuntime)
   - LangGraph runtime resumes with data
```

### ❌ INCORRECT Pattern (Anti-pattern in UiPathFunctionsRuntime)

The following code at `/home/chibionos/r2/uipath-python/src/uipath/functions/runtime.py:132-195` violates the architecture:

```python
# ❌ WRONG: This is in uipath-python but knows about LangGraph!
def _detect_langgraph_interrupt(self, output: dict[str, Any]) -> UiPathResumeTrigger | None:
    """Detect LangGraph __interrupt__ field..."""  # ← Framework-specific knowledge!

    if "__interrupt__" not in output:  # ← LangGraph-specific field
        return None

    interrupts = output["__interrupt__"]
    interrupt_obj = interrupts[0]
    invoke_process = interrupt_obj.value  # ← LangGraph Interrupt object

    return UiPathResumeTrigger(...)  # Converts LangGraph to UiPath trigger
```

**Why this is wrong:**
1. `UiPathFunctionsRuntime` is in `uipath-python` (framework-agnostic layer)
2. It directly checks for `__interrupt__` (LangGraph-specific)
3. It knows about `Interrupt` objects (LangGraph-specific)
4. This breaks abstraction - what if we support other frameworks?

## Component Responsibilities

### uipath-langchain-python Components

#### UiPathLangGraphRuntime
**Location:** `/home/chibionos/r2/uipath-langchain-python/src/uipath_langchain/runtime/runtime.py`

**Responsibilities:**
- Execute LangGraph and get StateSnapshot
- Detect interrupts via `StateSnapshot.interrupts`
- Extract interrupt values from LangGraph's `Interrupt` objects
- Convert to `UiPathResumeTrigger` objects
- Return `UiPathRuntimeResult` with `SUSPENDED` status

**Key Methods:**
```python
def _is_interrupted(self, state: StateSnapshot) -> bool:
    """Check if execution was interrupted."""
    return bool(state.next) or bool(state.interrupts)

async def _create_suspended_result(self, graph_state: StateSnapshot) -> UiPathRuntimeResult:
    """Create result for suspended execution."""
    interrupt_map: dict[str, Any] = {}

    if graph_state.interrupts:
        for interrupt in graph_state.interrupts:
            if isinstance(interrupt, Interrupt):
                for task in graph_state.tasks:
                    if task.interrupts and interrupt in task.interrupts:
                        if task.interrupts and not task.result:
                            interrupt_map[interrupt.id] = interrupt.value

    if interrupt_map:
        return UiPathRuntimeResult(
            output=interrupt_map,
            status=UiPathRuntimeStatus.SUSPENDED,
        )
```

**Lines:** `runtime.py:296-351`

### uipath-python Components

#### UiPathResumableRuntime
**Location:** `/home/chibionos/r2/uipath-python/src/uipath/runtime/resumable/runtime.py`

**Responsibilities:**
- Wrap any runtime (delegate pattern)
- Manage trigger lifecycle
- Store/retrieve triggers via storage layer
- Call trigger manager methods
- **NEVER** know about framework specifics

**Key Methods:**
```python
async def execute(
    self,
    input: dict[str, Any] | None = None,
    options: UiPathExecuteOptions | None = None,
) -> UiPathRuntimeResult:
    # Execute delegate (could be LangGraph, functions, or any runtime)
    result = await self._delegate.execute(input, options)

    # If suspended, process triggers (framework-agnostic)
    if result.status == UiPathRuntimeStatus.SUSPENDED:
        triggers = []
        if result.trigger:
            triggers.append(result.trigger)
        if result.triggers:
            triggers.extend(result.triggers)

        # Create triggers via manager (abstracts RPA/API/etc.)
        for trigger in triggers:
            created_trigger = await self._trigger_manager.create_trigger(trigger.payload)
            # Store trigger
            await self._storage.save_trigger(self._runtime_id, created_trigger)

        return result
```

#### UiPathResumeTrigger
**Location:** `/home/chibionos/r2/uipath-python/src/uipath/runtime/resumable/trigger.py`

**Purpose:** Abstract trigger model that works across all frameworks

**Key Fields:**
```python
@dataclass
class UiPathResumeTrigger:
    trigger_type: UiPathResumeTriggerType  # JOB, TASK, API, etc.
    trigger_name: UiPathResumeTriggerName
    item_key: str | None = None
    folder_path: str | None = None
    payload: dict[str, Any] | None = None  # Framework-agnostic payload
```

**Trigger Types:**
- `JOB` - RPA process invocation (from `InvokeProcess`)
- `TASK` - Human-in-the-loop task (from `CreateTask`)
- `API` - External API call (from `APIInput`)
- `DEEP_RAG` - Document retrieval (from `CreateDeepRag`)
- `BATCH_RAG` - Batch processing (from `CreateBatchTransform`)

## Correct Implementation Pattern

### For Framework-Specific Runtimes (LangGraph, CrewAI, etc.)

**Location:** In framework-specific package (e.g., `uipath-langchain-python`)

```python
class UiPathLangGraphRuntime:
    """LangGraph-specific runtime."""

    async def execute(self, input, options) -> UiPathRuntimeResult:
        # Execute LangGraph
        state = await self._graph.ainvoke(input, config)

        # Detect framework-specific interrupts
        if self._is_interrupted(state):
            # Convert framework interrupts to abstract triggers
            triggers = self._extract_triggers(state)
            return UiPathRuntimeResult(
                output=None,
                status=UiPathRuntimeStatus.SUSPENDED,
                triggers=triggers  # Abstract UiPathResumeTrigger objects
            )

        return UiPathRuntimeResult(
            output=state,
            status=UiPathRuntimeStatus.SUCCESSFUL
        )

    def _is_interrupted(self, state: StateSnapshot) -> bool:
        """Framework-specific interrupt detection."""
        return bool(state.interrupts)  # LangGraph-specific

    def _extract_triggers(self, state: StateSnapshot) -> list[UiPathResumeTrigger]:
        """Convert LangGraph interrupts to abstract triggers."""
        triggers = []
        for interrupt in state.interrupts:
            # Convert interrupt.value to UiPathResumeTrigger
            trigger = self._convert_interrupt_value(interrupt.value)
            triggers.append(trigger)
        return triggers
```

### For Framework-Agnostic Components

**Location:** In `uipath-python`

```python
class UiPathResumableRuntime:
    """Framework-agnostic resumable runtime wrapper."""

    async def execute(self, input, options) -> UiPathRuntimeResult:
        # Execute ANY runtime (LangGraph, functions, custom, etc.)
        result = await self._delegate.execute(input, options)

        # Work with abstract triggers only
        if result.status == UiPathRuntimeStatus.SUSPENDED:
            if result.triggers:
                for trigger in result.triggers:
                    # trigger is abstract UiPathResumeTrigger
                    # No knowledge of LangGraph/__interrupt__/etc.
                    await self._process_trigger(trigger)

        return result
```

## Testing Patterns

### Testing Framework-Specific Runtime

**Location:** `uipath-langchain-python/tests/runtime/test_resumable.py`

```python
@pytest.mark.asyncio
async def test_langgraph_interrupt_detection():
    """Test LangGraph-specific interrupt detection."""

    # Define graph with interrupt()
    def node_with_interrupt(state):
        result = interrupt({"message": "Need input"})
        return {"result": result}

    graph = StateGraph(State)
    graph.add_node("node", node_with_interrupt)
    compiled = graph.compile(checkpointer=AsyncSqliteSaver(...))

    # Create LangGraph runtime
    runtime = UiPathLangGraphRuntime(graph=compiled, ...)

    # Execute - should detect interrupt
    result = await runtime.execute({"input": "test"})

    assert result.status == UiPathRuntimeStatus.SUSPENDED
    assert result.triggers is not None
    assert len(result.triggers) > 0
```

### Testing Framework-Agnostic Runtime

**Location:** `uipath-python/tests/runtime/test_resumable.py`

```python
@pytest.mark.asyncio
async def test_resumable_runtime_with_mock():
    """Test resumable runtime with mock delegate."""

    # Mock ANY runtime (not LangGraph-specific)
    class MockRuntime:
        async def execute(self, input, options):
            return UiPathRuntimeResult(
                output=None,
                status=UiPathRuntimeStatus.SUSPENDED,
                triggers=[
                    UiPathResumeTrigger(
                        trigger_type=UiPathResumeTriggerType.API,
                        payload={"data": "mock"}
                    )
                ]
            )

    # Create resumable runtime (framework-agnostic)
    runtime = UiPathResumableRuntime(
        delegate=MockRuntime(),
        storage=...,
        trigger_manager=...
    )

    # Test trigger lifecycle
    result = await runtime.execute({})
    assert result.status == UiPathRuntimeStatus.SUSPENDED
```

## Problem: UiPathFunctionsRuntime Violates Architecture

### Current Issue

**File:** `/home/chibionos/r2/uipath-python/src/uipath/functions/runtime.py`
**Lines:** 132-195

The `_detect_langgraph_interrupt()` method brings LangGraph-specific knowledge into the framework-agnostic layer:

```python
def _detect_langgraph_interrupt(self, output: dict[str, Any]) -> UiPathResumeTrigger | None:
    """Detect LangGraph __interrupt__ field and extract InvokeProcess trigger."""  # ❌

    # Check for LangGraph's __interrupt__ field  # ❌
    if "__interrupt__" not in output:  # ❌
        return None

    interrupts = output["__interrupt__"]  # ❌
    interrupt_obj = interrupts[0]  # ❌
    invoke_process = interrupt_obj.value  # ❌
```

### Why This is Wrong

1. **Location:** `UiPathFunctionsRuntime` is in `uipath-python` (should be framework-agnostic)
2. **Knowledge:** Knows about `__interrupt__` (LangGraph-specific field name)
3. **Dependencies:** Expects LangGraph's `Interrupt` object structure
4. **Coupling:** Tightly coupled to LangGraph implementation details
5. **Extensibility:** Cannot support other frameworks (CrewAI, AutoGen, etc.)

### Correct Approach

**Option 1: Remove LangGraph Detection from UiPathFunctionsRuntime**

Functions runtime should not detect interrupts at all - it should execute functions and return output. If the function is a LangGraph agent, the LangGraph runtime should handle interrupts.

**Option 2: Use Delegation Pattern**

If functions runtime needs to support LangGraph agents, it should:
1. Detect if the function returns a runtime result
2. Delegate to appropriate framework-specific runtime
3. Never parse framework-specific structures itself

```python
# ✅ CORRECT: Framework-agnostic
class UiPathFunctionsRuntime:
    async def execute(self, input, options) -> UiPathRuntimeResult:
        func = self._load_function()
        output = await self._execute_function(func, input)

        # If output is already a UiPathRuntimeResult, return it
        if isinstance(output, UiPathRuntimeResult):
            return output

        # Otherwise, function completed successfully
        return UiPathRuntimeResult(
            output=output,
            status=UiPathRuntimeStatus.SUCCESSFUL
        )
```

## Migration Path

### Step 1: Remove LangGraph-Specific Code from UiPathFunctionsRuntime

**File:** `uipath-python/src/uipath/functions/runtime.py`

Remove:
- `_detect_langgraph_interrupt()` method (lines 132-195)
- All references to `__interrupt__` field
- All references to LangGraph `Interrupt` objects

### Step 2: Ensure LangGraph Runtime Handles All LangGraph Interrupts

**File:** `uipath-langchain-python/src/uipath_langchain/runtime/runtime.py`

Ensure:
- `_is_interrupted()` detects all interrupt cases
- `_create_suspended_result()` extracts all interrupt types
- Conversion to `UiPathResumeTrigger` is complete

### Step 3: Update Documentation

Update both repositories' documentation to clarify:
- Framework-specific code stays in framework packages
- uipath-python remains framework-agnostic
- Trigger abstraction is the boundary

## Summary: Key Takeaways

### ✅ Correct Patterns

1. **LangGraph-specific code** → `uipath-langchain-python`
2. **Framework-agnostic code** → `uipath-python`
3. **Abstraction boundary** → `UiPathResumeTrigger`
4. **Runtime wrapping** → `UiPathResumableRuntime` wraps any runtime

### ❌ Anti-Patterns

1. **Don't** check for `__interrupt__` in `uipath-python`
2. **Don't** parse LangGraph structures in framework-agnostic layer
3. **Don't** mix framework knowledge in abstract components
4. **Don't** violate the abstraction boundary

### 🎯 Architecture Goal

**Enable UiPath agents to work with ANY framework** (LangGraph, CrewAI, AutoGen, custom) by:
- Keeping framework specifics in framework packages
- Using abstract trigger model as the interface
- Maintaining clean separation of concerns
- Supporting extensibility without coupling

## Related Files

### uipath-langchain-python
- `/src/uipath_langchain/runtime/runtime.py` - LangGraph runtime (lines 296-351)
- `/tests/runtime/test_resumable.py` - LangGraph interrupt tests

### uipath-python
- `/src/uipath/runtime/resumable/runtime.py` - Framework-agnostic resumable runtime
- `/src/uipath/runtime/resumable/trigger.py` - Abstract trigger model
- `/src/uipath/functions/runtime.py` - ⚠️ Contains problematic LangGraph-specific code (lines 132-195)
- `/tests/cli/test_hitl.py` - Trigger manager tests

## References

- LangGraph interrupt() documentation: https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/
- UiPath resume trigger types: See `UiPathResumeTriggerType` enum
- Test patterns: See `test_resumable.py` for complete examples
