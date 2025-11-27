# Agent Evaluations

The UiPath SDK provides a comprehensive evaluation framework for assessing agent performance and behavior. This framework enables you to systematically measure and validate agent outputs, execution trajectories, and tool usage patterns.

## Overview

The evaluation framework consists of two main categories of evaluators, organized by what they evaluate:

### Output-Based Evaluators

These evaluators assess the final output/result produced by an agent:

-   **[Contains Evaluator](contains.md)**: Checks if the output contains specific text
-   **[Exact Match Evaluator](exact_match.md)**: Verifies exact string matching
-   **[JSON Similarity Evaluator](json_similarity.md)**: Measures structural similarity between JSON outputs
-   **[LLM Judge Output Evaluator](llm_judge_output.md)**: Uses LLM for semantic output evaluation and quality assessment

### Trajectory-Based Evaluators

These evaluators assess the execution path, decision-making process, and tool usage patterns during agent execution:

-   **[Tool Call Order Evaluator](tool_call_order.md)**: Validates the sequence in which tools are called
-   **[Tool Call Count Evaluator](tool_call_count.md)**: Verifies the frequency of tool calls
-   **[Tool Call Args Evaluator](tool_call_args.md)**: Checks tool call arguments for correctness
-   **[Tool Call Output Evaluator](tool_call_output.md)**: Validates the outputs returned by tool calls
-   **[LLM Judge Trajectory Evaluator](llm_judge_trajectory.md)**: Evaluates agent execution trajectories and decision-making with LLM judgment

### Custom Evaluators

When built-in evaluators don't meet your specific needs, you can create custom evaluators with your own logic.

Custom evaluators enable:

-   **Domain-specific validation**: Implement validation logic tailored to your industry or use case
-   **Complex scoring algorithms**: Use specialized algorithms like Jaccard similarity, Levenshtein distance, or custom metrics
-   **Tool call inspection**: Extract and validate data from specific tool calls in the agent trace
-   **Integration with external systems**: Connect to databases, APIs, or other validation services

See **[Custom Python Evaluators](custom_evaluators.md)** for detailed implementation guide, including:

-   Creating evaluator classes with proper type annotations
-   Implementing custom evaluation criteria and configuration
-   Extracting data from agent traces and tool calls
-   Registering evaluators with the CLI
-   Complete examples and best practices

## Core Concepts

### Evaluation Criteria

Each evaluator uses specific criteria to define what should be evaluated. Criteria can be specified per test case or set as defaults in the evaluator configuration.

### Evaluation Results

Evaluators return a score (typically between 0 and 1) along with optional details or justification for the score.

### Configuration

Each evaluator has a configuration class that defines:

-   **name**: The evaluator's identifier
-   **default_evaluation_criteria**: Default criteria if not specified per test
-   Evaluator-specific settings (e.g., `case_sensitive`, `strict`, `temperature`)

## Getting Started

To use an evaluator, you typically:

1. Import the evaluator class
2. Create an evaluator instance with configuration
3. Call the `evaluate()` method with agent execution data and criteria

```python
from uipath.eval.evaluators import ExactMatchEvaluator
from uipath.eval.models import AgentExecution

# Sample agent execution (this should be replaced with your agent run data)
agent_execution = AgentExecution(
    agent_input={"query": "Greet the world"},
    agent_output={"result": "hello, world!"},
    agent_trace=[],
)

# Create evaluator
evaluator = ExactMatchEvaluator(
    id="exact-match-1",
    config={
        "name": "ExactMatchEvaluator",
        "case_sensitive": False,
        "target_output_key": "result",
    }
)

# Evaluate
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"result": "Hello, World!"}}
)

print(f"Score: {result.score}")
```

## Best Practices

1. **Choose the right category**:
   - Use **Output-Based Evaluators** to validate what the agent produces (final results)
   - Use **Trajectory-Based Evaluators** to validate how the agent achieves results (decision-making and tool usage)

2. **Select appropriate evaluators within categories**:
   - For outputs: Use deterministic evaluators (exact match, contains, JSON similarity) for predictable outputs and LLM judges for semantic/quality assessment
   - For trajectories: Use tool call evaluators for specific validations and LLM judges for holistic behavior assessment

3. **Combine multiple evaluators**: Use different evaluators together for comprehensive evaluation (e.g., exact match for output + tool call order for trajectory)

4. **Set appropriate thresholds**: Define minimum acceptable scores based on your use case

5. **Evaluate both outputs and trajectories**: For complex agents, validate both what they produce and how they produce it

6. **Create custom evaluators when needed**: If built-in evaluators don't cover your use case, implement custom evaluators with domain-specific logic

## Running Evaluations

The UiPath SDK provides a CLI command to run evaluations against your agents. The evaluation framework automatically discovers your agent and evaluation sets, or you can specify them explicitly.

### Basic Usage

```bash
# Auto-discover entrypoint and evaluation set
uipath eval

# Specify entrypoint and evaluation set
uipath eval <entrypoint> <eval-set-path>

# Run with parallel workers
uipath eval --workers 4

# Save results to file
uipath eval --output-file results.json

# Run specific evaluation IDs
uipath eval --eval-ids "['eval-1', 'eval-2']"

# Disable reporting to Studio Web
uipath eval --no-report
```

### Command Options

| Option | Type | Description |
|--------|------|-------------|
| `entrypoint` | Positional | Path to agent script (optional, auto-discovered if not specified) |
| `eval_set` | Positional | Path to evaluation set JSON file (optional, auto-discovered if not specified) |
| `--eval-ids` | List | Specific evaluation IDs to run from the eval set |
| `--eval-set-run-id` | String | Custom evaluation run ID (UUID generated if not provided) |
| `--workers` | Integer | Number of parallel workers (default: 1) |
| `--output-file` | Path | File path to save evaluation results |
| `--no-report` | Flag | Disable reporting results to Studio Web |

### Evaluation Sets

Evaluation sets are JSON files that define test cases and specify which evaluators to use:

```json
{
  "version": "1.0",
  "id": "my-eval-set",
  "evaluatorRefs": ["exact-match-1", "MyCustomEvaluator"],
  "evaluationItems": [
    {
      "id": "test-1",
      "agentInput": {"query": "What is 2+2?"},
      "evaluations": [
        {
          "evaluatorId": "exact-match-1",
          "evaluationCriteria": {
            "expectedOutput": {"result": "4"}
          }
        },
        {
          "evaluatorId": "MyCustomEvaluator",
          "evaluationCriteria": {
            "expectedValues": ["value1", "value2"]
          }
        }
      ]
    }
  ]
}
```

### Results

Evaluation results include:

-   **Score**: Numeric score (typically 0.0 to 1.0) or boolean pass/fail
-   **Details**: Additional information about the evaluation (justification, matched items, etc.)
-   **Metrics**: Token usage, latency, and other execution metrics
-   **Trace**: Full execution trace including tool calls and outputs

Results can be viewed in:

-   **Console output**: Real-time progress and summary
-   **Output file**: JSON file with detailed results (use `--output-file`)
-   **Studio Web**: Automatically reported if running in a Studio project (unless `--no-report` is specified)

## Reference Documentation

See the individual evaluator pages for detailed information on configuration, usage, and examples.

