# Tool Call Args Evaluator

The Tool Call Args Evaluator validates that an agent calls tools with the correct arguments. This is essential for ensuring proper data flow, correct API usage, and validating that agents pass the right information to functions.

## Overview

**Evaluator ID**: `tool-call-args`

**Use Cases**:

-   Validate tool parameters are correct
-   Ensure proper data flow between tools
-   Test argument transformation logic
-   Verify API parameter usage
-   Check data type correctness

**Returns**: Continuous score from 0.0 to 1.0 based on argument accuracy

## Configuration

### ToolCallArgsEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ToolCallArgsEvaluator"` | The evaluator's name |
| `strict` | `bool` | `False` | Controls scoring when multiple tools expected: True = all-or-nothing (1.0 or 0.0), False = proportional (ratio of matched tools) |
| `subset` | `bool` | `False` | If True, actual args can be a subset of expected; if False, must match all expected args |
| `default_evaluation_criteria` | `ToolCallArgsEvaluationCriteria or None` | `None` | Default criteria |

### Evaluation Modes

| Mode | Description |
|------|-------------|
| `strict=False, subset=False` | Proportional scoring (e.g., 2/3 tools matched = 0.66), exact arg matching required |
| `strict=True, subset=False` | All-or-nothing scoring (1.0 or 0.0), exact arg matching required |
| `strict=False, subset=True` | Proportional scoring, expected args must be subset of actual (extra args allowed) |
| `strict=True, subset=True` | All-or-nothing scoring, expected args must be subset of actual (extra args allowed) |

## Evaluation Criteria

### ToolCallArgsEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_calls` | `list[ToolCall]` | List of expected tool calls with their arguments |

### ToolCall Structure

```python
{
    "name": "tool_name",           # Tool name
    "args": {"key": "value"}  # Expected arguments
}
```

## Scoring Algorithm

For each tool call:
1. Match tool calls by name
2. Compare arguments based on mode (strict or JSON similarity)
3. Calculate score based on match quality

**Final score**: Average across all expected tool calls

## Examples

### Basic Argument Validation

```python
from opentelemetry.sdk.trace import ReadableSpan
from uipath.eval.evaluators import ToolCallArgsEvaluator
from uipath.eval.models import AgentExecution

# Sample agent execution with tool calls and arguments
mock_spans = [
    ReadableSpan(
        name="update_user",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "update_user",
            "input.value": "{'user_id': 123, 'fields': {'email': 'user@example.com'}, 'notify': True}",
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"user_id": 123, "action": "update"},
    agent_output={"status": "success"},
    agent_trace=mock_spans,
)

evaluator = ToolCallArgsEvaluator(
    id="args-check-1",
    config={
        "name": "ToolCallArgsEvaluator",
        "strict": False,
        "subset": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls": [
            {
                "name": "update_user",
                "args": {
                    "user_id": 123,
                    "fields": {"email": "user@example.com"},
                    "notify": True
                }
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (exact match)
print(f"Details: {result.details}")
```

### Strict Mode - Exact Matching

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="api_request",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "api_request",
            "input.value": "{'endpoint': '/api/users', 'method': 'GET', 'headers': {'Authorization': 'Bearer token123'}}",
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"action": "fetch_users"},
    agent_output={"status": "success"},
    agent_trace=mock_spans,
)

evaluator = ToolCallArgsEvaluator(
    id="args-strict",
    config={
        "name": "ToolCallArgsEvaluator",
        "strict": True,
        "subset": False
    }
)

# Arguments must match exactly
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls": [
            {
                "name": "api_request",
                "args": {
                    "endpoint": "/api/users",
                    "method": "GET",
                    "headers": {"Authorization": "Bearer token123"}
                }
            }
        ]
    }
)

# Score is 1.0 only if arguments match exactly
print(f"Score: {result.score}")  # 1.0
```

### Non-Strict Mode - Proportional Scoring

```python
from opentelemetry.sdk.trace import ReadableSpan
from uipath.eval.evaluators import ToolCallArgsEvaluator
from uipath.eval.models import AgentExecution

