# Exact Match Evaluator

The Exact Match Evaluator performs exact string matching between the agent's output and expected output. This is the most strict deterministic evaluator, useful for scenarios where output must match exactly.

## Overview

**Evaluator ID**: `exact-match`

**Use Cases**:

-   Validate exact responses (e.g., status codes, IDs)
-   Test deterministic outputs
-   Ensure precise formatting is maintained
-   Verify exact data values

**Returns**: Binary score (1.0 if exact match, 0.0 otherwise)

## Configuration

!!! note "Agent Output Structure"
    `agent_output` must always be a dictionary (e.g., `{"result": "value"}`). To evaluate simple values like strings or numbers, wrap them in a dict and use `target_output_key` to extract the specific field.

### ExactMatchEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ExactMatchEvaluator"` | The evaluator's name |
| `case_sensitive` | `bool` | `False` | Whether comparison is case-sensitive |
| `negated` | `bool` | `False` | If True, passes when outputs do NOT match |
| `target_output_key` | `str` | `"*"` | Specific key to extract from output (use "*" for entire output) |
| `default_evaluation_criteria` | `OutputEvaluationCriteria or None` | `None` | Default criteria if not specified per test |

## Evaluation Criteria

### OutputEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `expected_output` | `dict[str, Any] or str` | The expected output to match exactly |

## Examples

### Basic Usage

```python
from uipath.eval.evaluators import ExactMatchEvaluator
from uipath.eval.models import AgentExecution

# agent_output must be a dict
agent_execution = AgentExecution(
    agent_input={"query": "What is 2+2?"},
    agent_output={"result": "4"},
    agent_trace=[]
)

# Create evaluator - extracts "result" field for comparison
evaluator = ExactMatchEvaluator(
    id="exact-match-1",
    config={
        "name": "ExactMatchEvaluator",
        "case_sensitive": False,
        "target_output_key": "result"  # Extract the "result" field
    }
)

# Evaluate - compares just the "result" field value
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"result": "4"}}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Case-Sensitive Matching

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"status": "SUCCESS"},
    agent_trace=[]
)

evaluator = ExactMatchEvaluator(
    id="exact-match-case",
    config={
        "name": "ExactMatchEvaluator",
        "case_sensitive": True,
        "target_output_key": "status"  # Extract the "status" field
    }
)

# Fails due to case mismatch
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"status": "success"}}
)

print(f"Score: {result.score}")  # Output: 0.0

# This would pass
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"status": "SUCCESS"}}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Matching Structured Outputs

When `target_output_key` is `"*"` (default), the entire output dict is compared:

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"status": "success", "code": 200},
    agent_trace=[]
)

evaluator = ExactMatchEvaluator(
    id="exact-match-dict",
    config={
        "name": "ExactMatchEvaluator",
        "target_output_key": "*"  # Compare entire output (default)
    }
)

# Entire dict structure must match
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"status": "success", "code": 200}}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Target Specific Field

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={
        "result": "approved",
        "timestamp": "2024-01-01T12:00:00Z"
    },
    agent_trace=[]
)

evaluator = ExactMatchEvaluator(
    id="exact-match-field",
    config={
        "name": "ExactMatchEvaluator",
        "target_output_key": "result"
    }
)

# Only checks the "result" field
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"result": "approved"}}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Negated Mode

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"result": "error"},
    agent_trace=[]
)

evaluator = ExactMatchEvaluator(
    id="exact-match-negated",
    config={
        "name": "ExactMatchEvaluator",
        "negated": True,
        "target_output_key": "result"  # Extract the "result" field
    }
)

# Passes because outputs do NOT match
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"result": "success"}}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Using Default Criteria

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"status": "OK"},
    agent_trace=[]
)

evaluator = ExactMatchEvaluator(
    id="exact-match-default",
    config={
        "name": "ExactMatchEvaluator",
        "target_output_key": "status",  # Extract the "status" field
        "default_evaluation_criteria": {"expected_output": {"status": "OK"}}
    }
)

# Use default criteria
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution, evaluation_criteria=None
)

print(f"Score: {result.score}")  # Output: 1.0
```

## Best Practices

1. **Use for deterministic outputs** where exact matches are expected
2. **Consider case sensitivity** based on your use case
3. **Use case-insensitive mode** by default for more robust tests
4. **For structured data**, consider using [JSON Similarity Evaluator](json_similarity.md) instead
5. **Combine with other evaluators** for comprehensive testing
6. **Be careful with whitespace** - exact match includes all whitespace characters

## When NOT to Use

- When output can vary slightly but still be correct
- For natural language outputs (use [LLM Judge](llm_judge_output.md) instead)
- When comparing complex JSON structures (use [JSON Similarity](json_similarity.md))
- When partial matches are acceptable (use [Contains](contains.md))

## Related Evaluators

- [Contains Evaluator](contains.md): For partial string matching
- [JSON Similarity Evaluator](json_similarity.md): For flexible JSON comparison
- [LLM Judge Output Evaluator](llm_judge_output.md): For semantic similarity


