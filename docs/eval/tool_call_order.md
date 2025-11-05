# Tool Call Order Evaluator

The Tool Call Order Evaluator validates that an agent calls tools in the expected sequence. This is crucial for workflows where the order of operations matters for correctness, data integrity, or business logic.

## Overview

**Evaluator ID**: `tool-call-order`

**Use Cases**:

-   Validate critical operation sequences (e.g., authenticate before access)
-   Ensure workflow steps follow business logic
-   Test that agents follow prescribed procedures
-   Verify proper data pipeline execution order

**Returns**: Continuous score from 0.0 to 1.0 based on sequence match

## Configuration

### ToolCallOrderEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ToolCallOrderEvaluator"` | The evaluator's name |
| `strict` | `bool` | `False` | If True, requires exact sequence match; if False, uses LCS (Longest Common Subsequence) |
| `default_evaluation_criteria` | `ToolCallOrderEvaluationCriteria or None` | `None` | Default criteria |

### Strict vs Non-Strict Mode

- **Strict mode** (`strict=True`): Requires exact sequence match, score is 1.0 or 0.0
- **Non-strict mode** (`strict=False`): Uses LCS algorithm, allows partial credit for subsequences

## Evaluation Criteria

### ToolCallOrderEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_calls_order` | `list[str]` | Ordered list of expected tool names |

## Scoring Algorithm

### Non-Strict Mode (LCS-based)

The score is calculated as:

```
score = length(LCS) / length(expected_sequence)
```

Where LCS is the Longest Common Subsequence between expected and actual tool call sequences.

**Example**:
- Expected: `["A", "B", "C", "D"]`
- Actual: `["A", "X", "B", "D"]`
- LCS: `["A", "B", "D"]` (length 3)
- Score: `3/4 = 0.75`

### Strict Mode

- Returns `1.0` if sequences match exactly
- Returns `0.0` if any difference exists

## Examples

### Basic Tool Call Order Validation

```python
from opentelemetry.sdk.trace import ReadableSpan
from uipath.eval.evaluators import ToolCallOrderEvaluator
from uipath.eval.models import AgentExecution

# Create mock spans representing tool calls in execution trace
mock_spans = [
    ReadableSpan(
        name="validate_user",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "validate_user"},
    ),
    ReadableSpan(
        name="check_inventory",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "check_inventory"},
    ),
    ReadableSpan(
        name="create_order",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "create_order"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Process user order"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOrderEvaluator(
    id="order-check-1",
    config={
        "name": "ToolCallOrderEvaluator",
        "strict": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_order": [
            "validate_user",
            "check_inventory",
            "create_order"
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (perfect match)
print(f"Details: {result.details}")
# Details includes: actual order, expected order, and LCS
```

### Strict Order Validation

```python
from opentelemetry.sdk.trace import ReadableSpan

# Critical security sequence
mock_spans = [
    ReadableSpan(
        name="authenticate_user",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "authenticate_user"},
    ),
    ReadableSpan(
        name="verify_permissions",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "verify_permissions"},
    ),
    ReadableSpan(
        name="access_resource",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "access_resource"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Access secured resource"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOrderEvaluator(
    id="order-strict",
    config={
        "name": "ToolCallOrderEvaluator",
        "strict": True
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_order": [
            "authenticate_user",
            "verify_permissions",
            "access_resource"
        ]
    }
)

# Score is either 1.0 (perfect match) or 0.0 (any mismatch)
print(f"Score: {result.score}")  # 1.0
```

### Partial Credit with LCS

```python
from opentelemetry.sdk.trace import ReadableSpan

# Actual execution (missing "sort")
mock_spans = [
    ReadableSpan(
        name="search",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "search"},
    ),
    ReadableSpan(
        name="filter",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "filter"},
    ),
    ReadableSpan(
        name="display",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "display"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Search and display"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOrderEvaluator(
    id="order-lcs",
    config={
        "name": "ToolCallOrderEvaluator",
        "strict": False  # Use LCS for partial credit
    }
)

# Expected sequence
expected = ["search", "filter", "sort", "display"]

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_order": expected
    }
)

# Score: 3/4 = 0.75 (3 tools in correct order out of 4 expected)
print(f"Score: {result.score}")  # 0.75
print(f"LCS: {result.details.lcs}")  # ["search", "filter", "display"]
```