# Agent called 3 tools, but only 2 match the expected args
mock_spans = [
    ReadableSpan(
        name="validate_input",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "validate_input",
            "input.value": "{'data': {'user_id': 123}}",  # ✓ Matches
        },
    ),
    ReadableSpan(
        name="fetch_user",
        start_time=1,
        end_time=2,
        attributes={
            "tool.name": "fetch_user",
            "input.value": "{'user_id': 999}",  # ✗ Wrong ID!
        },
    ),
    ReadableSpan(
        name="update_profile",
        start_time=2,
        end_time=3,
        attributes={
            "tool.name": "update_profile",
            "input.value": "{'user_id': 123, 'updates': {'name': 'John Doe'}}",  # ✓ Matches
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Update user profile"},
    agent_output={"status": "updated"},
    agent_trace=mock_spans,
)

evaluator = ToolCallArgsEvaluator(
    id="args-proportional",
    config={
        "name": "ToolCallArgsEvaluator",
        "strict": False,  # Proportional scoring
        "subset": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls": [
            {
                "name": "validate_input",
                "args": {"data": {"user_id": 123}}  # ✓ Matches
            },
            {
                "name": "fetch_user",
                "args": {"user_id": 123}  # ✗ Actual was 999
            },
            {
                "name": "update_profile",
                "args": {
                    "user_id": 123,
                    "updates": {"name": "John Doe"}  # ✓ Matches
                }
            }
        ]
    }
)

# Score is 2/3 = 0.66 (2 out of 3 tools matched)
print(f"Score: {result.score}")  # 0.66 (proportional!)
```

### Subset Mode - Partial Validation

```python
from opentelemetry.sdk.trace import ReadableSpan

# Agent included extra arguments beyond what we're validating
mock_spans = [
    ReadableSpan(
        name="send_email",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "send_email",
            "input.value": "{'to': 'user@example.com', 'subject': 'Welcome', 'cc': 'admin@example.com', 'body': 'Welcome to our platform!'}",
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"action": "send_welcome"},
    agent_output={"status": "sent"},
    agent_trace=mock_spans,
)

evaluator = ToolCallArgsEvaluator(
    id="args-subset",
    config={
        "name": "ToolCallArgsEvaluator",
        "strict": False,
        "subset": True
    }
)

