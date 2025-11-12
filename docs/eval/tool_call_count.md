# Tool Call Count Evaluator

The Tool Call Count Evaluator validates that an agent calls tools the expected number of times. This is useful for ensuring proper tool usage patterns, avoiding redundant calls, and verifying workflow completeness.

## Overview

**Evaluator ID**: `tool-call-count`

**Use Cases**:

-   Ensure tools are called the correct number of times
-   Validate no redundant or missing tool calls
-   Test resource usage efficiency
-   Verify loop and retry logic
-   Check API call frequency

**Returns**: Continuous score from 0.0 to 1.0 based on count accuracy

## Configuration

### ToolCallCountEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ToolCallCountEvaluator"` | The evaluator's name |
| `strict` | `bool` | `False` | Controls scoring: True = all-or-nothing (1.0 or 0.0), False = proportional (ratio of matched counts) |
| `default_evaluation_criteria` | `ToolCallCountEvaluationCriteria or None` | `None` | Default criteria |

### Strict vs Non-Strict Mode

- **Strict mode** (`strict=True`): All-or-nothing - returns 1.0 if ALL counts match, 0.0 if ANY count doesn't match
- **Non-strict mode** (`strict=False`): Proportional scoring - returns ratio of matched counts (e.g., 2/3 match = 0.66)

## Evaluation Criteria

### ToolCallCountEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_calls_count` | `dict[str, tuple[str, int]]` | Dictionary mapping tool names to (operator, count) tuples |

### Supported Operators

- `"="` or `"=="`: Exactly equal to count
- `">"`: Greater than count
- `"<"`: Less than count
- `">="`: Greater than or equal to count
- `"<="`: Less than or equal to count

## Scoring Algorithm

### Non-Strict Mode

```
score = correct_tools / total_expected_tools
```

Each tool is evaluated independently:
- Correct count match = 1.0 for that tool
- Incorrect count = 0.0 for that tool
- Final score is average across all tools

### Strict Mode

- Returns `1.0` if ALL tools match their count criteria
- Returns `0.0` if ANY tool fails its count criteria

## Examples

### Basic Count Validation

```python
from opentelemetry.sdk.trace import ReadableSpan
from uipath.eval.evaluators import ToolCallCountEvaluator
from uipath.eval.models import AgentExecution

# Sample agent execution with tool calls
mock_spans = [
    ReadableSpan(name="fetch_data", start_time=0, end_time=1,
                 attributes={"tool.name": "fetch_data"}),
    ReadableSpan(name="process_item", start_time=1, end_time=2,
                 attributes={"tool.name": "process_item"}),
    ReadableSpan(name="process_item", start_time=2, end_time=3,
                 attributes={"tool.name": "process_item"}),
    ReadableSpan(name="process_item", start_time=3, end_time=4,
                 attributes={"tool.name": "process_item"}),
    ReadableSpan(name="process_item", start_time=4, end_time=5,
                 attributes={"tool.name": "process_item"}),
    ReadableSpan(name="process_item", start_time=5, end_time=6,
                 attributes={"tool.name": "process_item"}),
    ReadableSpan(name="send_notification", start_time=6, end_time=7,
                 attributes={"tool.name": "send_notification"}),
]

agent_execution = AgentExecution(
    agent_input={"task": "Fetch and process data"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="count-check-1",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "fetch_data": ("=", 1),      # Called exactly once
            "process_item": ("=", 5),    # Called exactly 5 times
            "send_notification": ("=", 1)  # Called exactly once
        }
    }
)

print(f"Score: {result.score}")  # 1.0 (all counts match)
print(f"Details: {result.details}")
```

### Non-Strict Mode - Proportional Scoring