### Database Transaction Sequence

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="begin_transaction",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "begin_transaction"},
    ),
    ReadableSpan(
        name="validate_data",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "validate_data"},
    ),
    ReadableSpan(
        name="update_records",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "update_records"},
    ),
    ReadableSpan(
        name="commit_transaction",
        start_time=3,
        end_time=4,
        attributes={"tool.name": "commit_transaction"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Update database"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOrderEvaluator(
    id="db-transaction",
    config={
        "name": "ToolCallOrderEvaluator",
        "strict": True  # Transactions must be exact
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_order": [
            "begin_transaction",
            "validate_data",
            "update_records",
            "commit_transaction"
        ]
    }
)

# Must match exactly for data integrity
print(f"Score: {result.score}")  # 1.0
```

### API Integration Workflow

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="get_api_token",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "get_api_token"},
    ),
    ReadableSpan(
        name="fetch_user_data",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "fetch_user_data"},
    ),
    ReadableSpan(
        name="enrich_data",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "enrich_data"},
    ),
    ReadableSpan(
        name="post_to_webhook",
        start_time=3,
        end_time=4,
        attributes={"tool.name": "post_to_webhook"},
    ),
    ReadableSpan(
        name="log_result",
        start_time=4,
        end_time=5,
        attributes={"tool.name": "log_result"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "API integration"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOrderEvaluator(
    id="api-workflow",
    config={
        "name": "ToolCallOrderEvaluator",
        "strict": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_order": [
            "get_api_token",
            "fetch_user_data",
            "enrich_data",
            "post_to_webhook",
            "log_result"
        ]
    }
)

print(f"Score: {result.score}")  # 1.0
```

### Using Default Criteria

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="init",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "init"},
    ),
    ReadableSpan(
        name="process",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "process"},
    ),
    ReadableSpan(
        name="cleanup",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "cleanup"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Standard workflow"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOrderEvaluator(
    id="order-default",
    config={
        "name": "ToolCallOrderEvaluator",
        "strict": False,
        "default_evaluation_criteria": {
            "tool_calls_order": ["init", "process", "cleanup"]
        }
    }
)

# Use default criteria
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria=None  # Uses default
)

print(f"Score: {result.score}")  # 1.0
```

## Justification Details

The evaluator returns a `ToolCallOrderEvaluatorJustification` with:

```python
{
    "actual_tool_calls_order": ["tool1", "tool2", "tool3"],  # What the agent called
    "expected_tool_calls_order": ["tool1", "tool2", "tool3", "tool4"],  # What was expected
    "lcs": ["tool1", "tool2", "tool3"]  # Longest common subsequence (non-strict mode)
}
```

## Best Practices

1. **Use strict mode for critical sequences** - Authentication, transactions, data integrity workflows
2. **Use non-strict mode for flexible workflows** - When some steps might be optional or reorderable
3. **Combine with other evaluators** - Use with [Tool Call Count](tool_call_count.md) and [Tool Call Args](tool_call_args.md)
4. **Be specific with tool names** - Ensure tool names in criteria match exactly (case-sensitive)
5. **Consider repeated calls** - If a tool should be called multiple times, list it multiple times
6. **Test partial workflows** - Use non-strict mode during development, strict in production

## When to Use vs Other Evaluators

**Use Tool Call Order when**:

- Sequence of operations is important
- Workflow has defined steps
- Business logic requires specific order
- Data dependencies exist between steps

**Use Tool Call Count when**:

- Order doesn't matter, only frequency
- Testing tool usage patterns
- Ensuring tools are called correct number of times

**Use LLM Judge Trajectory when**:

- More flexible, semantic evaluation needed
- Decision-making process is complex
- Exact sequences are less important than overall behavior

## Limitations

1. **Case-sensitive matching** - Tool names must match exactly
2. **No argument validation** - Only checks tool names, not arguments (use [Tool Call Args Evaluator](tool_call_args.md))
3. **Position-based** - Doesn't consider parallel execution
4. **Multiple calls** - Each call is treated as separate position in sequence

## Error Handling

The evaluator handles these scenarios gracefully:

-   **Empty actual calls**: Score 0.0
-   **Empty expected calls**: Error (invalid criteria)
-   **Missing tools in trace**: Extracts only tool calls found
-   **Extra tools called**: In non-strict mode, uses LCS; in strict mode, score 0.0

## Performance Considerations

-   **Fast evaluation**: O(n*m) for LCS algorithm
-   **No LLM calls**: Deterministic and quick
-   **Low memory**: Efficient for large sequences

## Related Evaluators

-   [Tool Call Count Evaluator](tool_call_count.md): Validates tool usage frequencies
-   [Tool Call Args Evaluator](tool_call_args.md): Validates tool arguments
-   [Tool Call Output Evaluator](tool_call_output.md): Validates tool outputs
-   [LLM Judge Trajectory Evaluator](llm_judge_trajectory.md): For semantic trajectory evaluation


