# LLM Judge Output Evaluators

LLM Judge Output Evaluators use Language Models to assess the quality and semantic similarity of agent outputs. These evaluators are ideal for scenarios where deterministic comparison is insufficient and human-like judgment is needed.

## Overview

There are two variants of LLM Judge Output Evaluators:

1. **LLM Judge Output Evaluator** (`llm-judge-output-semantic-similarity`): General semantic similarity evaluation
2. **LLM Judge Strict JSON Similarity Output Evaluator** (`llm-judge-output-strict-json-similarity`): Strict JSON structure comparison with LLM judgment

**Use Cases**:

-   Evaluate natural language outputs
-   Assess semantic similarity beyond exact matching
-   Judge output quality based on intent and meaning
-   Validate structured outputs with flexible criteria

**Returns**: Continuous score from 0.0 to 1.0 with justification

## LLM Service Integration

LLM Judge evaluators require an LLM service to perform evaluations. By default, the evaluators use the **UiPathLlmService** to handle LLM requests, which automatically integrates with your configured LLM providers through the UiPath platform.

### Custom LLM Service

You can supply a custom LLM service that supports the following request format:

```python
{
    "model": "model-name",
    "messages": [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "evaluation prompt"}
    ],
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "evaluation_response",
            "schema": {
                # JSON schema for structured output
            }
        }
    },
    "max_tokens": 1000,  # or None
    "temperature": 0.0
}
```

The LLM service must:

- Accept messages with `system` and `user` roles
- Support structured output via `response_format` with JSON schema
- Return responses conforming to the specified schema
- Handle `temperature` and `max_tokens` parameters

### Model Selection

When configuring the evaluator, specify the model name according to your LLM service's conventions:

```python
evaluator = LLMJudgeOutputEvaluator(
    id="llm-judge-1",
    config={
        "name": "LLMJudgeOutputEvaluator",
        "model": "gpt-4o-2024-11-20",  # Use your service's model naming
        "temperature": 0.0
    }
)
```

!!! note "UiPathLlmService"
    The default `UiPathLlmService` supports multiple LLM providers configured through the UiPath platform. Model names follow the provider's conventions (e.g., `gpt-4o-2024-11-20` for OpenAI, `claude-3-5-sonnet-20241022` for Anthropic).

## LLM Judge Output Evaluator

### Configuration

#### LLMJudgeOutputEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"LLMJudgeOutputEvaluator"` | The evaluator's name |
| `prompt` | `str` | Default user prompt | Custom evaluation prompt |
| `model` | `str` | `""` | LLM model to use for judgment |
| `temperature` | `float` | `0.0` | LLM temperature (0.0 for minimal non-determinism) |
| `max_tokens` | `int or None` | `None` | Maximum tokens for LLM response |
| `target_output_key` | `str` | `"*"` | Specific key to extract from output |
| `default_evaluation_criteria` | `OutputEvaluationCriteria or None` | `None` | Default criteria |

### Evaluation Criteria

#### OutputEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `expected_output` | `dict[str, Any] or str` | The expected output for comparison |

### Prompt Placeholders

The prompt template supports these placeholders:

- `{{ActualOutput}}`: Replaced with the agent's actual output
- `{{ExpectedOutput}}`: Replaced with the expected output from criteria

### Examples

#### Basic Semantic Similarity

```python
from uipath.eval.evaluators import LLMJudgeOutputEvaluator
from uipath.eval.models import AgentExecution

agent_execution = AgentExecution(
    agent_input={"query": "What is the capital of France?"},
    agent_output={"answer": "Paris is the capital city of France."},
    agent_trace=[]
)

evaluator = LLMJudgeOutputEvaluator(
    id="llm-judge-1",
    config={
        "name": "LLMJudgeOutputEvaluator",
        # Use the UiPathLlmChatService convention for model names; should be changed according to selected service
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0,
        "target_output_key": "answer"  # Extract the "answer" field
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"answer": "The capital of France is Paris."}
    }
)

print(f"Score: {result.score}")  # e.g., 0.95
print(f"Justification: {result.details}")  # LLM's reasoning
```

#### Custom Evaluation Prompt

```python
custom_prompt = """
Compare the actual output with the expected output.
Focus on semantic meaning and intent rather than exact wording.

Actual Output: {{ActualOutput}}
Expected Output: {{ExpectedOutput}}

Provide a score from 0-100 based on semantic similarity.
"""

agent_execution = AgentExecution(
    agent_input={},
    agent_output={"message": "The product has been successfully added to your cart."},
    agent_trace=[]
)

evaluator = LLMJudgeOutputEvaluator(
    id="llm-judge-custom",
    config={
        "name": "LLMJudgeOutputEvaluator",
        "model": "gpt-4o-2024-11-20",
        "prompt": custom_prompt,
        "temperature": 0.0,
        "target_output_key": "message"  # Extract the "message" field
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"message": "Item added to shopping cart."}
    }
)

print(f"Score: {result.score}")
print(f"Justification: {result.details}")
```

#### Evaluating Natural Language Quality

