# JSON Similarity Evaluator

The JSON Similarity Evaluator performs flexible structural comparison of JSON-like outputs using a tree-based matching algorithm. It recursively traverses the JSON structure as a tree and compares leaf nodes (actual values) with type-specific similarity measures.

## Overview

**Evaluator ID**: `json-similarity`

**Use Cases**:

-   Compare complex nested JSON structures
-   Validate API responses with tolerance for minor differences
-   Test structured outputs where exact matches are too strict
-   Measure similarity when numeric values may vary slightly

**Returns**: Continuous score from 0.0 to 1.0 (0-100% similarity)

## Configuration

!!! note "Agent Output Structure"
    `agent_output` must always be a dictionary. The evaluator compares dictionary structures recursively, making it ideal for complex nested JSON-like outputs.

### JsonSimilarityEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"JsonSimilarityEvaluator"` | The evaluator's name |
| `target_output_key` | `str` | `"*"` | Specific key to extract from output (use "*" for entire output) |
| `default_evaluation_criteria` | `OutputEvaluationCriteria or None` | `None` | Default criteria if not specified per test |

## Evaluation Criteria

### OutputEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `expected_output` | `dict[str, Any] or str` | The expected JSON structure to compare against |

## How It Works

The evaluator uses a **tree-based matching algorithm**:

1. **Tree Structure**: The JSON/dictionary structure is treated as a tree, with nested objects and arrays forming branches
2. **Leaf Comparison**: Only leaf nodes (actual values) are compared, using type-specific similarity measures:
   - **Strings**: Levenshtein distance (edit distance) to measure textual similarity
   - **Numbers**: Absolute difference with tolerance (within 1% considered similar)
   - **Booleans**: Exact match required (binary comparison)
3. **Structural Recursion**:
   - **Objects**: Recursively traverses and compares all expected keys
   - **Arrays**: Compares elements by position (index-based matching)

**Score Calculation**: `matched_leaves / total_leaves`

The final score represents the percentage of matching leaf nodes in the tree structure.

## Examples

### Basic JSON Comparison

```python
from uipath.eval.evaluators import JsonSimilarityEvaluator
from uipath.eval.models import AgentExecution

agent_execution = AgentExecution(
    agent_input={},
    agent_output={"name": "John Doe", "age": 30, "city": "New York"},
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-1",
    config={
        "name": "JsonSimilarityEvaluator"
        # target_output_key defaults to "*" - compares entire output dict
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"name": "John Doe", "age": 30, "city": "New York"}
    }
)

print(f"Score: {result.score}")  # Output: 1.0 (perfect match)
print(f"Details: {result.details}")  # Matched leaves: 3, Total leaves: 3
```

### Numeric Tolerance

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"temperature": 20.5, "humidity": 65},
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-numeric",
    config={"name": "JsonSimilarityEvaluator"}
)

# Slightly different numbers
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"temperature": 20.3, "humidity": 65}
    }
)

# High similarity despite numeric difference
print(f"Score: {result.score}")  # ~0.99 (very high similarity)
```

### String Similarity

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"status": "completed successfully"},
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-string",
    config={"name": "JsonSimilarityEvaluator"}
)

# Similar but not exact string
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"status": "completed sucessfully"}  # typo
    }
)

# High but not perfect similarity
print(f"Score: {result.score}")  # ~0.95 (high similarity despite typo)
```

### Nested Structures

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={
        "user": {
            "name": "Alice",
            "profile": {
                "age": 25,
                "location": "Paris"
            }
        },
        "status": "active"
    },
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-nested",
    config={"name": "JsonSimilarityEvaluator"}
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {
            "user": {
                "name": "Alice",
                "profile": {
                    "age": 25,
                    "location": "Paris"
                }
            },
            "status": "active"
        }
    }
)

print(f"Score: {result.score}")  # Output: 1.0
```

### Array Comparison

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={"items": ["apple", "banana", "orange"]},
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-array",
    config={"name": "JsonSimilarityEvaluator"}
)

# Partial match (2 out of 3 correct)
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"items": ["apple", "banana", "grape"]}
    }
)

print(f"Score: {result.score}")  # ~0.67 (2/3 correct)
```

### Handling Extra Keys in Actual Output

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={
        "name": "Bob",
        "age": 30,
        "extra_field": "ignored"  # Extra field in actual output
    },
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-extra",
    config={"name": "JsonSimilarityEvaluator"}
)

# Only expected keys are evaluated
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {
            "name": "Bob",
            "age": 30
        }
    }
)

print(f"Score: {result.score}")  # Output: 1.0 (extra fields ignored)
```

### Target Specific Field

```python
agent_execution = AgentExecution(
    agent_input={},
    agent_output={
        "result": {"score": 95, "passed": True},
        "metadata": {"timestamp": "2024-01-01"}
    },
    agent_trace=[]
)

evaluator = JsonSimilarityEvaluator(
    id="json-sim-targeted",
    config={
        "name": "JsonSimilarityEvaluator",
        "target_output_key": "result"
    }
)

# Only compares the "result" field
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"result": {"score": 95, "passed": True}}
    }
)

print(f"Score: {result.score}")  # Output: 1.0
```

## Scoring Details

The evaluator returns a `NumericEvaluationResult` with:

- **score** (`float`): Value between 0.0 and 1.0
- **details** (`str`): Explanation like "Matched leaves: 8, Total leaves: 10"

### Score Interpretation

| Score Range | Interpretation |
|-------------|----------------|
| 1.0 | Perfect match |
| 0.9 - 0.99 | Very high similarity (minor differences) |
| 0.7 - 0.89 | Good similarity (some differences) |
| 0.5 - 0.69 | Moderate similarity (significant differences) |
| 0.0 - 0.49 | Low similarity (major differences) |

## Best Practices

1. **Use for structured data** like JSON, dictionaries, or objects
2. **Set score thresholds** based on your tolerance for differences (e.g., require score ≥ 0.9)
3. **Combine with exact match** for critical fields that must match exactly
4. **Only expected keys matter** - extra keys in actual output are ignored
5. **Consider array order** - elements are compared by position
6. **Useful for API testing** where responses may have minor variations

## When to Use vs Other Evaluators

**Use JSON Similarity when**:
- Comparing complex nested structures
- Minor numeric differences are acceptable
- String typos shouldn't cause complete failure
- You need a granular similarity score

**Use Exact Match when**:
- Output must match precisely
- No tolerance for any differences
- Simple string comparison needed

**Use LLM Judge when**:
- Semantic meaning matters more than structure
- Natural language comparison needed
- Context and intent should be considered

## Related Evaluators

- [Exact Match Evaluator](exact_match.md): For strict matching
- [Contains Evaluator](contains.md): For substring matching
- [LLM Judge Output Evaluator](llm_judge_output.md): For semantic comparison