# Only validate specific arguments, allow extras
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls": [
            {
                "name": "send_email",
                "args": {
                    "to": "user@example.com",
                    "subject": "Welcome"
                    # Agent can include additional args like "cc", "bcc", "body", etc.
                }
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (subset matches)
```

### Multiple Tool Calls

```python
from opentelemetry.sdk.trace import ReadableSpan

# Agent called multiple tools in sequence
mock_spans = [
    ReadableSpan(
        name="validate_input",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "validate_input",
            "input.value": "{'data': {'user_id': 123}}",
        },
    ),
    ReadableSpan(
        name="fetch_user",
        start_time=1,
        end_time=2,
        attributes={
            "tool.name": "fetch_user",
            "input.value": "{'user_id': 123}",
        },
    ),
    ReadableSpan(
        name="update_profile",
        start_time=2,
        end_time=3,
        attributes={
            "tool.name": "update_profile",
            "input.value": "{'user_id': 123, 'updates': {'name': 'John Doe'}}",
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Update user profile"},
    agent_output={"status": "updated"},
    agent_trace=mock_spans,
)

evaluator = ToolCallArgsEvaluator(
    id="args-multiple",
    config={
        "name": "ToolCallArgsEvaluator",
        "strict": False,
        "subset": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls": [
            {
                "name": "validate_input",
                "args": {"data": {"user_id": 123}}
            },
            {
                "name": "fetch_user",
                "args": {"user_id": 123}
            },
            {
                "name": "update_profile",
                "args": {
                    "user_id": 123,
                    "updates": {"name": "John Doe"}
                }
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (all tools match)
```

### Nested Arguments

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="create_order",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "create_order",
            "input.value": "{'customer': {'id': 123, 'name': 'John Doe', 'address': {'street': '123 Main St', 'city': 'New York', 'zip': '10001'}}, 'items': [{'product_id': 1, 'quantity': 2}, {'product_id': 2, 'quantity': 1}], 'total': 99.99}",
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Create order"},
    agent_output={"status": "created"},
    agent_trace=mock_spans,
)

evaluator = ToolCallArgsEvaluator(
    id="args-nested",
    config={
        "name": "ToolCallArgsEvaluator",
        "strict": False,
        "subset": False
    }
)

# Validate complex nested structures
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_calls": [
            {
                "name": "create_order",
                "args": {
                    "customer": {
                        "id": 123,
                        "name": "John Doe",
                        "address": {
                            "street": "123 Main St",
                            "city": "New York",
                            "zip": "10001"
                        }
                    },
                    "items": [
                        {"product_id": 1, "quantity": 2},
                        {"product_id": 2, "quantity": 1}
                    ],
                    "total": 99.99
                }
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (nested structure matches)
```

## Justification Details

The evaluator returns a `ToolCallArgsEvaluatorJustification` with:

```python
{
    "explained_tool_calls_args": {
        "update_user_0": "Actual: {'user_id': 123, 'status': 'active'}, Expected: {'user_id': 123, 'status': 'active'}, Score: 1.0",
        "send_email_0": "Actual: {'to': 'user@example.com', 'subject': 'Hello'}, Expected: {'to': 'user@example.com'}, Score: 1.0",
        "log_event_0": "Actual: {'type': 'info', 'message': 'Success'}, Expected: {'type': 'info'}, Score: 1.0"
    }
}
```

## Best Practices

1. **Use non-strict mode by default** - Allows for minor numeric or string variations
2. **Use subset mode for flexibility** - When some arguments are optional or variable
3. **Combine with order validation** - Use with [Tool Call Order Evaluator](tool_call_order.md)
4. **Test critical parameters in strict mode** - For security, authentication, or business-critical params
5. **Validate data types** - Ensure strings, numbers, booleans are used correctly
6. **Test edge cases** - Empty strings, null values, zero, negative numbers
7. **Consider partial matches** - Non-strict mode gives partial credit for similar values

## When to Use vs Other Evaluators

**Use Tool Call Args when**:

- Argument values matter
- Testing data flow correctness
- Validating parameter transformation
- Ensuring API contract compliance

**Use Tool Call Order when**:

- Sequence matters more than arguments
- Testing workflow steps

**Use Tool Call Output when**:

- Validating what tools return
- Testing tool response handling

**Use JSON Similarity when**:

- Comparing complex outputs (not tool args)
- General data structure comparison

## Limitations

1. **Tool name matching** - Must match exact tool names from trace
2. **Order matters for multiple calls** - First expected call matches first actual call of that name
3. **No cross-tool validation** - Each tool evaluated independently
4. **Case-sensitive** - Keys and values are case-sensitive

## Error Handling

The evaluator handles:

- **Missing tools**: Score 0.0 for that tool
- **Extra tools not in criteria**: Ignored
- **Missing arguments**: Scored based on mode
- **Type mismatches**: Scored based on mode (strict vs non-strict)

## Performance Considerations

- **Fast evaluation**: O(n*m) where n = expected calls, m = actual calls
- **No LLM calls**: Deterministic and quick
- **JSON similarity overhead**: Slightly slower than exact match

## Related Evaluators

- [Tool Call Order Evaluator](tool_call_order.md): Validates tool call sequences
- [Tool Call Count Evaluator](tool_call_count.md): Validates tool usage frequencies
- [Tool Call Output Evaluator](tool_call_output.md): Validates tool outputs
- [JSON Similarity Evaluator](json_similarity.md): For general JSON comparison