```python
agent_execution = AgentExecution(
    agent_input={"task": "Write a professional email"},
    agent_output={"email": """Dear Customer,

Thank you for your inquiry. We have reviewed your request
and are pleased to inform you that we can accommodate your
needs. Please let us know if you have any questions.

Best regards,
Support Team"""},
    agent_trace=[]
)

evaluator = LLMJudgeOutputEvaluator(
    id="llm-judge-quality",
    config={
        "name": "LLMJudgeOutputEvaluator",
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0,
        "target_output_key": "email"  # Extract the "email" field
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {"email": "A professional, courteous response addressing the customer's inquiry"}
    }
)

print(f"Score: {result.score}")
print(f"Justification: {result.details}")
```

## LLM Judge Strict JSON Similarity Output Evaluator

This variant performs **per-key matching** on JSON structures with penalty-based scoring. The LLM evaluates each top-level key individually and calculates a final score based on key-level matches.

### How It Works

1. **Key Inventory**: Identifies all top-level keys in expected and actual outputs
2. **Per-Key Matching**: For each expected key, checks if it exists in actual output
3. **Content Assessment**: For matching keys, evaluates content similarity (identical/similar/different)
4. **Penalty-Based Scoring**: Calculates score using these penalties per key:
   - **Missing key** (not in actual): `100/N` penalty
   - **Wrong key** (exists but significantly different content): `100/N` penalty
   - **Similar key** (exists with similar content): `50/N` penalty
   - **Identical key** (exists with identical content): `0` penalty
   - **Extra key** (in actual but not expected): `10/N` penalty

   Where `N` = total number of expected keys

**Final Score**: `100 - total_penalty` (scale 0-100)

### Why "Strict"?

Unlike the standard `LLMJudgeOutputEvaluator` which evaluates semantic similarity holistically, this evaluator:

-   **Enforces structural matching**: Each expected key must be present
-   **Penalizes missing keys heavily**: Same as wrong content (100/N penalty)
-   **Evaluates per-key**: Independence between key evaluations
-   **Deterministic scoring formula**: Mechanical calculation based on key-level assessments

### Configuration

#### LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig

Same as `LLMJudgeOutputEvaluatorConfig` but with:

- **name**: `"LLMJudgeStrictJSONSimilarityOutputEvaluator"`
- **prompt**: Specialized prompt enforcing per-key matching and penalty calculations

### Examples

#### Strict JSON Structure Evaluation

```python
from uipath.eval.evaluators import LLMJudgeStrictJSONSimilarityOutputEvaluator

evaluator = LLMJudgeStrictJSONSimilarityOutputEvaluator(
    id="llm-json-strict",
    config={
        "name": "LLMJudgeStrictJSONSimilarityOutputEvaluator",
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0
    }
)

agent_execution = AgentExecution(
    agent_input={},
    agent_output={
        "status": "success",
        "user_id": 12345,
        "name": "John Doe",
        "email": "john@example.com"
    },
    agent_trace=[]
)

result = await evaluator.evaluate(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_output": {
            "status": "success",
            "user_id": 12345,
            "name": "John Doe",
            "email": "john@example.com"
        }
    }
)

print(f"Score: {result.score}")
print(f"Justification: {result.details}")
```

## Understanding LLM Judge Response

The LLM returns a structured response:

```python
# Result structure
{
    "score": 0.85,  # 0.0 to 1.0 (normalized from 0-100)
    "details": "The outputs convey the same meaning..."  # LLM justification
}
```

## Best Practices

1. **Use temperature 0.0** for deterministic evaluations
2. **Craft clear prompts** - Be specific about evaluation criteria
3. **Include both placeholders** - Always use `{{ActualOutput}}` and `{{ExpectedOutput}}`
4. **Set score thresholds** - Define minimum acceptable scores (e.g., ≥ 0.8)
5. **Review justifications** - Use LLM explanations to understand scores
6. **Cost awareness** - LLM evaluations use API calls, consider token costs

## When to Use vs Other Evaluators

**Use LLM Judge Output when**:

-   Semantic meaning matters more than exact wording
-   Natural language outputs need human-like judgment
-   Context and intent are important
-   Flexible evaluation criteria needed

**Use Deterministic Evaluators when**:
- Exact matches are required
- Output format is predictable
- Speed and cost are priorities
- No ambiguity in correctness

## Configuration Tips

### Temperature Settings

- **0.0**: Deterministic, consistent results (recommended)
- **0.1**: Slight variation for nuanced judgment
- **>0.3**: Not recommended (too inconsistent)

## Error Handling

The evaluator will raise `UiPathEvaluationError` if:

- LLM service is unavailable
- Prompt doesn't contain required placeholders
- LLM response cannot be parsed
- Model returns invalid JSON

## Related Evaluators

- [LLM Judge Trajectory Evaluator](llm_judge_trajectory.md): For evaluating agent execution paths
- [JSON Similarity Evaluator](json_similarity.md): For deterministic JSON comparison
- [Exact Match Evaluator](exact_match.md): For strict string matching
- [Contains Evaluator](contains.md): For substring matching


