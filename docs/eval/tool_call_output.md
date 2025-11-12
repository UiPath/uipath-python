# Tool Call Output Evaluator

The Tool Call Output Evaluator validates that tools return the expected outputs. This is crucial for testing tool integrations, verifying data transformations, and ensuring that agents correctly handle tool responses.

## Overview

**Evaluator ID**: `tool-call-output`

**Use Cases**:

-   Validate tool return values
-   Test tool integration correctness
-   Verify data processing results
-   Ensure proper error handling
-   Check API response handling

**Returns**: Continuous score from 0.0 to 1.0 based on output accuracy

## Configuration

### ToolCallOutputEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ToolCallOutputEvaluator"` | The evaluator's name |
| `strict` | `bool` | `False` | Controls scoring when multiple tools expected: True = all-or-nothing (1.0 or 0.0), False = proportional (ratio of matched outputs) |
| `default_evaluation_criteria` | `ToolCallOutputEvaluationCriteria or None` | `None` | Default criteria |

### Evaluation Modes

- **Strict mode** (`strict=True`): All-or-nothing - returns 1.0 if ALL outputs match, 0.0 if ANY output doesn't match
- **Non-strict mode** (`strict=False`): Proportional scoring - returns ratio of matched outputs (e.g., 2/3 match = 0.66)

## Evaluation Criteria

### ToolCallOutputEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_outputs` | `list[ToolOutput]` | List of expected tool outputs |

### ToolOutput Structure

```python
{
    "name": "tool_name",        # Tool name
    "output": {...}             # Expected output value
}
```

## Scoring Algorithm

For each expected tool output:
1. Find matching tool calls by name in the trace
2. Compare actual output with expected output
3. Use strict or JSON similarity comparison based on mode

**Final score**: Average across all expected tool outputs

## Examples

### Basic Output Validation

```python
from opentelemetry.sdk.trace import ReadableSpan
from uipath.eval.evaluators import ToolCallOutputEvaluator
from uipath.eval.models import AgentExecution

# Sample agent execution with tool calls and outputs
mock_spans = [
    ReadableSpan(
        name="get_user",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "get_user",
            "output.value": '{"content": "{\\"user_id\\": 123, \\"name\\": \\"John Doe\\", \\"email\\": \\"john@example.com\\", \\"status\\": \\"active\\"}"}',
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"user_id": 123},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOutputEvaluator(
    id="output-check-1",
    config={
        "name": "ToolCallOutputEvaluator",
        "strict": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_outputs": [
            {
                "name": "get_user",
                "output": '{"user_id": 123, "name": "John Doe", "email": "john@example.com", "status": "active"}'
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (exact match)
print(f"Details: {result.details}")
```

### Strict Mode - Exact Output Matching

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="calculate_total",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "calculate_total",
            "output.value": '{"content": "{\\"total\\": 99.99, \\"currency\\": \\"USD\\"}"}',
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"items": ["item1", "item2"]},
    agent_output={"status": "calculated"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOutputEvaluator(
    id="output-strict",
    config={
        "name": "ToolCallOutputEvaluator",
        "strict": True
    }
)

# Outputs must match exactly
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_outputs": [
            {
                "name": "calculate_total",
                "output": {"total": 99.99, "currency": "USD"}
            }
        ]
    }
)

# Score is 1.0 only if output matches exactly
print(f"Score: {result.score}")  # 1.0
```

### Non-Strict Mode - Proportional Scoring

```python
from opentelemetry.sdk.trace import ReadableSpan
from uipath.eval.evaluators import ToolCallOutputEvaluator
from uipath.eval.models import AgentExecution

# Agent produced 3 outputs, but only 2 match expected
mock_spans = [
    ReadableSpan(
        name="fetch_data",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "fetch_data",
            "output.value": '{"content": "{\\"records\\": 150, \\"status\\": \\"success\\"}"}',  # ✓ Matches
        },
    ),
    ReadableSpan(
        name="process_data",
        start_time=1,
        end_time=2,
        attributes={
            "tool.name": "process_data",
            "output.value": '{"content": "{\\"processed\\": 100, \\"errors\\": 5}"}',  # ✗ Wrong values
        },
    ),
    ReadableSpan(
        name="save_results",
        start_time=2,
        end_time=3,
        attributes={
            "tool.name": "save_results",
            "output.value": '{"content": "{\\"saved\\": 150, \\"location\\": \\"/data/results.csv\\"}"}',  # ✓ Matches
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Process data pipeline"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOutputEvaluator(
    id="output-proportional",
    config={
        "name": "ToolCallOutputEvaluator",
        "strict": False  # Proportional scoring
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_outputs": [
            {
                "name": "fetch_data",
                "output": '{"records": 150, "status": "success"}'  # ✓ Matches
            },
            {
                "name": "process_data",
                "output": '{"processed": 150, "errors": 0}'  # ✗ Actual had errors: 5
            },
            {
                "name": "save_results",
                "output": '{"saved": 150, "location": "/data/results.csv"}'  # ✓ Matches
            }
        ]
    }
)

# Score is 2/3 = 0.66 (2 out of 3 outputs matched)
print(f"Score: {result.score}")  # 0.66 (proportional!)
```

### Multiple Tool Outputs

```python
from opentelemetry.sdk.trace import ReadableSpan