```python
from opentelemetry.sdk.trace import ReadableSpan

# Agent called fetch_data 1x, process_item 3x (expected 5), send_notification 1x
mock_spans = [
    ReadableSpan(
        name="fetch_data",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "fetch_data"},
    ),
]
# Add 3 process_item calls (but we expect 5)
for i in range(3):
    mock_spans.append(
        ReadableSpan(
            name="process_item",
            start_time=1 + i,
            end_time=2 + i,
            attributes={"tool.name": "process_item"},
        )
    )
mock_spans.append(
    ReadableSpan(
        name="send_notification",
        start_time=4,
        end_time=5,
        attributes={"tool.name": "send_notification"},
    )
)

agent_execution = AgentExecution(
    agent_input={"task": "Fetch and process data"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="count-proportional",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": False  # Proportional scoring
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "fetch_data": ("=", 1),           # ✓ Matches (1 call)
            "process_item": ("=", 5),         # ✗ Doesn't match (3 calls, expected 5)
            "send_notification": ("=", 1)     # ✓ Matches (1 call)
        }
    }
)

# Score is 2/3 = 0.66 (2 out of 3 counts matched)
print(f"Score: {result.score}")  # 0.66 (proportional!)
```

### Strict Mode - All or Nothing

```python
from opentelemetry.sdk.trace import ReadableSpan

# Agent made 2 calls but expected 1
mock_spans = [
    ReadableSpan(
        name="authenticate",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "authenticate"},
    ),
    ReadableSpan(
        name="fetch_records",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "fetch_records"},
    ),
    ReadableSpan(
        name="fetch_records",  # DUPLICATE call
        start_time=2,
        end_time=3,
        attributes={"tool.name": "fetch_records"},
    ),
    ReadableSpan(
        name="close_connection",
        start_time=3,
        end_time=4,
        attributes={"tool.name": "close_connection"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Database operation"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="count-strict",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": True  # All-or-nothing scoring
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "authenticate": ("=", 1),      # ✓ Matches (1 call)
            "fetch_records": ("=", 1),     # ✗ Doesn't match (2 calls)
            "close_connection": ("=", 1)   # ✓ Matches (1 call)
        }
    }
)

# Score is 0.0 because ONE count didn't match (strict mode)
print(f"Score: {result.score}")  # 0.0 (not 0.66!)
```

### Preventing Redundant Calls

```python
from opentelemetry.sdk.trace import ReadableSpan

# Only one expensive call
mock_spans = [
    ReadableSpan(
        name="expensive_api_call",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "expensive_api_call"},
    ),
    ReadableSpan(
        name="database_query",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "database_query"},
    ),
    ReadableSpan(
        name="database_query",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "database_query"},
    ),
    ReadableSpan(
        name="llm_call",
        start_time=3,
        end_time=4,
        attributes={"tool.name": "llm_call"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Optimize resource usage"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="prevent-redundant",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": False
    }
)

# Ensure expensive operations aren't called too many times
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "expensive_api_call": ("<=", 1),  # Should not be called more than once
            "database_query": ("<=", 3),      # At most 3 queries
            "llm_call": ("<=", 2)             # At most 2 LLM calls
        }
    }
)

print(f"Score: {result.score}")  # 1.0 (all within limits)
```

### Loop Validation

```python
from opentelemetry.sdk.trace import ReadableSpan

# Create 10 process_item, 10 validate_item, 10 save_result calls
mock_spans = []
for i in range(10):
    mock_spans.extend([
        ReadableSpan(
            name="process_item",
            start_time=i * 3,
            end_time=i * 3 + 1,
            attributes={"tool.name": "process_item"},
        ),
        ReadableSpan(
            name="validate_item",
            start_time=i * 3 + 1,
            end_time=i * 3 + 2,
            attributes={"tool.name": "validate_item"},
        ),
        ReadableSpan(
            name="save_result",
            start_time=i * 3 + 2,
            end_time=i * 3 + 3,
            attributes={"tool.name": "save_result"},
        ),
    ])

agent_execution = AgentExecution(
    agent_input={"task": "Process 10 items"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="loop-validation",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": False
    }
)

# Verify loop processed correct number of items
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "process_item": ("=", 10),  # Should process 10 items
            "validate_item": ("=", 10), # Each item should be validated
            "save_result": ("=", 10)    # Each result should be saved
        }
    }
)

print(f"Score: {result.score}")  # 1.0 (all counts correct)
```

### Retry Logic Validation

