# Contains Evaluator

The Contains Evaluator checks whether the agent's output contains a specific search text. This is useful for validating that certain keywords, phrases, or patterns appear in the output without requiring an exact match.

## Overview

**Evaluator ID**: `contains`

**Use Cases**:

-   Verify specific keywords or phrases appear in output
-   Check for presence of expected content
-   Test that error messages or warnings contain specific text
-   Validate outputs include required information

**Returns**: Binary score (1.0 if found, 0.0 if not found)

## Configuration

!!! note "Agent Output Structure"
    `agent_output` must always be a dictionary. When comparing, the value (or specific field via `target_output_key`) is converted to a string before checking if it contains the search text.

### ContainsEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"ContainsEvaluator"` | The evaluator's name |
| `case_sensitive` | `bool` | `False` | Whether comparison is case-sensitive |
| `negated` | `bool` | `False` | If True, passes when text is NOT found |
| `target_output_key` | `str` | `"*"` | Specific key to extract from output (use "*" for entire output) |
| `default_evaluation_criteria` | `ContainsEvaluationCriteria or None` | `None` | Default criteria if not specified per test |

## Evaluation Criteria

### ContainsEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `search_text` | `str` | The text to search for in the output |

## Examples

### Basic Usage

```python
from uipath.eval.evaluators import ContainsEvaluator
from uipath.eval.models import AgentExecution

# Sample agent execution
agent_execution = AgentExecution(
    agent_input={"query": "What is the capital of France?"},
    agent_output={"response": "The capital of France is Paris."},
    agent_trace=[],
)

# Create evaluator - extracts "response" field for comparison
evaluator = ContainsEvaluator(
    id="contains-check",
    config={
        "name": "ContainsEvaluator",
        "case_sensitive": False,
        "target_output_key": "response"  # Extract the "response" field
    }
)

# Evaluate - searches in the "response" field value
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"search_text": "Paris"}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Case-Sensitive Search

```python
# Sample agent execution
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"message": "Hello World"},
    agent_trace=[],
)

evaluator = ContainsEvaluator(
    id="contains-case-sensitive",
    config={
        "name": "ContainsEvaluator",
        "case_sensitive": True,
        "target_output_key": "message"  # Extract the "message" field
    }
)

# This will fail because of case mismatch
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"search_text": "hello"}
)

print(f"Score: {result.score}")  # Output: 0.0
```

### Negated Search

Use negation to ensure specific text is NOT present:

```python
# Sample agent execution
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"status": "Success: Operation completed"},
    agent_trace=[],
)

evaluator = ContainsEvaluator(
    id="contains-negated",
    config={
        "name": "ContainsEvaluator",
        "negated": True,
        "target_output_key": "status"  # Extract the "status" field
    }
)

# Passes because "error" is NOT found
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"search_text": "error"}
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Target Specific Output Field

```python
# Sample agent execution
agent_execution = AgentExecution(
    agent_input={},
    agent_output={
        "status": "success",
        "message": "User profile updated successfully"
    },
    agent_trace=[],
)

evaluator = ContainsEvaluator(
    id="contains-targeted",
    config={
        "name": "ContainsEvaluator",
        "target_output_key": "message"
    }
)

# Only searches within the "message" field
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"search_text": "updated"}
)

print(f"Score: {result.score}")  # Output: 1.0
```

## Best Practices

1. **Use case-insensitive matching** by default to make tests more robust
2. **Combine with other evaluators** for comprehensive validation
3. **Use negated mode** to ensure error messages or sensitive data are NOT present
4. **Target specific fields** when evaluating structured outputs to reduce false positives
5. **Remember substring matching** - this evaluator uses substring search, not full-text search

## Related Evaluators

- [Exact Match Evaluator](exact_match.md): For exact string matching
- [JSON Similarity Evaluator](json_similarity.md): For structural comparison
- [LLM Judge Output Evaluator](llm_judge_output.md): For semantic similarity