# Multiple tools called in sequence
mock_spans = [
    ReadableSpan(
        name="fetch_data",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "fetch_data",
            "output.value": '{"content": "{\\"records\\": 150, \\"status\\": \\"success\\"}"}',
        },
    ),
    ReadableSpan(
        name="process_data",
        start_time=1,
        end_time=2,
        attributes={
            "tool.name": "process_data",
            "output.value": '{"content": "{\\"processed\\": 150, \\"errors\\": 0}"}',
        },
    ),
    ReadableSpan(
        name="save_results",
        start_time=2,
        end_time=3,
        attributes={
            "tool.name": "save_results",
            "output.value": '{"content": "{\\"saved\\": 150, \\"location\\": \\"/data/results.csv\\"}"}',
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Process data pipeline"},
    agent_output={"status": "completed"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOutputEvaluator(
    id="output-multiple",
    config={
        "name": "ToolCallOutputEvaluator",
        "strict": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_outputs": [
            {
                "name": "fetch_data",
                "output": {"records": 150, "status": "success"}
            },
            {
                "name": "process_data",
                "output": {"processed": 150, "errors": 0}
            },
            {
                "name": "save_results",
                "output": {"saved": 150, "location": "/data/results.csv"}
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (all outputs match)
```

### Complex Nested Outputs

```python
from opentelemetry.sdk.trace import ReadableSpan

mock_spans = [
    ReadableSpan(
        name="generate_report",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "generate_report",
            "output.value": '{"content": "{\\"report_id\\": \\"RPT-001\\", \\"summary\\": {\\"total_records\\": 1000, \\"processed\\": 950, \\"errors\\": 50}, \\"details\\": [{\\"category\\": \\"A\\", \\"count\\": 400}, {\\"category\\": \\"B\\", \\"count\\": 350}, {\\"category\\": \\"C\\", \\"count\\": 200}], \\"metadata\\": {\\"generated_at\\": \\"2024-01-01T12:00:00Z\\", \\"version\\": \\"1.0\\"}}"}',
        },
    ),
]

agent_execution = AgentExecution(
    agent_input={"task": "Generate report"},
    agent_output={"status": "generated"},
    agent_trace=mock_spans,
)

evaluator = ToolCallOutputEvaluator(
    id="nested-output",
    config={
        "name": "ToolCallOutputEvaluator",
        "strict": False
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "tool_outputs": [
            {
                "name": "generate_report",
                "output": {
                    "report_id": "RPT-001",
                    "summary": {
                        "total_records": 1000,
                        "processed": 950,
                        "errors": 50
                    },
                    "details": [
                        {"category": "A", "count": 400},
                        {"category": "B", "count": 350},
                        {"category": "C", "count": 200}
                    ],
                    "metadata": {
                        "generated_at": "2024-01-01T12:00:00Z",
                        "version": "1.0"
                    }
                }
            }
        ]
    }
)

print(f"Score: {result.score}")  # 1.0 (nested output matches)
```

## Justification Details

The evaluator returns a `ToolCallOutputEvaluatorJustification` with:

```python
{
    "explained_tool_calls_outputs": {
        "get_user_0": "Actual: {'user_id': 123, 'name': 'John Doe'}, Expected: {'user_id': 123, 'name': 'John Doe'}, Score: 1.0",
        "calculate_total_0": "Actual: {'total': 99.99}, Expected: {'total': 99.99}, Score: 1.0",
        "api_request_0": "Actual: {'status': 200, 'data': {}}, Expected: {'status': 200, 'data': {}}, Score: 1.0"
    }
}
```

## Best Practices

1. **Use non-strict mode by default** - Allows for minor variations in outputs
2. **Use strict mode for critical outputs** - Boolean flags, status codes, exact values
3. **Validate key fields** - Focus on important output fields
4. **Test error scenarios** - Verify tools return proper error outputs
5. **Consider data types** - Ensure strings, numbers, booleans are correct
6. **Test edge cases** - Empty responses, null values, error conditions
7. **Combine with other evaluators** - Use with [Tool Call Args](tool_call_args.md) for complete validation


## When to Use vs Other Evaluators

**Use Tool Call Output when**:

- Tool return values need validation
- Testing tool integration correctness
- Verifying data processing results
- Ensuring proper error handling

**Use Tool Call Args when**:

- Validating inputs to tools (not outputs)
- Testing parameter passing

**Use Output Evaluator when**:

- Validating final agent output (not tool outputs)
- Testing overall result

**Use JSON Similarity when**:

- Comparing general data structures
- Not specifically tool outputs

## Limitations

1. **Tool name matching** - Must match exact tool names from trace
2. **Order matters** - First expected output matches first actual call of that tool
3. **No temporal validation** - Doesn't verify when outputs occurred
4. **Case-sensitive** - Keys and values are case-sensitive

## Error Handling

The evaluator handles:

- **Missing tools**: Score 0.0 for that tool
- **Extra tool calls not in criteria**: Ignored
- **Null/empty outputs**: Compared based on mode
- **Type mismatches**: Scored based on mode

## Performance Considerations

- **Fast evaluation**: O(n*m) where n = expected outputs, m = actual tool calls
- **No LLM calls**: Deterministic and quick
- **JSON similarity overhead**: Slightly slower than exact match

## Related Evaluators

- [Tool Call Args Evaluator](tool_call_args.md): Validates tool arguments (inputs)
- [Tool Call Order Evaluator](tool_call_order.md): Validates tool call sequences
- [Tool Call Count Evaluator](tool_call_count.md): Validates tool usage frequencies
- [Output Evaluator](../eval/index.md#output-based-evaluators): For final agent outputs
- [JSON Similarity Evaluator](json_similarity.md): For general JSON comparison