```python
from opentelemetry.sdk.trace import ReadableSpan

# Agent attempted operation 2 times, logged retry, got final result
mock_spans = [
    ReadableSpan(
        name="attempt_operation",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "attempt_operation"},
    ),
    ReadableSpan(
        name="log_retry",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "log_retry"},
    ),
    ReadableSpan(
        name="attempt_operation",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "attempt_operation"},
    ),
    ReadableSpan(
        name="final_result",
        start_time=3,
        end_time=4,
        attributes={"tool.name": "final_result"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Retry operation"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="retry-logic",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": False
    }
)

# Verify retry logic doesn't exceed limits
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "attempt_operation": ("<=", 3),  # Max 3 retries
            "log_retry": (">=", 1),          # Should log retries
            "final_result": ("=", 1)         # Only one final result
        }
    }
)

print(f"Score: {result.score}")  # 1.0 (retry logic correct)
```

### Ensuring Minimum Calls

```python
from opentelemetry.sdk.trace import ReadableSpan

# Agent called all required security checks
mock_spans = [
    ReadableSpan(
        name="validate_input",
        start_time=0,
        end_time=1,
        attributes={"tool.name": "validate_input"},
    ),
    ReadableSpan(
        name="check_security",
        start_time=1,
        end_time=2,
        attributes={"tool.name": "check_security"},
    ),
    ReadableSpan(
        name="audit_log",
        start_time=2,
        end_time=3,
        attributes={"tool.name": "audit_log"},
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Secure operation"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallCountEvaluator(
    id="minimum-calls",
    config={
        "name": "ToolCallCountEvaluator",
        "strict": False
    }
)

# Ensure agent calls important tools
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls_count": {
            "validate_input": (">=", 1),    # Must validate at least once
            "check_security": (">=", 1),    # Security check required
            "audit_log": (">", 0)           # Must create audit logs
        }
    }
)

print(f"Score: {result.score}")  # 1.0 (minimum calls met)
```

## Justification Details

The evaluator returns a `ToolCallCountEvaluatorJustification` with:

```python
{
    "explained_tool_calls_count": {
        "fetch_data": "Actual: 1, Expected: 1, Score: 1.0",
        "process_item": "Actual: 3, Expected: 5, Score: 0.0",
        "send_notification": "Actual: 1, Expected: 1, Score: 1.0"
    }
}
```

## Best Practices

1. **Use for resource-sensitive operations** - Database queries, API calls, expensive computations
2. **Combine with order validation** - Use with [Tool Call Order Evaluator](tool_call_order.md) for complete validation
3. **Set realistic bounds** - Use `<=` and `>=` for flexible but bounded behavior
4. **Use strict mode sparingly** - Non-strict provides better debugging information
5. **Consider variability** - Use ranges (`>=`, `<=`) when exact counts might vary
6. **Test efficiency** - Ensure agents don't make redundant calls

## When to Use vs Other Evaluators

**Use Tool Call Count when**:

- Tool usage frequency matters
- Testing efficiency and optimization
- Validating retry logic
- Ensuring resource constraints

**Use Tool Call Order when**:

- Sequence matters more than count
- Workflow has specific steps
- Dependencies exist between tools

**Use Tool Call Args when**:

- Tool parameters need validation
- Specific argument values matter
- Testing data flow through tools

## Limitations

1. **Case-sensitive tool names** - Must match exactly
2. **No temporal information** - Doesn't know when calls happened
3. **No context awareness** - Doesn't understand why counts differ
4. **All tools independent** - Each tool evaluated separately

## Error Handling

The evaluator handles:

- **Missing tools in actual calls**: Count as 0
- **Extra tools not in criteria**: Ignored
- **Invalid operators**: Raises validation error
- **Negative counts**: Raises validation error

## Performance Considerations

- **Fast evaluation**: O(n) where n is number of tools
- **No LLM calls**: Deterministic and instant
- **Low memory**: Efficient for large call counts

## Related Evaluators

- [Tool Call Order Evaluator](tool_call_order.md): Validates tool call sequences
- [Tool Call Args Evaluator](tool_call_args.md): Validates tool arguments
- [Tool Call Output Evaluator](tool_call_output.md): Validates tool outputs
- [LLM Judge Trajectory Evaluator](llm_judge_trajectory.md): For semantic evaluation


